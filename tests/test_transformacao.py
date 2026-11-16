"""
Testes das regras de negocio com dados pequenos e conhecidos.
Rodam no GitHub Actions antes do pipeline: se uma regra quebrar, nada e publicado.
"""

import pandas as pd
import pytest

from caged_pipeline import qualidade, transformacao as t

CABECALHO = "competênciamov;região;saldomovimentação;cbo2002ocupação;salário;unidadesaláriocódigo\n"


def arquivo(tmp_path, linhas):
    caminho = tmp_path / "CAGEDMOV.txt"
    caminho.write_text(CABECALHO + "\n".join(linhas) + "\n", encoding="utf-8")
    return str(caminho)


def test_le_colunas_com_acento_e_converte_tipos(tmp_path):
    df = t.ler_microdados(arquivo(tmp_path, ["202609;3;1;514320;1621,50;5"]))
    assert list(df.columns) == ["competencia", "saldo", "cbo", "salario", "unidade_salario"]
    assert df.loc[0, "salario"] == pytest.approx(1621.50)
    assert df.loc[0, "saldo"] == 1


def test_cbo_recupera_zero_a_esquerda(tmp_path):
    df = t.ler_microdados(arquivo(tmp_path, ["202609;3;1;10105;5000,00;5"]))
    assert df.loc[0, "cbo"] == "010105"


def test_coluna_faltando_da_erro(tmp_path):
    caminho = tmp_path / "ruim.txt"
    caminho.write_text("competênciamov;saldomovimentação\n202609;1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="colunas ausentes"):
        t.ler_microdados(str(caminho))


def test_exclusao_desfaz_movimentacao():
    mov = t.limpar(pd.DataFrame({"competencia": ["202609"] * 3, "saldo": ["1", "1", "-1"],
                                 "cbo": ["422105"] * 3, "salario": ["2000,00"] * 3,
                                 "unidade_salario": ["5"] * 3}))
    exc = mov.iloc[[0]]  # uma das admissoes foi cancelada
    total = pd.concat([t.contar_por_ocupacao(mov, 1),
                       t.contar_por_ocupacao(exc, -1)]).groupby(level=0).sum()
    assert total.loc["422105", "admissoes"] == 1
    assert total.loc["422105", "desligamentos"] == 1


def test_janela_descarta_meses_de_fora():
    df = pd.DataFrame({"competencia": ["202409", "202609"]})
    assert list(t.filtrar_janela(df, {"202609"})["competencia"]) == ["202609"]


def test_salario_so_admissoes_validas():
    df = t.limpar(pd.DataFrame({
        "competencia": ["202609"] * 5,
        "saldo":       ["1",     "1",    "1",     "-1",    "1"],
        "cbo":         ["1"] * 5,
        "salario":     ["2000,00", "0,00", "9,50", "3000,00", "2500,00"],
        "unidade_salario": ["5",  "5",    "6",     "5",     "1"],
    }))
    # entram: 2000 (mes) e 2500 (hora, ja convertido p/ mensal). Saem: zero, tarefa, desligamento.
    assert sorted(t.salarios_de_admissao(df)["salario"]) == [2000.0, 2500.0]


def test_consolidar_usa_mediana_e_junta_nome():
    contagens = [pd.DataFrame({"admissoes": [3], "desligamentos": [1]},
                              index=pd.Index(["422105"], name="cbo"))]
    salarios = [pd.DataFrame({"cbo": ["422105"] * 3, "salario": [1500.0, 1600.0, 27_841_398.0]})]
    dicionario = pd.DataFrame({"cbo_ocupacao": ["422105"], "nome_ocupacao": ["Recepcionista, em Geral"]})

    r = t.consolidar(contagens, salarios, dicionario).iloc[0]
    assert r["salario_mediano_admissao"] == 1600.0   # o outlier de R$ 27 mi nao pesa
    assert r["saldo"] == 2
    assert r["taxa_saldo"] == pytest.approx(0.6667)
    assert r["nome_ocupacao"] == "Recepcionista, em Geral"


def test_qualidade_barra_resumo_pequeno():
    resumo = pd.DataFrame({"cbo_ocupacao": ["422105"], "nome_ocupacao": ["x"],
                           "admissoes": [1], "desligamentos": [0], "n_salarios": [1]})
    with pytest.raises(qualidade.ErroQualidade, match="ocupacoes"):
        qualidade.validar(resumo)
