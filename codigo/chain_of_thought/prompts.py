from codigo.utils import (
    montar_questao_enem,
    montar_questao_gsm8k
)


def prompt_cot_enem(questao):
    return f"""
Você é um resolvedor de questões de matemática do ENEM.

Resolva a questão passo a passo.

Depois do raciocínio, escreva obrigatoriamente a resposta final neste formato:

Resposta final: X

em que X deve ser apenas uma alternativa: A, B, C, D ou E.

Questão:

{montar_questao_enem(questao)}
""".strip()


def prompt_cot_gsm8k(problema):
    return f"""
Você é um resolvedor de problemas matemáticos.

Resolva o problema passo a passo.

Depois do raciocínio, escreva obrigatoriamente a resposta final neste formato:

Resposta final: número

Problema:

{montar_questao_gsm8k(problema)}
""".strip()