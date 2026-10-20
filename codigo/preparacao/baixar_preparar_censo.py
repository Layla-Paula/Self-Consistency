import argparse
import csv
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
# Endereço do pacote oficial
URL_CENSO = "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2025_.zip"
PASTA_CENSO = Path("dados/censo_escolar")
PASTA_ORIGINAL = PASTA_CENSO / "originais"
PASTA_EXTRAIDA = PASTA_ORIGINAL / "microdados_2025"
ARQUIVO_ZIP = PASTA_ORIGINAL / "microdados_censo_escolar_2025_.zip"
ARQUIVO_QUESTOES = PASTA_CENSO / "final" / "censo_escolar_2025.json"
# Documento padrão: permite executar o módulo sem informar --docx.
ARQUIVO_DOCX_PADRAO = PASTA_ORIGINAL / "Censo_Escolar_2025_50_Questoes.docx"
# Reconhece "1. Pergunta" e "Bloco 1 — Título" no DOCX.
PADRAO_QUESTAO = re.compile(r"^\s*(\d{1,2})\s*\.\s*(.+)$", re.S)
PADRAO_BLOCO = re.compile(r"^Bloco\s+(\d+)(?:\s*[—–-]\s*(.*))?$", re.I)
TOTAL_QUESTOES = 50
TOTAL_ESCOLAS_REFERENCIA = 178766

