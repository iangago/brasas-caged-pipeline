"""
Pipeline do CAGED - Etapa 2: resumo de 12 meses por ocupacao (CBO)

O que este script faz, em ordem:
  1. EXTRACAO   - descobre os 12 meses mais recentes publicados e baixa, de cada
                  mes, os 3 arquivos do Novo CAGED (MOV, FOR, EXC) do FTP do PDET.
  2. TRANSFORMACAO - le so as colunas necessarias, limpa (CBO com 6 digitos,
                  salario so mensal e > 0) e soma as movimentacoes por ocupacao.
  3. CARGA      - grava caged_resumo.csv (uma linha por ocupacao). O GitHub Actions
                  faz o commit desse arquivo no repositorio.

Por que 3 arquivos por mes?
  - MOV: movimentacoes (admissoes e desligamentos) declaradas no prazo.
  - FOR: declaradas FORA do prazo. Chegam meses depois e se referem a meses
         anteriores (a coluna competenciamov diz a qual mes pertencem).
  - EXC: EXCLUSOES - declaracoes antigas que a empresa cancelou. Tem que subtrair.
  Resultado correto = MOV + FOR - EXC, sempre agrupando pelo mes de competencia
  (o mes em que a movimentacao aconteceu, nao o mes em que foi declarada).
"""

import ftplib
import glob
import os
import shutil
import sys
import time
import unicodedata
from datetime import date, datetime, timezone

import pandas as pd
import py7zr

FTP_HOST = "ftp.mtps.gov.br"
BASE = "/pdet/microdados/NOVO CAGED"
N_MESES = 12
SAIDA = "caged_resumo.csv"
TMP = "tmp_caged"
FONTE = "Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados"

# Codigo da unidade de salario que significa "por mes" no Novo CAGED.
# Salarios por hora, dia, tarefa etc. nao sao comparaveis, entao ficam de fora.
UNIDADE_MENSAL = "5"


