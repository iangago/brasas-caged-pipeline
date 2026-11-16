"""
TRANSFORMACAO: limpa os microdados e resume por ocupacao (CBO).

Regras (documentadas no README):
  - Saldo correto = MOV + FOR - EXC, filtrando pelo mes da movimentacao (competencia).
    Uma exclusao tem efeito inverso ao do evento: excluir uma admissao reduz o saldo.
  - Salario: a coluna "salario" ja e o salario MENSAL declarado. Entram admissoes com
    salario > 0 e unidade de pagamento hora/dia/semana/quinzena/mes. Saem tarefa,
    variavel e nao identificado (no teste, mediana de R$ 9,51 e R$ 0).
  - Usa MEDIANA, nao media: existem salarios digitados errado (ex.: R$ 27,8 milhoes).
"""

import unicodedata

import pandas as pd

# Codigos de "unidadesaláriocódigo" no dicionario oficial:
# 1 Hora, 2 Dia, 3 Semana, 4 Quinzena, 5 Mes, 6 Tarefa, 7 Variavel, 99 Nao identificado
UNIDADES_VALIDAS = {"1", "2", "3", "4", "5"}

# Nome normalizado da coluna no arquivo -> nome usado no pipeline
COLUNAS = {
    "competenciamov": "competencia",
    "saldomovimentacao": "saldo",
    "cbo2002ocupacao": "cbo",
    "salario": "salario",
    "unidadesalariocodigo": "unidade_salario",
}


def normalizar_nome(texto: str) -> str:
    """'saldomovimentação' -> 'saldomovimentacao'. Protege contra mudanca de acento."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return t.lower().replace(" ", "").strip()


def ler_microdados(caminho_txt: str) -> pd.DataFrame:
    """Le so as 5 colunas necessarias (de 28) e converte os tipos."""
    cabecalho = pd.read_csv(caminho_txt, sep=";", encoding="utf-8", nrows=0).columns
    mapa = {normalizar_nome(c): c for c in cabecalho}
    faltando = [c for c in COLUNAS if c not in mapa]
    if faltando:
        raise ValueError(f"colunas ausentes em {caminho_txt}: {faltando}")

    df = pd.read_csv(caminho_txt, sep=";", encoding="utf-8", dtype=str,
                     usecols=[mapa[c] for c in COLUNAS])
    df = df.rename(columns={mapa[c]: novo for c, novo in COLUNAS.items()})
    return limpar(df)


def limpar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # CBO tem 6 digitos; codigos que comecam com 0 perdem o zero no arquivo.
    df["cbo"] = df["cbo"].str.strip().str.zfill(6)
    # saldo: +1 = admissao, -1 = desligamento
    df["saldo"] = pd.to_numeric(df["saldo"], errors="coerce").fillna(0).astype("int8")
    # salario vem como "1621,00" (virgula decimal)
    df["salario"] = pd.to_numeric(
        df["salario"].str.replace(",", ".", regex=False), errors="coerce")
    df["unidade_salario"] = df["unidade_salario"].str.strip()
    return df


def filtrar_janela(df: pd.DataFrame, janela: set[str]) -> pd.DataFrame:
    """Mantem so movimentacoes que aconteceram dentro da janela de meses."""
    return df[df["competencia"].isin(janela)]


def contar_por_ocupacao(df: pd.DataFrame, sinal: int) -> pd.DataFrame:
    """Admissoes e desligamentos por CBO. sinal = +1 (MOV, FOR) ou -1 (EXC)."""
    marcado = pd.DataFrame({
        "cbo": df["cbo"],
        "admissoes": (df["saldo"] == 1).astype("int32"),
        "desligamentos": (df["saldo"] == -1).astype("int32"),
    })
    return marcado.groupby("cbo").sum() * sinal


def salarios_de_admissao(df: pd.DataFrame) -> pd.DataFrame:
    """Salarios que entram na mediana: admissoes, salario > 0, unidade valida."""
    ok = ((df["saldo"] == 1)
          & (df["salario"] > 0)
          & (df["unidade_salario"].isin(UNIDADES_VALIDAS)))
    return df.loc[ok, ["cbo", "salario"]].astype({"salario": "float32"})


def consolidar(contagens: list[pd.DataFrame], salarios: list[pd.DataFrame],
               dicionario_cbo: pd.DataFrame) -> pd.DataFrame:
    """Soma MOV + FOR - EXC, calcula a mediana de salario e junta o nome da ocupacao."""
    total = pd.concat(contagens).groupby(level=0).sum()
    total["saldo"] = total["admissoes"] - total["desligamentos"]
    # Taxa de crescimento relativa: saldo / admissoes. Nao favorece profissao so por
    # ser grande (o saldo absoluto de "vendedor" sempre seria enorme).
    total["taxa_saldo"] = (total["saldo"] / total["admissoes"].where(total["admissoes"] > 0)).round(4)

    sal = pd.concat(salarios)
    mediana = sal.groupby("cbo")["salario"].agg(
        salario_mediano_admissao="median", n_salarios="size")

    resumo = (total.join(mediana, how="left")
              .reset_index()
              .rename(columns={"cbo": "cbo_ocupacao"})
              .merge(dicionario_cbo, on="cbo_ocupacao", how="left"))
    resumo["salario_mediano_admissao"] = resumo["salario_mediano_admissao"].round(2)
    resumo["n_salarios"] = resumo["n_salarios"].fillna(0).astype(int)
    colunas = ["cbo_ocupacao", "nome_ocupacao", "admissoes", "desligamentos", "saldo",
               "taxa_saldo", "salario_mediano_admissao", "n_salarios"]
    return resumo[colunas].sort_values("admissoes", ascending=False, ignore_index=True)