# Resoluções elaboradas para as demonstrações CoT, associadas aos números do DOCX.
# Não são respostas originais do professor; confira contra a mesma versão dos microdados.
RACIOCINIOS_CENSO = {1: '1. Abrir a Tabela_Matricula_2025_V2.csv. 2. Identificar CO_ENTIDADE como código da escola. 3. '
    'Contar os códigos distintos com COUNT(DISTINCT CO_ENTIDADE), evitando contar duas vezes a mesma '
    'escola. 4. A contagem resulta em 178.766 escolas.',
 2: '1. Identificar QT_MAT_BAS, quantidade de matrículas da Educação Básica por escola. 2. Converter os '
    'valores para inteiros e somar QT_MAT_BAS em todas as linhas, sem agrupar por escola ou região. 3. '
    'A soma é 46.018.380 matrículas; não confundir soma de matrículas com contagem de escolas.',
 3: '1. Consultar a definição de QT_MAT_BAS no Dicionário de Variáveis da Educação Básica, pois a '
    'exclusão de modalidades não pode ser deduzida apenas de somas do CSV. 2. Identificar as duas '
    'exclusões descritas: turmas exclusivas de atividade complementar e turmas exclusivas de '
    'Atendimento Educacional Especializado (AEE). 3. Informar ambas, sem subtrair valores da tabela.',
 4: '1. Localizar SG_UF (sigla) ou CO_UF (código da Unidade da Federação). 2. Obter valores distintos '
    'não vazios com COUNT(DISTINCT SG_UF). 3. A contagem é 27 UFs. 4. Interpretar corretamente: 26 '
    'estados e o Distrito Federal. 5. Listar as 27 UFs: AC, AL, AP, AM, BA, CE, DF, ES, GO, MA, MT, MS, MG, PA, PB, PR, PE, PI, RJ, RN, RS, RO, RR, SC, SP, SE e TO.',
 5: '1. Identificar CO_MUNICIPIO, código do município em que a escola está localizada. 2. Considerar '
    'todas as escolas registradas e contar os códigos municipais distintos, ignorando duplicatas. 3. '
    'COUNT(DISTINCT CO_MUNICIPIO) resulta em 5.571 municípios com pelo menos uma escola.',
 6: '1. Consultar a definição de NU_ANO_CENSO no dicionário: ano de referência do levantamento. 2. '
    'Obter os valores distintos dessa coluna no CSV. 3. Verificar que todas as linhas apresentam o '
    'único valor 2025. 4. Informar significado e valor, sem confundir com ano de fundação da escola.',
 7: '1. Ler QT_MAT_BAS como número em cada registro. 2. Filtrar os registros em que QT_MAT_BAS = 0 e '
    'contá-los. 3. O filtro retorna zero escolas. 4. Concluir apenas que nenhuma escola desta tabela '
    'apresenta zero matrículas nessa variável; a causa exata do recorte depende da documentação da '
    'base.',
 8: '1. Consultar as definições de TP_DEPENDENCIA e CO_REDE no dicionário. 2. TP_DEPENDENCIA distingue '
    'Federal (1), Estadual (2), Municipal (3) e Privada (4). 3. CO_REDE agrega as três primeiras na '
    'rede Pública (1) e a última na Privada (2). 4. Explicar que uma variável detalha a administração e '
    'a outra resume a rede.',
 9: '1. Usar CO_REDE para separar as escolas em Pública (código 1) e Privada (código 2). 2. Contar '
    'CO_ENTIDADE distinta em cada grupo. 3. Encontrar 137.020 escolas públicas e 41.746 privadas. 4. '
    'Conferir: 137.020 + 41.746 = 178.766 escolas.',
 10: '1. Agrupar os registros por TP_DEPENDENCIA: 1 Federal, 2 Estadual, 3 Municipal e 4 Privada. 2. '
     'Somar QT_MAT_BAS em cada grupo: 383.526; 13.330.302; 23.059.168; 9.245.384. 3. Conferir que a '
     'soma dos quatro grupos é 46.018.380. 4. Comparar os totais e identificar Municipal como maior, '
     'com cerca de 50,11% do total.',
 11: '1. Agrupar as escolas por TP_DEPENDENCIA e contar CO_ENTIDADE em cada grupo. 2. Comparar Federal '
     '716, Estadual 29.732, Municipal 106.572 e Privada 41.746 escolas. 3. Identificar Federal como '
     'menor quantidade. 4. Somar QT_MAT_BAS apenas no grupo Federal: 383.526 matrículas. 5. Relacionar '
     'o volume de matrículas ao porte médio das instituições, sem afirmar que todas são grandes.',
 12: '1. Agrupar por TP_DEPENDENCIA. 2. Para cada grupo, contar escolas distintas e somar QT_MAT_BAS. '
     '3. Dividir matrículas por escolas: Federal 383.526/716 ≈ 535,7; Estadual 13.330.302/29.732 ≈ '
     '448,3; Privada 9.245.384/41.746 ≈ 221,5; Municipal 23.059.168/106.572 ≈ 216,4. 4. Identificar a '
     'maior média, Federal, e explicar que a média sugere maior porte típico, sem provar o tamanho de '
     'cada escola.',
 13: '1. Filtrar TP_DEPENDENCIA = 3 (Municipal) e = 2 (Estadual). 2. Calcular média = '
     'SUM(QT_MAT_BAS)/COUNT(DISTINCT CO_ENTIDADE). 3. Municipal: 23.059.168/106.572 ≈ 216,4; Estadual: '
     '13.330.302/29.732 ≈ 448,3. 4. Comparar: a média estadual é aproximadamente 2,07 vezes a '
     'municipal. 5. Interpretar como indício de unidades municipais menores em média, sem inferir a '
     'distribuição individual apenas dessas médias.',
 14: '1. Consultar o dicionário de variáveis para identificar a classificação das escolas privadas. 2. '
     'Localizar TP_CATEGORIA_ESCOLA_PRIVADA no CSV. 3. Conferir os códigos: 1 Particular, 2 '
     'Comunitária, 3 Confessional, 4 Filantrópica. 4. Responder com o nome da variável e as quatro '
     'categorias; CO_REDE sozinho só separa pública de privada.',
 15: '1. Filtrar escolas privadas (TP_DEPENDENCIA = 4). 2. Agrupar por TP_CATEGORIA_ESCOLA_PRIVADA e '
     'somar QT_MAT_BAS. 3. Particular (1): 7.085.034; Filantrópica (4): 1.711.268; Comunitária (2): '
     '299.736; Confessional (3): 149.346. 4. Comparar Particular e Filantrópica: Particular é maior. 5. '
     'Calcular 7.085.034/9.245.384 × 100 ≈ 76,6% das matrículas privadas.',
 16: '1. Identificar IN_PODER_PUBLICO_PARCERIA como indicador de parceria com o poder público. 2. '
     'Consultar o dicionário para interpretar o valor 1 como presença de parceria/convênio. 3. Explicar '
     'que a parceria pode envolver financiamento do atendimento educacional ou oferta de itinerário '
     'técnico-profissional. 4. Não concluir que a escola é pública: parceria e dependência '
     'administrativa são características diferentes.',
 17: '1. Identificar TP_LOCALIZACAO no CSV: 1 Urbana, 2 Rural. 2. Agrupar os registros por esses '
     'códigos e contar CO_ENTIDADE distinta. 3. Encontrar 128.037 escolas urbanas e 50.729 rurais. 4. '
     'Conferir que a soma é 178.766.',
 18: '1. Agrupar por TP_LOCALIZACAO: 1 Urbana e 2 Rural. 2. Somar QT_MAT_BAS em cada grupo, sem contar '
     'somente escolas. 3. Obter 40.871.166 matrículas em escolas urbanas e 5.147.214 em escolas rurais. '
     '4. Conferir a soma de 46.018.380 matrículas.',
 19: '1. Agrupar por TP_LOCALIZACAO. 2. Contar escolas e somar QT_MAT_BAS: Urbana 128.037 escolas e '
     '40.871.166 matrículas; Rural 50.729 escolas e 5.147.214 matrículas. 3. Calcular médias: Urbana '
     '40.871.166/128.037 ≈ 319,2; Rural 5.147.214/50.729 ≈ 101,5. 4. Comparar: a média urbana supera a '
     'rural em mais de três vezes. 5. Interpretar como diferença de porte médio, não como medida do '
     'tamanho de cada escola.',
 20: '1. Agrupar as matrículas por NO_REGIAO e TP_LOCALIZACAO. 2. Para cada região, calcular 100 × '
     'SUM(QT_MAT_BAS das escolas rurais, TP_LOCALIZACAO=2) / SUM(QT_MAT_BAS de todas as escolas da '
     'região). 3. Obter Norte 24,42%; Nordeste 21,34%; Centro-Oeste 5,90%; Sul 5,77%; Sudeste 3,30%. 4. '
     'Comparar os cinco percentuais e identificar Norte como maior. 5. O denominador é o total '
     'regional, não o total nacional.',
 21: '1. Calcular para cada NO_REGIAO o percentual de matrículas em escolas rurais: 100 × matrículas '
     'com TP_LOCALIZACAO=2 / matrículas totais da região. 2. Comparar os cinco resultados; o Sudeste '
     'tem o menor, cerca de 3,30%. 3. Associar como hipótese à elevada urbanização e concentração '
     'metropolitana da região. 4. Ressaltar que o CSV descreve matrículas e não comprova sozinho a '
     'causa socioeconômica.',
 22: '1. Agrupar os registros por SG_UF. 2. Somar QT_MAT_BAS de todas as escolas em cada UF. 3. Ordenar '
     'os totais em ordem decrescente e selecionar as cinco primeiras: SP 9.600.318; MG 4.220.829; BA '
     '3.345.058; RJ 3.319.771; PR 2.438.428. 4. Informar os nomes correspondentes: São Paulo, Minas '
     'Gerais, Bahia, Rio de Janeiro e Paraná.',
 23: '1. Agrupar os registros por SG_UF e somar QT_MAT_BAS em cada UF. 2. Ordenar os 27 totais em ordem '
     'crescente. 3. Selecionar as cinco primeiras: RR 186.395; AP 212.026; AC 242.727; RO 376.264; TO '
     '380.768. 4. Informar Roraima, Amapá, Acre, Rondônia e Tocantins. 5. A posição no ranking resulta '
     'da soma, não do número de escolas.',
 24: '1. Agrupar as linhas pelo código CO_MUNICIPIO (e usar NO_MUNICIPIO e SG_UF para apresentar o '
     'nome). 2. Somar QT_MAT_BAS para cada município. 3. Ordenar em ordem decrescente. 4. Identificar '
     'São Paulo/SP com 2.512.355 matrículas; o segundo é Rio de Janeiro/RJ com 1.208.798. 5. Não '
     'confundir município com estado de São Paulo.',
 25: '1. Consultar o dicionário de TP_LOCALIZACAO_DIFERENCIADA: código 2 corresponde a Terra Indígena e '
     '3 a Comunidade Quilombola. 2. Filtrar cada código separadamente e somar QT_MAT_BAS. 3. Obter '
     'Terra Indígena 280.634 e Comunidade Quilombola 288.673. 4. Comparar os totais: Quilombola supera '
     'Indígena em 8.039 matrículas.',
 26: '1. Identificar as variáveis de grandes etapas QT_MAT_INF, QT_MAT_FUND, QT_MAT_MED, QT_MAT_PROF e '
     'QT_MAT_EJA. 2. Somar cada coluna em todas as escolas: Infantil 9.286.182; Fundamental 25.806.767; '
     'Médio 7.370.879; Profissional 3.187.976; EJA 2.252.069. 3. Comparar os cinco totais e identificar '
     'Ensino Fundamental como maior. 4. Não somar esses totais para obter o total geral sem verificar '
     'sobreposições de modalidades.',
 27: '1. Somar QT_MAT_INF_CRE em todas as escolas: 4.182.646 matrículas. 2. Somar QT_MAT_INF_PRE: '
     '5.103.536 matrículas. 3. Comparar e encontrar 920.890 matrículas a mais na Pré-Escola. 4. '
     'Relacionar a diferença à obrigatoriedade de matrícula a partir dos 4 anos, prevista na '
     'legislação; essa relação é contextual, não causalidade demonstrada pela tabela.',
 28: '1. Somar QT_MAT_FUND_AI (Anos Iniciais): 14.514.244. 2. Somar QT_MAT_FUND_AF (Anos Finais): '
     '11.292.523. 3. Subtrair: diferença de 3.221.721 matrículas. 4. Discutir possíveis fatores de '
     'fluxo escolar, como evasão, retenção e variação entre coortes, sem tratar a comparação '
     'transversal de 2025 como prova de abandono dos mesmos alunos.',
 29: '1. Somar separadamente QT_MAT_FUND_AI_1 a QT_MAT_FUND_AI_5 e QT_MAT_FUND_AF_6 a QT_MAT_FUND_AF_9. '
     '2. Obter, do 1º ao 9º ano: 2.890.337; 2.874.392; 2.850.775; 2.984.869; 2.913.871; 2.919.014; '
     '2.870.115; 2.840.218; 2.663.176. 3. Organizar em tabela com ano e matrículas. 4. Comparar as nove '
     'somas e identificar o 4º ano, com 2.984.869, como maior.',
 30: '1. Somar as variáveis QT_MAT_MED_1, QT_MAT_MED_2 e QT_MAT_MED_3, correspondentes às três séries. '
     '2. Encontrar 1ª 2.746.470; 2ª 2.438.380; 3ª 2.109.116. 3. Verificar a redução entre as séries. 4. '
     'Calcular (2.746.470 − 2.109.116)/2.746.470 × 100 ≈ 23,2%. 5. Apontar evasão ou retenção como '
     'hipóteses, não como causas comprovadas por um único retrato anual.',
 31: '1. Somar QT_MAT_PROF_TEC em todas as escolas: 2.490.145 matrículas técnicas. 2. Somar '
     'QT_MAT_PROF: 3.187.976 matrículas na Educação Profissional. 3. Calcular 100 × 2.490.145/3.187.976 '
     '≈ 78,1%. 4. Informar numerador, denominador e percentual.',
 32: '1. Somar QT_MAT_PROF_TEC_CONC: 348.446 matrículas em cursos técnicos concomitantes. 2. Somar '
     'QT_MAT_PROF_TEC_SUBS: 832.032 matrículas em cursos subsequentes. 3. Comparar: Subsequente é '
     'maior. 4. Consultar o dicionário: Concomitante ocorre durante o Ensino Médio; Subsequente ocorre '
     'após sua conclusão. 5. Não confundir as duas formas com curso técnico integrado.',
 33: '1. Somar QT_MAT_EJA: 2.252.069 matrículas. 2. Somar QT_MAT_BAS: 46.018.380 matrículas. 3. '
     'Calcular 100 × 2.252.069/46.018.380 ≈ 4,89%. 4. Informar o total de EJA e sua proporção no total '
     'geral.',
 34: '1. Somar QT_MAT_EJA_FUND: 1.406.442 matrículas. 2. Somar QT_MAT_EJA_MED: 845.627 matrículas. 3. '
     'Comparar os valores: EJA Fundamental é maior por 560.815 matrículas. 4. Interpretar a '
     'predominância como perfil da modalidade, sem inferir trajetórias individuais.',
 35: '1. Localizar QT_MAT_BAS_LIBRAS no CSV e somar seus valores: 3.637 matrículas. 2. Comparar com o '
     'total QT_MAT_BAS de 46.018.380, reconhecendo sua pequena participação. 3. Consultar o dicionário '
     'para delimitar o indicador às classes bilíngues de surdos. 4. Explicar que não equivale ao total '
     'de estudantes surdos nem a todos os estudantes com atendimento em Libras.',
 36: '1. Somar QT_MAT_BAS_FEM: 22.735.128. 2. Somar QT_MAT_BAS_MASC: 23.283.252. 3. Calcular razão '
     'Masculino/Feminino = 23.283.252/22.735.128 ≈ 1,0241. 4. Interpretar como aproximadamente 102,4 '
     'matrículas masculinas para cada 100 femininas.',
 37: '1. Somar QT_MAT_BAS_FEM (22.735.128), QT_MAT_BAS_MASC (23.283.252) e QT_MAT_BAS (46.018.380). 2. '
     'Calcular 100 × feminino/total ≈ 49,4% e 100 × masculino/total ≈ 50,6%. 3. Comparar os '
     'percentuais: diferença de aproximadamente 1,2 ponto percentual, pequena.',
 38: '1. Somar QT_MAT_BAS_PRETA = 2.301.626 e QT_MAT_BAS_PARDA = 20.847.435; juntos 23.149.061. 2. '
     'Calcular o total de cor/raça declarada subtraindo QT_MAT_BAS_ND do total: 46.018.380 − 6.275.577 '
     '= 39.742.803. 3. Dividir 23.149.061 por 39.742.803 e multiplicar por 100: aproximadamente 58,25%. '
     '4. Usar apenas declarados como denominador, conforme o enunciado.',
 39: '1. Somar as colunas de cor/raça declarada: QT_MAT_BAS_BRANCA, PRETA, PARDA, AMARELA e INDIGENA. '
     '2. Excluir QT_MAT_BAS_ND (não declarada) da comparação. 3. Comparar as somas: Amarela tem '
     '167.379, abaixo de Indígena (381.498) e dos demais grupos. 4. Identificar Amarela como menor '
     'grupo declarado.',
 40: '1. Somar QT_MAT_BAS_ND: 6.275.577 matrículas sem declaração de cor/raça. 2. Calcular 100 × '
     '6.275.577/46.018.380 ≈ 13,6%. 3. Explicar que a ausência de declaração pode afetar proporções e '
     'comparações entre grupos. 4. Não presumir que os não declarados se distribuem igualmente entre '
     'categorias.',
 41: '1. Somar QT_MAT_BAS_6_10: 14.111.254 matrículas. 2. Somar QT_MAT_BAS_11_14: 11.194.106. 3. '
     'Comparar: 6 a 10 anos apresenta maior total. 4. Relacionar, em termos de idade usual, 6–10 anos '
     'aos Anos Iniciais e 11–14 aos Anos Finais do Ensino Fundamental, admitindo distorção idade-série.',
 42: '1. Somar QT_MAT_BAS_18_MAIS: 3.974.803 matrículas. 2. Identificar no dicionário que a coluna '
     'corresponde a estudantes de 18 anos ou mais. 3. Associar esse contingente, como interpretação '
     'provável, à EJA, à Educação Profissional e a estudantes com distorção idade-série. 4. Não afirmar '
     'que a coluna isoladamente distribui esse total por modalidade.',
 43: '1. Somar QT_MAT_BAS_0_3: 3.874.541. 2. Somar QT_MAT_BAS_4_5: 4.968.651. 3. Comparar: a faixa 4–5 '
     'anos tem 1.094.110 matrículas a mais. 4. Relacionar o resultado à matrícula obrigatória na '
     'Pré-Escola a partir dos 4 anos, diferentemente da Creche; não atribuir toda a diferença apenas à '
     'legislação.',
 44: '1. Somar QT_MAT_BAS_D (Diurno): 42.131.013. 2. Somar QT_MAT_BAS_N (Noturno): 3.240.654. 3. Somar '
     'QT_MAT_BAS_EAD: 646.713. 4. Comparar os três totais: Diurno é muito maior. 5. Calcular '
     '42.131.013/46.018.380 × 100 ≈ 91,55% das matrículas.',
 45: '1. Somar QT_MAT_BAS_DM (Diurno Matutino): 24.171.117. 2. Somar QT_MAT_BAS_DV (Diurno Vespertino): '
     '17.959.896. 3. Comparar: Matutino é maior. 4. Conferir 24.171.117 + 17.959.896 = 42.131.013 '
     'matrículas diurnas. 5. Calcular 24.171.117/42.131.013 × 100 ≈ 57,4%.',
 46: '1. Somar QT_MAT_BAS_INT: 10.143.262 matrículas em tempo integral. 2. Somar QT_MAT_BAS: '
     '46.018.380. 3. Calcular 100 × 10.143.262/46.018.380 ≈ 22,04%. 4. Apresentar total e percentual, '
     'sem confundir tempo integral com turno diurno.',
 47: '1. Somar QT_MAT_ESP: 2.458.159 matrículas de Educação Especial. 2. Somar QT_MAT_BAS: 46.018.380. '
     '3. Calcular 100 × 2.458.159/46.018.380 ≈ 5,34%. 4. Informar o total e a participação percentual.',
 48: '1. Somar QT_MAT_ESP_CC (Classes Comuns): 2.298.005. 2. Somar QT_MAT_ESP_CE (Classes Exclusivas): '
     '160.154. 3. Conferir que ambas totalizam 2.458.159 matrículas de Educação Especial. 4. Calcular '
     '100 × 2.298.005/2.458.159 ≈ 93,48%. 5. Identificar Classes Comuns como predominantes e relacionar '
     'o resultado à política de inclusão, sem concluir que o indicador sozinho mede qualidade da '
     'inclusão.',
 49: '1. Somar QT_TRANSP_PUBLICO: 9.078.809 matrículas com transporte escolar público. 2. Somar '
     'QT_TRANSP_RESP_EST: 1.431.234 e QT_TRANSP_RESP_MUN: 7.647.575. 3. Conferir que as duas '
     'responsabilidades somam 9.078.809. 4. Comparar os totais: Municipal é maior. 5. Calcular 100 × '
     '7.647.575/9.078.809 ≈ 84,2%.',
 50: '1. Somar QT_MAT_ZR_URB: 38.397.441 matrículas de residentes urbanos. 2. Somar QT_MAT_ZR_RUR: '
     '7.618.155 de residentes rurais. 3. Separadamente, agrupar QT_MAT_BAS por TP_LOCALIZACAO da '
     'escola: Urbana 40.871.166; Rural 5.147.214. 4. Observar que residentes rurais são mais numerosos '
     'que matrículas em escolas rurais, o que é compatível com deslocamentos para escolas urbanas. 5. '
     'Ressaltar que totais marginais não identificam individualmente os trajetos nem provam quantos '
     'alunos rurais estudam em escolas urbanas; além disso, as duas somas de residência não cobrem '
     'exatamente o total geral, exigindo atenção a dados ausentes.'}

