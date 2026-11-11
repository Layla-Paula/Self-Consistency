# Teste exploratório: juiz de consenso na SC do Censo

Arquivo: `self_consistency_censo_03112026_104526_347.json` · temperatura 0.7, 5 amostras, 1200 tokens

- Questões: 44; juiz chamado em 37 (respostas divergentes)
- Escolha do juiz diferente da votação em 19; pendentes de revisão: 1
- Acertos: votação 4 (9.1%), juiz 4 (após revisar pendentes%)

| Questão | Votação | Juiz | Votação acertou | Juiz acertou |
|---|---|---|---|---|
| censo_2025_01 | 178766 | A base tem 178.767 escolas de Educação Básica regi | sim | não |
| censo_2025_08 | A variável CO_REDE representa o código da rede de  | Dicionário: CO_REDE

A diferença conceitual entre  | não | não |
| censo_2025_09 | Escolas públicas: 1.234
Escolas privadas: 567 | A rede pública tem 137020 escolas e a rede privada | não | sim |
| censo_2025_10 | ... usando exclusivamente os resultados reais no h | O tipo de dependência que concentra o maior número | não | não |
| censo_2025_11 | A dependência administrativa com menor número de e | CO_ENTIDADE 'MUNICÍPIO' | não | não |
| censo_2025_16 | A escola com IN_PODER_PUBLICO_PARCERIA = 1 tem ape | 10077 escolas têm IN_PODER_PUBLICO_PARCERIA = 1. | não | não |
| censo_2025_17 | 0 escolas estão localizadas em área urbana e 0 em  | Quase todas as escolas estão localizadas em áreas  | não | não |
| censo_2025_20 | A região Sul apresenta o menor percentual de matrí | Não é possível calcular o percentual de matrículas | não | não |
| censo_2025_27 | A etapa de Educação Infantil com maior matrículas  | A educação infantil tem mais matrículas na Pré-Esc | sim | não |
| censo_2025_28 | A diferença entre o total de matrículas nos Anos I | O total de matrículas nos Anos Iniciais do Ensino  | não | não |
| censo_2025_32 | Os cursos técnicos concomitantes e subsequentes tê | SELECT 
  SUM(CASE WHEN TP_DEPENDENCIA = 'CURSO_TE | não | não |
| censo_2025_34 | A modalidade EJA concentra mais estudantes no Ensi | A modalidade EJA concentra mais estudantes no Ensi | não | não |
| censo_2025_35 | A variável QT_MAT_BAS_LIBRAS registra matrículas e | O total nacional de matrículas em classes bilíngue | não | sim |
| censo_2025_38 | 100 * (SUM(QT_MAT_BAS_PRETA) + SUM(QT_MAT_BAS_BRAN | SELECT ROUND(SUM(QT_MAT_BAS_BRANCA + QT_MAT_BAS_PR | não | PENDENTE |
| censo_2025_40 | Total de matrículas classificadas como "Não Declar | Esse dado é preocupante pois sugere que uma grande | não | não |
| censo_2025_43 | A faixa etária de 0 a 3 anos apresenta maior númer | As duas faixas etárias apresentam números de matrí | não | não |
| censo_2025_45 | O turno Vespertino tem mais matrículas do que o Di | Matutino (2.449.852) vs Vespertino (2.446.361). | não | não |
| censo_2025_48 | A quantidade de matrículas de Educação Especial em | A porcentagem de matrículas de Educação Especial e | não | sim |
| censo_2025_50 | Sim, é possível haver alunos residentes na zona ru | Para responder à pergunta, precisamos entender que | sim | não |

Exploratório: só altera a escolha entre respostas já geradas; não substitui a votação do método.
