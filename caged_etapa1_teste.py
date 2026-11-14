"""
Pipeline do CAGED - Etapa 1 (teste)

Baixa UM mes do Novo CAGED (arquivo de movimentacoes, CAGEDMOV) do FTP do
PDET / Ministerio do Trabalho e mostra o que tem dentro:
  - se o runner do GitHub alcanca o FTP
  - quais arquivos existem na pasta do mes (MOV, FOR, EXC)
  - encoding, separador e nomes das colunas
  - formato do codigo CBO e do salario
  - um resumo nacional (admissoes, desligamentos, saldo) e o top 10 de ocupacoes

Nao grava nada. Serve so para validar o caminho antes do script do resumo (etapa 2).
"""

import ftplib
import glob
import os
import sys
import time
import unicodedata
from datetime import date

import pandas as pd
import py7zr

FTP_HOST = "ftp.mtps.gov.br"
BASE = "/pdet/microdados/NOVO CAGED"
MESES_PARA_PROCURAR = 8  # o CAGED sai com ~1 a 2 meses de atraso
PASTA_DADOS = "dados"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def norm(texto):
    """Tira acento, espaco e deixa minusculo: 'Saldo Movimentação' -> 'saldomovimentacao'."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower().replace(" ", "").strip()


def meses_anteriores(n):
    a, m = date.today().year, date.today().month
    for _ in range(n):
        m -= 1
        if m == 0:
            a, m = a - 1, 12
        yield a, m


def conectar():
    log(f"Conectando em {FTP_HOST} ...")
    ftp = ftplib.FTP(FTP_HOST, timeout=120)
    ftp.login()  # acesso anonimo
    log("Conectado.")
    return ftp


def achar_mes_mais_recente(ftp):
    for a, m in meses_anteriores(MESES_PARA_PROCURAR):
        comp = f"{a}{m:02d}"
        pasta = f"{BASE}/{a}/{comp}"
        try:
            nomes = [n.split("/")[-1] for n in ftp.nlst(pasta)]
        except ftplib.error_perm:
            log(f"{comp}: pasta nao existe ainda")
            continue
        alvo = f"CAGEDMOV{comp}.7z"
        if alvo in nomes:
            log(f"Mes mais recente disponivel: {comp}")
            log(f"Arquivos na pasta: {sorted(nomes)}")
            return pasta, alvo
        log(f"{comp}: pasta existe, mas sem {alvo}. Arquivos: {sorted(nomes)}")
    sys.exit(f"ERRO: nenhum CAGEDMOV encontrado nos ultimos {MESES_PARA_PROCURAR} meses.")


def baixar(ftp, pasta, alvo):
    log(f"Baixando {alvo} ...")
    inicio = time.time()
    with open(alvo, "wb") as f:
        ftp.retrbinary(f"RETR {pasta}/{alvo}", f.write, blocksize=1 << 20)
    tamanho_mb = os.path.getsize(alvo) / 1e6
    log(f"Baixado: {tamanho_mb:.1f} MB em {time.time() - inicio:.0f}s")


def descompactar(alvo):
    log("Descompactando ...")
    os.makedirs(PASTA_DADOS, exist_ok=True)
    with py7zr.SevenZipFile(alvo, mode="r") as z:
        z.extractall(path=PASTA_DADOS)
    arquivos = glob.glob(f"{PASTA_DADOS}/**/*.txt", recursive=True)
    if not arquivos:
        sys.exit(f"ERRO: nenhum .txt dentro do .7z. Conteudo: {os.listdir(PASTA_DADOS)}")
    txt = arquivos[0]
    log(f"Arquivo extraido: {txt} ({os.path.getsize(txt) / 1e6:.0f} MB)")
    return txt


def detectar_encoding(txt):
    with open(txt, "rb") as f:
        amostra = f.read(2_000_000)
    try:
        amostra.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def main():
    ftp = conectar()
    pasta, alvo = achar_mes_mais_recente(ftp)
    baixar(ftp, pasta, alvo)
    ftp.quit()

    txt = descompactar(alvo)
    enc = detectar_encoding(txt)
    log(f"Encoding detectado: {enc}")

    # 1) Cabecalho e primeiras linhas
    amostra = pd.read_csv(txt, sep=";", encoding=enc, dtype=str, nrows=5)
    print("\n=== COLUNAS ===")
    for c in amostra.columns:
        print(f"  {c!r:45} -> {norm(c)}")
    print("\n=== 3 PRIMEIRAS LINHAS ===")
    print(amostra.head(3).T.to_string())

    # 2) Ler so as colunas que interessam
    mapa = {norm(c): c for c in amostra.columns}
    desejadas = {
        "saldo": "saldomovimentacao",
        "cbo": "cbo2002ocupacao",
        "salario": "salario",
        "uf": "uf",
        "competencia": "competenciamov",
    }
    faltando = [v for v in desejadas.values() if v not in mapa]
    if faltando:
        print(f"\nATENCAO: colunas nao encontradas: {faltando}")
    usar = {k: mapa[v] for k, v in desejadas.items() if v in mapa}

    log("Lendo o arquivo inteiro (so as colunas necessarias) ...")
    df = pd.read_csv(txt, sep=";", encoding=enc, dtype=str, usecols=list(usar.values()))
    df = df.rename(columns={v: k for k, v in usar.items()})
    log(f"Linhas: {len(df):,}")

    # 3) Resumo nacional
    df["saldo"] = pd.to_numeric(df["saldo"], errors="coerce")
    adm = int((df["saldo"] == 1).sum())
    desl = int((df["saldo"] == -1).sum())
    print("\n=== RESUMO BRASIL ===")
    if "competencia" in df:
        print(f"  Competencias no arquivo: {sorted(df['competencia'].dropna().unique())}")
    print(f"  Valores de saldo: {df['saldo'].value_counts(dropna=False).to_dict()}")
    print(f"  Admissoes: {adm:,} | Desligamentos: {desl:,} | Saldo: {adm - desl:,}")

    # 4) CBO
    if "cbo" in df:
        tamanhos = df["cbo"].str.len().value_counts().to_dict()
        print("\n=== CBO ===")
        print(f"  Ocupacoes distintas: {df['cbo'].nunique():,}")
        print(f"  Tamanho dos codigos (qtd de digitos -> linhas): {tamanhos}")
        print(f"  Exemplos: {df['cbo'].dropna().unique()[:10].tolist()}")

    # 5) Salario
    if "salario" in df:
        print("\n=== SALARIO ===")
        print(f"  Exemplos brutos: {df['salario'].dropna().unique()[:10].tolist()}")
        df["salario_num"] = pd.to_numeric(df["salario"].str.replace(",", ".", regex=False), errors="coerce")
        sal_adm = df.loc[df["saldo"] == 1, "salario_num"]
        print(f"  Admissoes sem salario valido: {int(sal_adm.isna().sum()):,}")
        print(f"  Admissoes com salario 0: {int((sal_adm == 0).sum()):,}")
        print("  Estatisticas do salario de admissao:")
        print(sal_adm.describe(percentiles=[0.01, 0.5, 0.99]).round(2).to_string())

    # 6) Top 10 ocupacoes por admissoes
    if "cbo" in df:
        adm_df = df[df["saldo"] == 1]
        top = adm_df.groupby("cbo").agg(
            admissoes=("saldo", "size"),
            salario_mediano=("salario_num", "median") if "salario_num" in df else ("saldo", "size"),
        ).sort_values("admissoes", ascending=False).head(10)
        saldo_cbo = df.groupby("cbo")["saldo"].sum()
        top["saldo"] = saldo_cbo.reindex(top.index)
        print("\n=== TOP 10 OCUPACOES POR ADMISSOES ===")
        print(top.to_string())

    log("Teste concluido.")


if __name__ == "__main__":
    main()
