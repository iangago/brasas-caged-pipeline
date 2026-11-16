"""
QUALIDADE: checagens que fazem o pipeline FALHAR em vez de publicar dado errado,
e um relatorio em Markdown salvo junto com o CSV a cada rodada.
"""

import pandas as pd


class ErroQualidade(AssertionError):
    pass


def validar(resumo: pd.DataFrame) -> list[str]:
    """Levanta ErroQualidade se algo estiver claramente errado. Devolve avisos."""
    erros, avisos = [], []

    if len(resumo) < 2000:
        erros.append(f"so {len(resumo)} ocupacoes (esperado > 2.000)")
    if not resumo["cbo_ocupacao"].str.fullmatch(r"\d{6}").all():
        erros.append("ha codigos CBO fora do padrao de 6 digitos")
    if (resumo["admissoes"] < 0).any() or (resumo["desligamentos"] < 0).any():
        erros.append("contagem negativa: exclusoes maiores que as movimentacoes")
    if resumo["cbo_ocupacao"].duplicated().any():
        erros.append("CBO duplicado no resumo")

    adm_total = resumo["admissoes"].sum()
    adm_sem_nome = resumo.loc[resumo["nome_ocupacao"].isna(), "admissoes"].sum()
    if adm_sem_nome / adm_total > 0.01:
        erros.append(f"{adm_sem_nome / adm_total:.1%} das admissoes sem nome de ocupacao")
    elif adm_sem_nome:
        avisos.append(f"{adm_sem_nome:,} admissoes com CBO fora do dicionario")

    sem_salario = (resumo["n_salarios"] == 0).sum()
    if sem_salario:
        avisos.append(f"{sem_salario} ocupacoes sem nenhum salario valido")

    if erros:
        raise ErroQualidade("; ".join(erros))
    return avisos


def relatorio(resumo: pd.DataFrame, saldo_mensal: pd.DataFrame,
              meses: list[str], avisos: list[str], data: str) -> str:
    """Relatorio legivel do que foi processado, para conferir com os numeros oficiais."""
    linhas = [
        "# Relatorio de qualidade - caged_resumo.csv",
        "",
        f"Gerado em {data} pelo GitHub Actions.",
        "",
        f"- Janela: **{meses[0]} a {meses[-1]}** ({len(meses)} meses)",
        f"- Ocupacoes: **{len(resumo):,}**",
        f"- Admissoes: **{resumo['admissoes'].sum():,}** | "
        f"Desligamentos: **{resumo['desligamentos'].sum():,}** | "
        f"Saldo: **{resumo['saldo'].sum():+,}**",
        f"- Salarios usados na mediana: **{resumo['n_salarios'].sum():,}**",
        "",
        "## Saldo Brasil por mes (MOV + FOR - EXC)",
        "",
        "Para conferir com o saldo divulgado pelo Ministerio do Trabalho. "
        "O ultimo mes fica levemente subestimado: as declaracoes fora do prazo dele ainda nao chegaram.",
        "",
        saldo_mensal.to_markdown(),
        "",
        "## Avisos",
        "",
        *([f"- {a}" for a in avisos] or ["- Nenhum"]),
        "",
        "## Top 10 ocupacoes por admissoes",
        "",
        resumo.head(10).to_markdown(index=False),
        "",
    ]
    return "\n".join(linhas)
