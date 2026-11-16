# Relatorio de qualidade - caged_resumo.csv

Gerado em 2026-11-16 pelo GitHub Actions.

- Janela: **202510 a 202609** (12 meses)
- Ocupacoes: **2,671**
- Admissoes: **26,655,386** | Desligamentos: **25,868,313** | Saldo: **+787,073**
- Salarios usados na mediana: **26,308,971**

## Saldo Brasil por mes (MOV + FOR - EXC)

Para conferir com o saldo divulgado pelo Ministerio do Trabalho. O ultimo mes fica levemente subestimado: as declaracoes fora do prazo dele ainda nao chegaram.

|   competencia |     MOV |    FOR |   EXC |   total |
|--------------:|--------:|-------:|------:|--------:|
|        202510 |   85147 |   7039 |   388 |   92574 |
|        202511 |   85864 |  -4324 |  -376 |   81164 |
|        202512 | -618164 | -18362 |   947 | -635579 |
|        202601 |  112334 |   4880 |   511 |  117725 |
|        202602 |  255321 |  12991 |  -397 |  267915 |
|        202603 |  228208 |      6 |  -478 |  227736 |
|        202604 |   85888 |  -6059 |  -563 |   79266 |
|        202605 |   72960 |   8630 |  -115 |   81475 |
|        202606 |  145161 |  -7837 |  -901 |  136423 |
|        202607 |   58568 |  -1827 |  -734 |   56007 |
|        202608 |  165827 |  -4115 |  -650 |  161062 |
|        202609 |  121305 |      0 |     0 |  121305 |

## Avisos

- 20,457 admissoes com CBO fora do dicionario
- 40 ocupacoes sem nenhum salario valido

## Top 10 ocupacoes por admissoes

|   cbo_ocupacao | nome_ocupacao                                            |   admissoes |   desligamentos |   saldo |   taxa_saldo |   salario_mediano_admissao |   n_salarios |   periodo_inicio |   periodo_fim | recorte   | fonte                                                                              | data_processamento   |
|---------------:|:---------------------------------------------------------|------------:|----------------:|--------:|-------------:|---------------------------:|-------------:|-----------------:|--------------:|:----------|:-----------------------------------------------------------------------------------|:---------------------|
|         514320 | Faxineiro (Desativado em 2010)                           |     1410809 |         1274662 |  136147 |       0.0965 |                    1736.68 |      1409304 |           202510 |        202609 | brasil    | Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados nao identificados | 2026-11-16           |
|         784205 | Alimentador de Linha de Producao                         |     1314232 |         1163159 |  151073 |       0.115  |                    2000.3  |      1313348 |           202510 |        202609 | brasil    | Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados nao identificados | 2026-11-16           |
|         521110 | Vendedor de Comercio Varejista                           |     1226377 |         1244447 |  -18070 |      -0.0147 |                    1800    |      1109957 |           202510 |        202609 | brasil    | Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados nao identificados | 2026-11-16           |
|         411005 | Auxiliar de Escritorio, em Geral                         |      865118 |          797133 |   67985 |       0.0786 |                    1733    |       863722 |           202510 |        202609 | brasil    | Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados nao identificados | 2026-11-16           |
|         717020 | Servente de Obras                                        |      843973 |          747384 |   96589 |       0.1144 |                    1800    |       843813 |           202510 |        202609 | brasil    | Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados nao identificados | 2026-11-16           |
|         411010 | Assistente Administrativo                                |      802843 |          757378 |   45465 |       0.0566 |                    2000    |       801011 |           202510 |        202609 | brasil    | Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados nao identificados | 2026-11-16           |
|         521140 | Atendente de Lojas e Mercados                            |      794383 |          719201 |   75182 |       0.0946 |                    1807.02 |       793425 |           202510 |        202609 | brasil    | Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados nao identificados | 2026-11-16           |
|         421125 | Operador de Caixa                                        |      778855 |          766327 |   12528 |       0.0161 |                    1815    |       777622 |           202510 |        202609 | brasil    | Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados nao identificados | 2026-11-16           |
|         414140 | Auxiliar de Logistica                                    |      710598 |          610052 |  100546 |       0.1415 |                    2025    |       713946 |           202510 |        202609 | brasil    | Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados nao identificados | 2026-11-16           |
|         782510 | Motorista de Caminhao (Rotas Regionais e Internacionais) |      596181 |          602385 |   -6204 |      -0.0104 |                    2769.22 |       582298 |           202510 |        202609 | brasil    | Novo CAGED - Ministerio do Trabalho e Emprego (PDET), microdados nao identificados | 2026-11-16           |