def salvar_json(caminho, dados):
    """Grava o JSON com segurança, substituindo o destino somente ao terminar."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    arquivo_temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".tmp",
            dir=caminho.parent, delete=False
        ) as arquivo:
            arquivo_temporario = Path(arquivo.name)
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo_temporario.replace(caminho)
    finally:
        if arquivo_temporario is not None:
            arquivo_temporario.unlink(missing_ok=True)
def baixar_zip(url):
    """Baixa o ZIP, reutilizando um arquivo válido já existente."""
    ARQUIVO_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if ARQUIVO_ZIP.is_file() and zipfile.is_zipfile(ARQUIVO_ZIP):
        print(f"ZIP já baixado: {ARQUIVO_ZIP}")
        return
    arquivo_parcial = ARQUIVO_ZIP.with_suffix(".zip.part")
    print("Baixando microdados oficiais do Inep...")
    try:
        pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(pedido, timeout=120) as resposta, arquivo_parcial.open("wb") as saida:
            shutil.copyfileobj(resposta, saida, length=1024 * 1024)
        if not zipfile.is_zipfile(arquivo_parcial):
            raise ValueError("O download não resultou em um ZIP válido.")
        arquivo_parcial.replace(ARQUIVO_ZIP)
    finally:
        arquivo_parcial.unlink(missing_ok=True)
def escolher_arquivos_do_zip(pacote):
    """Seleciona uma tabela de matrícula e os dicionários/arquivos explicativos."""
    arquivos = [arquivo for arquivo in pacote.infolist() if not arquivo.is_dir()]
    tabelas = [
        arquivo for arquivo in arquivos
        if Path(arquivo.filename).suffix.lower() == ".csv"
        and "matricula" in arquivo.filename.lower().replace("í", "i")
    ]
    if not tabelas:
        raise FileNotFoundError("Não encontrei um CSV de matrícula no ZIP. Confira a versão do pacote.")
    # Primeiro procura a versão exata do professor; depois, a maior tabela candidata.
    tabelas.sort(key=lambda arquivo: (
        Path(arquivo.filename).name.casefold() != "tabela_matricula_2025_v2.csv",
        -arquivo.file_size,
    ))
    tabela_escolhida = tabelas[0]
    auxiliares = [
        arquivo for arquivo in arquivos
        if arquivo != tabela_escolhida
        and any(palavra in arquivo.filename.casefold() for palavra in
                ("dicion", "layout", "leia-me", "leia_me", "instru", "nota_tecnica"))
        and Path(arquivo.filename).suffix.lower() in
        {".xlsx", ".xls", ".csv", ".pdf", ".txt", ".ods", ".docx"}
    ]
    return tabela_escolhida, auxiliares
def extrair_arquivos():
    """Extrai apenas os arquivos úteis; impede sobrescrever nomes repetidos no ZIP."""
    PASTA_EXTRAIDA.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARQUIVO_ZIP) as pacote:
        tabela, auxiliares = escolher_arquivos_do_zip(pacote)
        selecionados = [tabela, *auxiliares]
        nomes = [Path(arquivo.filename).name.casefold() for arquivo in selecionados]
        if len(nomes) != len(set(nomes)):
            raise ValueError("O ZIP possui arquivos selecionados com nomes repetidos. Extração interrompida.")
        for arquivo in selecionados:
            destino = PASTA_EXTRAIDA / Path(arquivo.filename).name
            # Não confia apenas no tamanho: extrai de novo para evitar arquivos antigos.
            arquivo_parcial = destino.with_name(destino.name + ".part")
            try:
                with pacote.open(arquivo) as origem, arquivo_parcial.open("wb") as saida:
                    shutil.copyfileobj(origem, saida, length=1024 * 1024)
                if arquivo_parcial.stat().st_size != arquivo.file_size:
                    raise ValueError(f"Extração incompleta: {destino.name}")
                arquivo_parcial.replace(destino)
            finally:
                arquivo_parcial.unlink(missing_ok=True)
            print(f"Extraído: {destino.name}")
    return PASTA_EXTRAIDA / Path(tabela.filename).name
def conferir_csv(caminho_csv):
    """Confere cabeçalho e número de registros sem carregar a tabela na memória."""
    codificacao = "utf-8-sig"
    try:
        with caminho_csv.open(encoding=codificacao) as arquivo:
            amostra = arquivo.read(8192)
    except UnicodeDecodeError:
        codificacao = "latin-1"
        with caminho_csv.open(encoding=codificacao) as arquivo:
            amostra = arquivo.read(8192)
    # O CSV do Inep costuma usar ponto e vírgula.
    delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
    with caminho_csv.open(encoding=codificacao, newline="") as arquivo:
        leitor = csv.reader(arquivo, delimiter=delimitador)
        colunas = next(leitor, [])
        total_registros = sum(1 for linha in leitor if linha)
    if "QT_MAT_BAS" not in colunas:
        raise ValueError("A tabela selecionada não possui a coluna QT_MAT_BAS.")
    print(f"Tabela: {caminho_csv.name}")
    print(f"Escolas/registros: {total_registros:,} | Colunas: {len(colunas)}")
    if caminho_csv.name.casefold() != "tabela_matricula_2025_v2.csv":
        print("AVISO: nome diferente da Tabela_Matricula_2025_V2.csv usada pelo professor.")
    if total_registros != TOTAL_ESCOLAS_REFERENCIA:
        print(f"AVISO: o professor utilizou {TOTAL_ESCOLAS_REFERENCIA:,} escolas. "
              "A equivalência da base não foi confirmada.")
    return total_registros
def ler_elementos_docx(documento):
    """Percorre parágrafos e tabelas na mesma ordem em que aparecem no Word."""
    for elemento in documento.element.body.iterchildren():
        if elemento.tag == qn("w:p"):
            yield "paragrafo", Paragraph(elemento, documento).text.strip()
        elif elemento.tag == qn("w:tbl"):
            tabela = Table(elemento, documento)
            linhas = []
            for linha in tabela.rows:
                celulas = [celula.text.strip().replace("\n", " / ") for celula in linha.cells]
                linhas.append(" | ".join(celulas))
            yield "tabela", "\n".join(linhas)
def converter_questoes_docx(caminho_docx):
    """Transforma as 50 perguntas e respostas em JSON, validando numeração e blocos."""
    if not caminho_docx.is_file():
        raise FileNotFoundError(f"DOCX não encontrado: {caminho_docx}")
    secao_atual = None
    bloco_atual = None
    numero_atual = None
    temas_dos_blocos = {}
    perguntas = {}
    respostas = {}
    for tipo, texto in ler_elementos_docx(Document(caminho_docx)):
        if not texto:
            continue
        if tipo == "paragrafo" and "PARTE I" in texto and "QUESTÕES" in texto:
            secao_atual, bloco_atual, numero_atual = "perguntas", None, None
            continue
        if tipo == "paragrafo" and "PARTE II" in texto and "RESPOSTAS" in texto:
            secao_atual, bloco_atual, numero_atual = "respostas", None, None
            continue
        if tipo == "paragrafo" and texto.casefold() == "fontes":
            break
        if secao_atual is None:
            continue
        bloco_encontrado = PADRAO_BLOCO.fullmatch(texto) if tipo == "paragrafo" else None
        if bloco_encontrado:
            bloco_atual = int(bloco_encontrado.group(1))
            if secao_atual == "perguntas":
                temas_dos_blocos[bloco_atual] = bloco_encontrado.group(2) or ""
            numero_atual = None
            continue
        numero_encontrado = PADRAO_QUESTAO.match(texto) if tipo == "paragrafo" else None
        itens = perguntas if secao_atual == "perguntas" else respostas
        if numero_encontrado:
            numero_atual = int(numero_encontrado.group(1))
            if numero_atual in itens:
                raise ValueError(f"Questão repetida em {secao_atual}: {numero_atual}")
            itens[numero_atual] = {
                "texto": numero_encontrado.group(2).strip(), "bloco": bloco_atual
            }
        elif numero_atual is not None:
            # Parágrafos de continuação e tabelas pertencem à questão anterior.
            separador = "\n" if tipo == "tabela" else " "
            itens[numero_atual]["texto"] += separador + texto
    numeros_esperados = set(range(1, TOTAL_QUESTOES + 1))
    if set(perguntas) != numeros_esperados or set(respostas) != numeros_esperados:
        raise ValueError("DOCX incompleto: não foram encontradas as 50 perguntas e respostas. "
                         f"Perguntas: {sorted(perguntas)}; respostas: {sorted(respostas)}")
    # Confere se cada raciocínio existe; os valores devem ser auditados nos microdados.
    # Os gabaritos permanecem exatamente como estão no documento do professor.
    if set(RACIOCINIOS_CENSO) != numeros_esperados or any(
        not isinstance(texto, str) or not texto.strip()
        for texto in RACIOCINIOS_CENSO.values()
    ):
        raise ValueError("Raciocínios do Censo incompletos: são necessárias as 50 resoluções.")

    questoes = []
    for numero in range(1, TOTAL_QUESTOES + 1):
        pergunta = perguntas[numero]
        resposta = respostas[numero]
        if pergunta["bloco"] is None or pergunta["bloco"] != resposta["bloco"]:
            raise ValueError(f"Bloco ausente ou divergente na questão {numero}")
        questoes.append({
            "id": f"censo_2025_{numero:02d}",
            "pergunta": pergunta["texto"],
            "resposta_esperada": resposta["texto"],
            "raciocinio": RACIOCINIOS_CENSO[numero],
        })
    return {
        "dataset_info": {
            "nome": "Censo Escolar 2025 — 50 questões do professor",
            "total": len(questoes),
        },
        "questoes": questoes,
    }
def executar():
    """Coordena download, extração, validação e conversão, preservando o ZIP."""
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument(
        "--docx",
        type=Path,
        default=ARQUIVO_DOCX_PADRAO,
        help="Caminho do DOCX com as 50 questões (opcional).",
    )
    argumentos.add_argument("--url", default=URL_CENSO, help="URL do ZIP oficial do Inep")
    argumentos.add_argument("--sem-download", action="store_true",
                            help="Usa ZIP já existente, sem baixar novamente")
    opcoes = argumentos.parse_args()
    # Verifica o documento antes de iniciar um download potencialmente grande.
    if not opcoes.docx.is_file():
        raise FileNotFoundError(f"DOCX não encontrado: {opcoes.docx}")
    if not opcoes.sem_download:
        baixar_zip(opcoes.url)
    if not ARQUIVO_ZIP.is_file() or not zipfile.is_zipfile(ARQUIVO_ZIP):
        raise FileNotFoundError(f"ZIP não encontrado ou inválido: {ARQUIVO_ZIP}")
    caminho_csv = extrair_arquivos()
    conferir_csv(caminho_csv)
    dados_questoes = converter_questoes_docx(opcoes.docx)
    salvar_json(ARQUIVO_QUESTOES, dados_questoes)
    print(f"50 questões salvas em: {ARQUIVO_QUESTOES}")
    # Mantém o ZIP original para reproduzir o experimento ou reextrair os dados.
    print(f"ZIP original preservado em: {ARQUIVO_ZIP}")
if __name__ == "__main__":
    executar()
