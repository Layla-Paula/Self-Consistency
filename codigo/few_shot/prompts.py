"""Prompts Few-shot: exemplos REAIS lidos do JSON em tempo de execução.

"""
from codigo.utils import montar_questao_gsm8k, montar_questao_aqua_rat, montar_questao_censo, extrair_gabarito_gsm8k, extrair_gabarito_aqua_rat

# Few-shot clássico: demonstrar entrada e saída, SEM mostrar raciocínio detalhado.



def _demonstracoes_gsm8k(exemplos):
    blocos = []
    for i, exemplo in enumerate(exemplos, 1):
        blocos.append(f"Exemplo {i}:\nProblema:\n{montar_questao_gsm8k(exemplo)}\nResposta: {extrair_gabarito_gsm8k(exemplo)}")
    return '\n\n'.join(blocos)


def _demonstracoes_aqua_rat(exemplos):
    blocos = []
    for i, exemplo in enumerate(exemplos, 1):
        blocos.append(f"Exemplo {i}:\nQuestão:\n{montar_questao_aqua_rat(exemplo)}\nResposta: {extrair_gabarito_aqua_rat(exemplo)}")
    return '\n\n'.join(blocos)


def prompt_few_shot_gsm8k(problema, exemplos):
    """Os 10 exemplos vêm do train; a questão atual vem do test."""
    if not exemplos:
        raise ValueError('Few-shot GSM8K precisa de exemplos do train.')
    return f'''Você resolve problemas matemáticos. Observe os exemplos de problemas e respostas:

{_demonstracoes_gsm8k(exemplos)}

Agora resolva este NOVO problema sem consultar respostas de referência:
Problema:
{montar_questao_gsm8k(problema)}

Responda somente no formato: Resposta: número'''.strip()


def prompt_few_shot_aqua_rat(problema, exemplos):
    """Não envia rationale_pt nem correct da questão atual ao modelo."""
    if not exemplos:
        raise ValueError('Few-shot AQuA-RAT precisa de exemplos do train.')
    return f'''Você resolve questões matemáticas de múltipla escolha. Observe exemplos reais de questões e suas respostas:

{_demonstracoes_aqua_rat(exemplos)}

Agora resolva esta NOVA questão:
{montar_questao_aqua_rat(problema)}

Escolha a alternativa correta considerando apenas o enunciado e as cinco opções.
Responda exclusivamente no formato: Resposta: X
Substitua X por uma única letra entre A e E.'''.strip()


# CENSO: as demonstrações contêm dados calculados do CSV e respostas do train
# sorteado; a questão avaliada recebe somente sua própria evidência e pergunta.
def prompt_few_shot_censo(questao, contexto, exemplos, contextos):
    if not exemplos:
        raise ValueError('Few-shot Censo precisa de demonstrações.')
    blocos = []
    for i, exemplo in enumerate(exemplos, 1):
        resposta = str(exemplo.get('resposta_esperada') or '').strip()
        if not resposta:
            raise ValueError(f'Exemplo do Censo sem gabarito: {exemplo["id"]}')
        blocos.append(
            f'Exemplo {i}:\n'
            f'{montar_questao_censo(exemplo, contextos[exemplo["id"]])}\n'
            f'Resposta: {resposta}'
        )
    demonstracoes = '\n\n'.join(blocos)
    return f'''Você analisa dados do Censo Escolar 2025. Observe as demonstrações com consultas reais ao CSV. Não invente valores.

{demonstracoes}

Agora responda uma nova questão usando SOMENTE os dados apresentados para ela:
{montar_questao_censo(questao, contexto)}

Resposta:'''.strip()