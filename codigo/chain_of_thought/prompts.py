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
# rationale_pt só é utilizado em exemplos do train
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
    """CoT com demonstrações reais do train e problema atual de qualquer split."""
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
    """CoT objetivo para AQuA-RAT; compartilhado com Self-Consistency.

    O gabarito da questão avaliada nunca é enviado ao modelo.
    """
    if not exemplos:
        raise ValueError('CoT AQuA-RAT precisa de exemplos do train.')
    return f'''Você resolve questões matemáticas de múltipla escolha.
Observe as demonstrações resolvidas e use-as apenas como exemplos do método.

{_demonstracoes_aqua_rat(exemplos)}

Resolva a NOVA questão abaixo de modo objetivo.

REGRAS DE RESOLUÇÃO:
1. Identifique os dados relevantes e escolha UMA estratégia matemática adequada.
2. Mostre somente as operações necessárias, sem repetir cálculos já feitos.
3. Se uma tentativa não avançar, não recomece a mesma conta nem teste valores indefinidamente: use uma relação matemática mais direta ou verifique as alternativas.
4. Compare o resultado com as opções A, B, C, D e E e encerre com uma única alternativa.
5. Evite copiar o enunciado, listar hipóteses repetidas, abrir novas tentativas após obter um resultado ou continuar explicando depois da conclusão.
6. Se não conseguir resolver integralmente, escolha a alternativa mais sustentada pelos cálculos disponíveis; não invente operações ou valores.

Questão:
{montar_questao_aqua_rat(problema)}

Apresente a resolução de forma breve e finalize OBRIGATORIAMENTE com:
Resposta final: X

Substitua X por uma única letra de A a E. Não escreva nada após a resposta final.'''.strip()


# CENSO ESCOLAR — demonstrações reais selecionadas automaticamente do JSON.
# Cada demonstração inclui contexto do CSV, resolução passo a passo e resposta.
# A questão avaliada não aparece nas demonstrações e não recebe seu gabarito.
def prompt_cot_censo(questao, contexto, exemplos, contextos_exemplos, raciocinios_exemplos):
    if not exemplos:
        raise ValueError('CoT Censo precisa de demonstrações.')
    ids_exemplos = {str(e['id']) for e in exemplos}
    if str(questao['id']) in ids_exemplos:
        raise ValueError('Uma demonstração do Censo não pode ser avaliada.')
    blocos = []
    for indice, exemplo in enumerate(exemplos, 1):
        identificador = str(exemplo['id'])
        resposta = str(exemplo.get('resposta_esperada') or '').strip()
        raciocinio = str(raciocinios_exemplos.get(identificador) or '').strip()
        if not resposta or not raciocinio:
            raise ValueError(f'Demonstração incompleta: {identificador}')
        blocos.append(
            f'Exemplo {indice}:\n'
            f'{montar_questao_censo(exemplo, contextos_exemplos[identificador])}\n'
            f'Resolução passo a passo:\n{raciocinio}\n'
            f'Resposta final: {resposta}'
        )
    demonstracoes = '\n\n'.join(blocos)
    return f"""Você analisa os microdados do Censo Escolar 2025.
Observe os exemplos resolvidos passo a passo, com consultas reais ao CSV.
Não invente valores nem use respostas de referência de outras questões.

{demonstracoes}

Agora resolva uma NOVA questão, usando SOMENTE os dados apresentados para ela.
Explique as etapas relevantes e apresente o resultado solicitado.

{montar_questao_censo(questao, contexto)}

Termine com uma linha iniciada por:
Resposta final:""".strip()