# ---------------------------------------------------------------- utilidades

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def norm(texto):
    """'saldomovimentação' -> 'saldomovimentacao' (sem acento, minusculo, sem espaco)."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return t.lower().replace(" ", "").strip()


def mes_anterior(a, m):
    return (a - 1, 12) if m == 1 else (a, m - 1)


# ---------------------------------------------------------------- 1. extracao

def conectar():
    ftp = ftplib.FTP(FTP_HOST, timeout=180)
    ftp.login()  # FTP publico, acesso anonimo
    return ftp


def meses_disponiveis(ftp):
    """Volta mes a mes a partir de hoje ate achar os N_MESES mais recentes publicados."""
    a, m = date.today().year, date.today().month
    meses = []
    tentativas = 0
    while len(meses) < N_MESES and tentativas < N_MESES + 6:
        a, m = mes_anterior(a, m)
        tentativas += 1
        comp = f"{a}{m:02d}"
        try:
            nomes = {n.split("/")[-1] for n in ftp.nlst(f"{BASE}/{a}/{comp}")}
        except ftplib.error_perm:
            nomes = set()
        if f"CAGEDMOV{comp}.7z" in nomes:
            meses.append(comp)
        elif meses:
            # Um buraco no meio da serie nao pode passar em silencio.
            sys.exit(f"ERRO: {comp} sem arquivo MOV no meio da serie.")
        else:
            log(f"{comp}: ainda nao publicado")
    if len(meses) < N_MESES:
        sys.exit(f"ERRO: so encontrei {len(meses)} meses.")
    return sorted(meses)


def baixar_e_extrair(ftp, tipo, comp):
    """Baixa CAGED<tipo><comp>.7z e devolve o caminho do .txt extraido."""
    nome = f"CAGED{tipo}{comp}.7z"
    pasta = f"{BASE}/{comp[:4]}/{comp}"
    arq_7z = os.path.join(TMP, nome)
    with open(arq_7z, "wb") as f:
        ftp.retrbinary(f"RETR {pasta}/{nome}", f.write, blocksize=1 << 20)
    destino = os.path.join(TMP, f"{tipo}{comp}")
    with py7zr.SevenZipFile(arq_7z, mode="r") as z:
        z.extractall(path=destino)
    os.remove(arq_7z)
    txts = glob.glob(f"{destino}/**/*.txt", recursive=True)
    if not txts:
        sys.exit(f"ERRO: {nome} nao tem .txt dentro.")
    return txts[0], destino


# ------------------------------------------------------------ 2. transformacao

COLUNAS = {
    "competenciamov": "competencia",
    "saldomovimentacao": "saldo",
    "cbo2002ocupacao": "cbo",
    "salario": "salario",
    "unidadesalariocodigo": "unidade_salario",
}


def ler_arquivo(txt):
    """Le so as 5 colunas que interessam, como texto, e padroniza os nomes."""
    cabecalho = pd.read_csv(txt, sep=";", encoding="utf-8", nrows=0).columns
    mapa = {norm(c): c for c in cabecalho}
    faltando = [c for c in COLUNAS if c not in mapa]
    if faltando:
        sys.exit(f"ERRO: colunas ausentes em {txt}: {faltando}. Colunas: {list(cabecalho)}")
    df = pd.read_csv(txt, sep=";", encoding="utf-8", dtype=str,
                     usecols=[mapa[c] for c in COLUNAS])
    df = df.rename(columns={mapa[c]: novo for c, novo in COLUNAS.items()})

    # CBO tem 6 digitos; alguns codigos perdem o zero a esquerda no arquivo.
    df["cbo"] = df["cbo"].str.strip().str.zfill(6)
    # saldo: +1 = admissao, -1 = desligamento
    df["saldo"] = pd.to_numeric(df["saldo"], errors="coerce").fillna(0).astype("int8")
    # salario vem como "1621,00" (virgula decimal)
    df["salario"] = pd.to_numeric(df["salario"].str.replace(",", ".", regex=False),
                                  errors="coerce")
    return df


def contar(df, sinal):
    """Admissoes, desligamentos e saldo por ocupacao. sinal=-1 para o arquivo EXC."""
    marcado = pd.DataFrame({
        "cbo": df["cbo"],
        "admissoes": (df["saldo"] == 1).astype("int32"),
        "desligamentos": (df["saldo"] == -1).astype("int32"),
    })
    return marcado.groupby("cbo").sum() * sinal


def salarios_validos(df):
    """Salarios de admissao que entram na mediana: mensais e maiores que zero."""
    adm = df[(df["saldo"] == 1)
             & (df["unidade_salario"] == UNIDADE_MENSAL)
             & (df["salario"] > 0)]
    return adm[["cbo", "salario"]].astype({"salario": "float32"})


# ---------------------------------------------------------------- principal

def main():
    os.makedirs(TMP, exist_ok=True)
    ftp = conectar()
    meses = meses_disponiveis(ftp)
    janela = set(meses)
    log(f"Janela de 12 meses: {meses[0]} a {meses[-1]}")

    contagens = []       # pedacos de admissoes/desligamentos por cbo
    salarios = []        # salarios de admissao validos (para a mediana)
    checagem = []        # totais por mes, para conferir com o numero oficial

    for comp in meses:
        for tipo, sinal in (("MOV", 1), ("FOR", 1), ("EXC", -1)):
            inicio = time.time()
            try:
                txt, pasta = baixar_e_extrair(ftp, tipo, comp)
            except ftplib.error_perm:
                log(f"{tipo}{comp}: arquivo nao existe, seguindo")
                continue
            df = ler_arquivo(txt)
            shutil.rmtree(pasta)

            # So entra o que aconteceu DENTRO da janela de 12 meses.
            # (FOR e EXC trazem movimentacoes de meses antigos.)
            df = df[df["competencia"].isin(janela)]

            contagens.append(contar(df, sinal))
            if tipo != "EXC":
                salarios.append(salarios_validos(df))
                # Pequena simplificacao: exclusoes nao saem da mediana de salario
                # (sao poucas e nao mudam uma mediana de forma relevante).

            for c, sub in df.groupby("competencia"):
                checagem.append({"competencia": c, "tipo": tipo,
                                 "saldo": int(sub["saldo"].sum()) * sinal})
            log(f"{tipo}{comp}: {len(df):,} linhas na janela ({time.time() - inicio:.0f}s)")

            # Para a etapa 1 de validacao: distribuicao das unidades de salario.
            if tipo == "MOV" and comp == meses[-1]:
                adm = df[df["saldo"] == 1]
                resumo_unid = adm.groupby("unidade_salario")["salario"].agg(["size", "median"])
                log("Unidades de salario nas admissoes do ultimo mes:\n" + resumo_unid.to_string())
    ftp.quit()

    # Soma tudo: MOV + FOR - EXC
    total = pd.concat(contagens).groupby(level=0).sum()
    total["saldo"] = total["admissoes"] - total["desligamentos"]

    sal = pd.concat(salarios)
    med = sal.groupby("cbo")["salario"].agg(salario_mediano_admissao="median",
                                             n_salarios="size")
    resumo = total.join(med, how="left").reset_index().rename(columns={"cbo": "cbo_ocupacao"})
    resumo["salario_mediano_admissao"] = resumo["salario_mediano_admissao"].round(2)
    resumo["n_salarios"] = resumo["n_salarios"].fillna(0).astype(int)
    resumo["recorte"] = "brasil"
    resumo["periodo_inicio"] = meses[0]
    resumo["periodo_fim"] = meses[-1]
    resumo["fonte"] = FONTE
    resumo["data_processamento"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resumo = resumo.sort_values("admissoes", ascending=False)

    # --------------------------------------------- checagens de qualidade
    print("\n=== SALDO BRASIL POR MES (MOV + FOR - EXC) ===")
    chk = pd.DataFrame(checagem).pivot_table(index="competencia", columns="tipo",
                                             values="saldo", aggfunc="sum").fillna(0)
    chk["total"] = chk.sum(axis=1)
    print(chk.astype(int).to_string())
    print(f"\nSaldo 12 meses: {int(resumo['saldo'].sum()):,}")
    print(f"Ocupacoes: {len(resumo):,}")
    print(f"Ocupacoes sem salario valido: {(resumo['n_salarios'] == 0).sum():,}")

    assert len(resumo) > 2000, "Poucas ocupacoes: algo deu errado na leitura."
    assert (resumo["cbo_ocupacao"].str.len() == 6).all(), "CBO fora do padrao de 6 digitos."

    resumo.to_csv(SAIDA, index=False, encoding="utf-8")
    log(f"Gravado {SAIDA} ({len(resumo):,} linhas)")
    print(resumo.head(10).to_string(index=False))
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
