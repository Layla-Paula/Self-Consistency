"""Prompts Chain-of-Thought para GSM8K, AQuA-RAT e Censo Escolar.

"""
import re

from codigo.utils import (
    montar_questao_gsm8k, montar_questao_aqua_rat, montar_questao_censo,
    extrair_gabarito_gsm8k, extrair_gabarito_aqua_rat,
)


# DEMONSTRAÇÕES DE RACIOCÍNIO — GSM8K
# Usa a resolução de referência APENAS dos exemplos selecionados do train.
# Os marcadores <<...>> são anotações do GSM8K, não parte do raciocínio textual.
def _demonstracoes_gsm8k(exemplos):
    blocos = []
    for indice, exemplo in enumerate(exemplos, 1):
        resolucao = str(exemplo.get('answer_pt') or exemplo.get('answer_en') or exemplo.get('answer') or '')
        resolucao = re.sub(r'<<[^>]*>>', '', resolucao)
        resolucao = re.sub(r'\s*####\s*[-\d.,]+\s*$', '', resolucao).strip()
        if not resolucao:
            raise ValueError(f'Exemplo GSM8K sem resolução: {exemplo.get("id")}')
        blocos.append(
            f'Exemplo {indice}:\nProblema:\n{montar_questao_gsm8k(exemplo)}\n'
            f'Resolução:\n{resolucao}\nResposta final: {extrair_gabarito_gsm8k(exemplo)}'
        )
    return '\n\n'.join(blocos)


# DEMONSTRAÇÕES DE RACIOCÍNIO — AQUA-RAT
# rationale_pt só é utilizado em exemplos do train; nunca na questão do test.
def _demonstracoes_aqua_rat(exemplos):
    blocos = []
    for indice, exemplo in enumerate(exemplos, 1):
        justificativa = str(exemplo.get('rationale_pt') or '').strip()
        if not justificativa:
            raise ValueError(f'Exemplo AQuA-RAT sem rationale_pt: {exemplo.get("id")}')
        blocos.append(
            f'Exemplo {indice}:\nQuestão:\n{montar_questao_aqua_rat(exemplo)}\n'
            f'Resolução:\n{justificativa}\nResposta final: {extrair_gabarito_aqua_rat(exemplo)}'
        )
    return '\n\n'.join(blocos)


def prompt_cot_gsm8k(problema, exemplos):
    """CoT com demonstrações reais do train e problema atual do test."""
    if not exemplos:
        raise ValueError('CoT GSM8K precisa de exemplos do train.')
    return f'''Você resolve problemas matemáticos. Observe os exemplos com resoluções intermediárias.

{_demonstracoes_gsm8k(exemplos)}

Agora resolva um NOVO problema. Explique os cálculos necessários, verifique as unidades e apresente o resultado.

Problema:
{montar_questao_gsm8k(problema)}

Termine obrigatoriamente com uma linha no formato:
Resposta final: número'''.strip()


def prompt_cot_aqua_rat(problema, exemplos):
    """CoT com rationale_pt dos exemplos; não acessa o gabarito da questão atual."""
    if not exemplos:
        raise ValueError('CoT AQuA-RAT precisa de exemplos do train.')
    return f'''Você resolve questões matemáticas de múltipla escolha. Observe exemplos com resoluções.

{_demonstracoes_aqua_rat(exemplos)}

Agora resolva uma NOVA questão. Mostre os cálculos relevantes e confira as cinco alternativas.

Questão:
{montar_questao_aqua_rat(problema)}

Termine obrigatoriamente com uma linha no formato:
Resposta final: X
Onde X é uma única letra de A a E.'''.strip()


