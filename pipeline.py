"""
Ponto de entrada do pipeline: python pipeline.py

Extrai 12 meses do Novo CAGED, resume por ocupacao, valida e grava:
  dados/caged_resumo.csv         uma linha por ocupacao (CBO)
  dados/relatorio_qualidade.md   o que foi processado e as checagens
"""

import logging
import os
import shutil
import time
from datetime import datetime, timezone

import pandas as pd

from caged_pipeline import extracao, qualidade, transformacao

N_MESES = 12
PASTA_TMP = "tmp_caged"
PASTA_SAIDA = "dados"
FONTE = "Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados nao identificados"

# EXC entra com sinal negativo: a exclusao desfaz um evento declarado antes.
ARQUIVOS = (("MOV", 1), ("FOR", 1), ("EXC", -1))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("pipeline")


def main() -> None:
    inicio = time.time()
    os.makedirs(PASTA_TMP, exist_ok=True)
    os.makedirs(PASTA_SAIDA, exist_ok=True)

    ftp = extracao.conectar()
    meses = extracao.meses_disponiveis(ftp, N_MESES)
    janela = set(meses)
    log.info("Janela: %s a %s", meses[0], meses[-1])

    dicionario = extracao.baixar_dicionario_cbo(ftp)
    log.info("Dicionario CBO: %d ocupacoes", len(dicionario))

    contagens, salarios, saldo_mensal = [], [], []
    for comp in meses:
        for tipo, sinal in ARQUIVOS:
            t0 = time.time()
            txt = extracao.baixar_mes(ftp, tipo, comp, PASTA_TMP)
            if txt is None:
                log.info("%s%s: nao publicado, seguindo", tipo, comp)
                continue
            df = transformacao.ler_microdados(txt)
            shutil.rmtree(os.path.dirname(txt), ignore_errors=True)

            df = transformacao.filtrar_janela(df, janela)
            contagens.append(transformacao.contar_por_ocupacao(df, sinal))
            if tipo != "EXC":
                # Simplificacao consciente: exclusoes nao saem da mediana de salario
                # (~0,1% das linhas; nao mexem numa mediana).
                salarios.append(transformacao.salarios_de_admissao(df))
            for c, sub in df.groupby("competencia"):
                saldo_mensal.append({"competencia": c, "arquivo": tipo,
                                     "saldo": int(sub["saldo"].sum()) * sinal})
            log.info("%s%s: %s linhas na janela (%.0fs)", tipo, comp, f"{len(df):,}", time.time() - t0)
    ftp.quit()

    resumo = transformacao.consolidar(contagens, salarios, dicionario)
    avisos = qualidade.validar(resumo)

    data = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resumo["periodo_inicio"] = meses[0]
    resumo["periodo_fim"] = meses[-1]
    resumo["recorte"] = "brasil"
    resumo["fonte"] = FONTE
    resumo["data_processamento"] = data
    resumo.to_csv(os.path.join(PASTA_SAIDA, "caged_resumo.csv"), index=False, encoding="utf-8")

    tabela = (pd.DataFrame(saldo_mensal)
              .pivot_table(index="competencia", columns="arquivo", values="saldo", aggfunc="sum")
              .reindex(columns=[a for a, _ in ARQUIVOS]).fillna(0).astype(int))
    tabela["total"] = tabela.sum(axis=1)
    with open(os.path.join(PASTA_SAIDA, "relatorio_qualidade.md"), "w", encoding="utf-8") as f:
        f.write(qualidade.relatorio(resumo, tabela, meses, avisos, data))

    shutil.rmtree(PASTA_TMP, ignore_errors=True)
    log.info("Pronto: %d ocupacoes em %.0f min", len(resumo), (time.time() - inicio) / 60)
    print(tabela.to_string())


if __name__ == "__main__":
    main()
