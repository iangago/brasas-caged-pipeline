"""
EXTRACAO: baixa os microdados do Novo CAGED e o dicionario de ocupacoes do FTP do PDET.

Fonte: ftp://ftp.mtps.gov.br/pdet/microdados/NOVO CAGED/
  <AAAA>/<AAAAMM>/CAGEDMOV<AAAAMM>.7z  movimentacoes declaradas no prazo
  <AAAA>/<AAAAMM>/CAGEDFOR<AAAAMM>.7z  declaradas fora do prazo (referentes a meses anteriores)
  <AAAA>/<AAAAMM>/CAGEDEXC<AAAAMM>.7z  exclusoes (declaracoes canceladas)
  Layout Nao-identificado Novo Caged Movimentacao.xlsx  dicionario oficial dos codigos
"""

import ftplib
import glob
import io
import logging
import os
from datetime import date

import pandas as pd
import py7zr

log = logging.getLogger(__name__)

FTP_HOST = "ftp.mtps.gov.br"
BASE = "/pdet/microdados/NOVO CAGED"
LAYOUT = f"{BASE}/Layout Não-identificado Novo Caged Movimentação.xlsx"


class ErroExtracao(RuntimeError):
    pass


def conectar() -> ftplib.FTP:
    # Os nomes de arquivo do FTP estao em latin-1 (ex.: "Movimentação").
    ftp = ftplib.FTP(FTP_HOST, timeout=180, encoding="latin-1")
    ftp.login()  # FTP publico, acesso anonimo
    return ftp


def _mes_anterior(ano: int, mes: int) -> tuple[int, int]:
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def meses_disponiveis(ftp: ftplib.FTP, n_meses: int, hoje: date | None = None) -> list[str]:
    """
    Devolve as n_meses competencias mais recentes ja publicadas (AAAAMM, em ordem).
    O CAGED sai com 1 a 2 meses de atraso, entao volta mes a mes a partir de hoje.
    Um mes faltando NO MEIO da serie e erro: a soma de 12 meses ficaria errada.
    """
    hoje = hoje or date.today()
    ano, mes = hoje.year, hoje.month
    meses: list[str] = []
    for _ in range(n_meses + 6):
        ano, mes = _mes_anterior(ano, mes)
        comp = f"{ano}{mes:02d}"
        try:
            nomes = {n.split("/")[-1] for n in ftp.nlst(f"{BASE}/{ano}/{comp}")}
        except ftplib.error_perm:
            nomes = set()
        if f"CAGEDMOV{comp}.7z" in nomes:
            meses.append(comp)
            if len(meses) == n_meses:
                return sorted(meses)
        elif meses:
            raise ErroExtracao(f"{comp} sem arquivo MOV no meio da serie")
        else:
            log.info("%s: ainda nao publicado", comp)
    raise ErroExtracao(f"so encontrei {len(meses)} de {n_meses} meses")


def baixar_mes(ftp: ftplib.FTP, tipo: str, comp: str, pasta_tmp: str) -> str | None:
    """
    Baixa e descompacta CAGED<tipo><comp>.7z. Devolve o caminho do .txt,
    ou None se o arquivo nao existir (pode acontecer com FOR/EXC).
    """
    nome = f"CAGED{tipo}{comp}.7z"
    caminho_7z = os.path.join(pasta_tmp, nome)
    try:
        with open(caminho_7z, "wb") as f:
            ftp.retrbinary(f"RETR {BASE}/{comp[:4]}/{comp}/{nome}", f.write, blocksize=1 << 20)
    except ftplib.error_perm:
        os.remove(caminho_7z)
        return None

    destino = os.path.join(pasta_tmp, f"{tipo}{comp}")
    with py7zr.SevenZipFile(caminho_7z, mode="r") as z:
        z.extractall(path=destino)
    os.remove(caminho_7z)

    txts = glob.glob(f"{destino}/**/*.txt", recursive=True)
    if not txts:
        raise ErroExtracao(f"{nome} nao tem .txt dentro")
    return txts[0]


def baixar_dicionario_cbo(ftp: ftplib.FTP) -> pd.DataFrame:
    """Le a aba de ocupacoes (CBO 2002) do dicionario oficial: codigo -> nome."""
    buf = io.BytesIO()
    ftp.retrbinary(f"RETR {LAYOUT}", buf.write)
    cbo = pd.read_excel(buf, sheet_name="cbo2002ocupação", dtype=str)
    cbo.columns = ["cbo_ocupacao", "nome_ocupacao"]
    cbo["cbo_ocupacao"] = cbo["cbo_ocupacao"].str.strip().str.zfill(6)
    cbo["nome_ocupacao"] = cbo["nome_ocupacao"].str.strip()
    return cbo