# CENSO ESCOLAR — dez demonstrações fixas e explicadas manualmente.
# Os números abaixo são os valores de referência do JSON do professor.
# As operações/contagens precisam ser conferidas contra o CSV real.
# NÃO são usados os gabaritos das questões de avaliação (11 a 50).
RESOLUCOES_CENSO = {
    'censo_2025_01': """1. Abrir a Tabela de Matrícula de 2025.
2. Identificar a coluna que representa cada escola (CO_ENTIDADE, se presente).
3. Contar as escolas distintas: COUNT(DISTINCT CO_ENTIDADE). Se houver exatamente uma linha por escola, COUNT(*) produz o mesmo resultado.
4. Conferir a ausência de duplicações e comparar a contagem com o total de referência: 178.766 escolas.
5. Responder com a unidade 'escolas'.""",
    'censo_2025_02': """1. Localizar a coluna numérica QT_MAT_BAS, que informa matrículas da Educação Básica por escola.
2. Converter os valores para números e verificar valores ausentes antes de somar.
3. Calcular SUM(QT_MAT_BAS) sobre todas as escolas, sem agrupar por UF ou dependência.
4. Total de referência: 46.018.380 matrículas.
5. Não contar linhas: cada linha pode representar uma escola com muitas matrículas.""",
    'censo_2025_03': """1. Esta é uma questão conceitual: consultar o dicionário de dados, não deduzir apenas pelos totais do CSV.
2. Localizar a definição de QT_MAT_BAS e identificar explicitamente as exclusões.
3. A definição de referência exclui turmas exclusivas de atividade complementar e turmas exclusivas de Atendimento Educacional Especializado (AEE).
4. Não subtrair matrículas sem evidência: a pergunta pede os tipos de turma excluídos, não uma quantidade.""",
    'censo_2025_04': """1. Identificar o campo de UF (por exemplo, CO_UF, conforme o cabeçalho real).
2. Selecionar valores únicos não nulos: SELECT DISTINCT CO_UF.
3. Contar os códigos distintos: COUNT(DISTINCT CO_UF) = 27, conforme a referência.
4. Interpretar: são 26 estados e o Distrito Federal; o DF é uma Unidade da Federação, não um estado.
5. Para listar nomes individuais, relacionar códigos ao dicionário oficial de UFs; não inventar nomes a partir dos códigos.""",
    'censo_2025_05': """1. Identificar o código de município (CO_MUNICIPIO, conforme o cabeçalho).
2. Selecionar apenas registros de escolas existentes na Tabela de Matrícula.
3. Contar códigos distintos, e não escolas: COUNT(DISTINCT CO_MUNICIPIO).
4. Resultado de referência: 5.571 municípios distintos.
5. Um município com várias escolas entra apenas uma vez na contagem.""",
    'censo_2025_06': """1. Consultar no dicionário o significado de NU_ANO_CENSO: ano de referência do Censo Escolar.
2. Ler os valores distintos dessa coluna: SELECT DISTINCT NU_ANO_CENSO.
3. Verificar se o único valor observado é 2025, como indica a referência.
4. Conferir se há valores ausentes ou diferentes antes de afirmar que todas as linhas possuem o mesmo ano.
5. Explicar o significado e informar o valor único: 2025.""",
    'censo_2025_07': """1. Localizar QT_MAT_BAS e conferir que foi lido como número.
2. Aplicar filtro QT_MAT_BAS = 0.
3. Contar as linhas filtradas: COUNT(*) = 0, segundo a referência.
4. Interpretar com cautela: na Tabela de Matrícula analisada não aparecem escolas com zero matrículas de Educação Básica.
5. Essa observação não prova, isoladamente, a regra de seleção da base; consultar a documentação antes de afirmar o motivo da ausência.""",
    'censo_2025_08': """1. Consultar no dicionário as definições de TP_DEPENDENCIA e CO_REDE.
2. TP_DEPENDENCIA distingue quatro dependências administrativas: Federal, Estadual, Municipal e Privada.
3. CO_REDE reúne essas dependências em duas redes: Pública (Federal + Estadual + Municipal) e Privada.
4. Explicar que CO_REDE é um agrupamento derivado, enquanto TP_DEPENDENCIA mantém o detalhamento administrativo.
5. Esta é uma comparação conceitual; não é necessário calcular totais para responder.""",
    'censo_2025_09': """1. Identificar CO_REDE e conferir no dicionário os códigos de Pública e Privada.
2. Agrupar escolas por rede e contar escolas distintas em cada grupo: GROUP BY CO_REDE e COUNT(DISTINCT CO_ENTIDADE).
3. Valores de referência: Pública = 137.020; Privada = 41.746 escolas.
4. Conferir a soma: 137.020 + 41.746 = 178.766 escolas, consistente com o total da questão 1.
5. Não confundir quantidade de escolas com quantidade de matrículas.""",
    'censo_2025_10': """1. Identificar TP_DEPENDENCIA, QT_MAT_BAS e os códigos de cada dependência no dicionário.
2. Agrupar por dependência administrativa e calcular SUM(QT_MAT_BAS) para cada categoria.
3. Totais de referência: Federal = 383.526; Estadual = 13.330.302; Municipal = 23.059.168; Privada = 9.245.384.
4. Conferir a soma: 383.526 + 13.330.302 + 23.059.168 + 9.245.384 = 46.018.380 matrículas.
5. Comparar os quatro resultados: Municipal (23.059.168) é o maior.
6. Proporção municipal: 23.059.168 / 46.018.380 × 100 ≈ 50,11%, portanto pouco mais da metade.""",
}


def prompt_cot_censo(questao, contexto, exemplos, contextos_exemplos):
    """Dez demonstrações fixas com procedimentos e cálculos manuais."""
    ids_esperados = [f'censo_2025_{i:02d}' for i in range(1, 11)]
    if [e.get('id') for e in exemplos] != ids_esperados:
        raise ValueError('CoT Censo exige exatamente as questões 01 a 10, nessa ordem.')
    if questao.get('id') in ids_esperados:
        raise ValueError('Uma demonstração do Censo não pode ser avaliada.')
    blocos = []
    for indice, exemplo in enumerate(exemplos, 1):
        identificador = exemplo['id']
        contexto_exemplo = contextos_exemplos[identificador]
        resposta = str(exemplo['resposta_esperada']).strip()
        blocos.append(
            f'Exemplo {indice}:\n'
            f'{montar_questao_censo(exemplo, contexto_exemplo)}\n'
            f'Procedimento detalhado e cálculos:\n{RESOLUCOES_CENSO[identificador]}\n'
            f'Resposta final: {resposta}'
        )
    demonstracoes = '\n\n'.join(blocos)
    return f"""Você analisa os microdados do Censo Escolar 2025.
Observe as dez demonstrações, que explicam as variáveis, filtros, operações e interpretação.
Os totais mostrados são valores de referência das demonstrações; a evidência
consultada no CSV deve ser conferida antes de tratá-los como resultados verificados.

{demonstracoes}

Agora resolva uma NOVA questão. Use SOMENTE os dados consultados para ela.
Explique passo a passo quais variáveis foram usadas, filtros, contagens, somas,
percentuais ou comparações aplicáveis. Não invente números nem utilize respostas
ou gabaritos de outras questões como substitutos para a consulta.
Se os dados forem insuficientes, indique claramente o que falta.

{montar_questao_censo(questao, contexto)}

Termine com uma linha iniciada por:
Resposta final:""".strip()