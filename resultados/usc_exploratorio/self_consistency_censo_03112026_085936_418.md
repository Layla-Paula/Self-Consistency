# Teste exploratório: juiz de consenso na SC do Censo

Arquivo: `self_consistency_censo_03112026_085936_418.json` · temperatura 0.7, 5 amostras, 1200 tokens

- Questões: 44; juiz chamado em 37 (respostas divergentes)
- Escolha do juiz diferente da votação em 25; pendentes de revisão: 4
- Acertos: votação 3 (6.8%), juiz 4 (após revisar pendentes%)

| Questão | Votação | Juiz | Votação acertou | Juiz acertou |
|---|---|---|---|---|
| censo_2025_01 | 178766 | A Tabela de Matrícula 2025 contém 178.766 escolas  | sim | sim |
| censo_2025_02 | 46018380 | O total de matrículas da Educação Básica é de 46.0 | sim | sim |
| censo_2025_03 | MATRIZAS_TURMAS_TURBO: 5147214, MATRIZAS_TURMAS_RE | A variável QT_MAT_BAS não inclui matrículas em tur | não | não |
| censo_2025_05 | 5288 municípios distintos há pelo menos uma escola | Há 178466 municípios distintos com pelo menos uma  | não | não |
| censo_2025_07 | Existe uma escola registrada com QT_MAT_BAS igual  | Não foi encontrado nenhum tipo de entidade com núm | não | não |
| censo_2025_09 | A rede pública tem apenas 1 escola, enquanto a red | A rede pública tem 716 escolas e a rede privada te | não | não |
| censo_2025_10 | ... usando exclusivamente os resultados reais no h | TP_DEPENDENCIA | NUM_MATRICULAS
1 | 383.526
2 | 13 | não | não |
| censo_2025_13 | A média de matrículas por escola da rede Municipal | A rede Municipal tem uma média de matrículas por e | não | não |
| censo_2025_17 | num_escolas_urbanas: 50729
num_escolas_rurais: 507 | Ascolas_urbanas: 50729, escolas_rurais: 128037. | não | não |
| censo_2025_18 | Total de matrículas em escolas urbanas: 5147214
To | SELECT SUM(QT_MAT_BAS) AS total_escolas_urbanas, S | não | não |
| censo_2025_20 | A região Norte apresenta o maior percentual de mat | Os dados disponíveis não permitem determinar a per | não | não |
| censo_2025_23 | A base está dividida em 5 Estados (UF) com as segu | A lista das 5 unidades federativas com menor númer | não | sim |
| censo_2025_24 | A escola com o maior número de matrículas na Educa | São Paulo, com 1.153.116 matrículas na Educação Bá | não | não |
| censo_2025_25 | A Comunidade Quilombola concentra mais matrículas, | A escola de Terra Indígena concentra mais matrícul | não | não |
| censo_2025_26 | A grande etapa de ensino com maior número de matrí | A etapa de ensino que concentra o maior número de  | não | não |
| censo_2025_27 | Aqui estão as escolas que têm a mesma quantidade d | A etapa Creche tem mais matrículas do que a Pré-Es | não | não |
| censo_2025_28 | A diferença entre o total de matrículas nos Anos I | A diferença entre o total de matrículas nos Anos I | não | PENDENTE |
| censo_2025_29 | 2025, 46018380, 46018380
2020, 25314550, 25314550
 | A tabela das matrículas por ano/série é:

NU_ANO_C | não | não |
| censo_2025_31 | Total de matrículas na Educação Profissional Técni | SUM(QT_MAT_PROF_TEC) = 2.490.145
PORCENTAGEM = 6,2 | não | não |
| censo_2025_35 | O total nacional de matrículas em classes bilíngue | O total nacional de matrículas em classes bilíngue | não | sim |
| censo_2025_40 | 6275577 | A total de matrículas classificadas como "Não Decl | não | não |
| censo_2025_41 | As faixas etárias de 6 a 10 anos têm 5.147.214 mat | A faixa de 6 a 10 anos geralmente corresponde à 1ª | não | PENDENTE |
| censo_2025_42 | O total de matrículas na faixa etária de 18 anos o | O total de matrículas de estudantes com idade 18 a | não | não |
| censo_2025_43 | A faixa etária de 0 a 3 anos apresenta o menor núm | A faixa etária de 4 a 5 anos apresenta o maior núm | não | PENDENTE |
| censo_2025_50 | {"colunas": ["matrículas_urbanas", "matrículas_rur | Para responder à pergunta, podemos analisar os dad | sim | PENDENTE |

Exploratório: só altera a escolha entre respostas já geradas; não substitui a votação do método.
