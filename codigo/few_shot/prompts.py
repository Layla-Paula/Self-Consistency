from codigo.utils import (
    montar_questao_enem,
    montar_questao_gsm8k
)


EXEMPLOS_ENEM = """
Exemplo 1:

Questão:
Uma loja vende um produto por R$ 80,00. Em uma promoção, concede desconto de 25%.
Qual é o preço final?

A) R$ 20,00
B) R$ 40,00
C) R$ 55,00
D) R$ 60,00
E) R$ 75,00

Resposta: D

Exemplo 2:

Questão:
Um terreno retangular mede 10 m de largura e 15 m de comprimento.
Qual é sua área?

A) 25 m²
B) 50 m²
C) 100 m²
D) 150 m²
E) 300 m²

Resposta: D

Exemplo 3:

Questão:
Se 3 cadernos custam R$ 18,00, quanto custam 5 cadernos iguais?

A) R$ 24,00
B) R$ 25,00
C) R$ 28,00
D) R$ 30,00
E) R$ 36,00

Resposta: D
""".strip()


EXEMPLOS_GSM8K = """
Exemplo 1:

Problema:
João tinha 12 balas e ganhou mais 8. Quantas balas ele tem agora?

Resposta: 20

Exemplo 2:

Problema:
Maria comprou 3 caixas com 6 lápis em cada caixa. Quantos lápis ela comprou?

Resposta: 18

Exemplo 3:

Problema:
Um ônibus tinha 40 passageiros. Desceram 15. Quantos passageiros ficaram?

Resposta: 25
""".strip()


def prompt_few_shot_enem(questao):
    return f"""
Você é um resolvedor de questões de matemática.

Observe os exemplos:

{EXEMPLOS_ENEM}

Agora resolva a questão abaixo.

{montar_questao_enem(questao)}

Responda somente com a letra da alternativa correta.
Formato obrigatório:
Resposta: X
""".strip()


def prompt_few_shot_gsm8k(problema):
    return f"""
Você é um resolvedor de problemas matemáticos.

Observe os exemplos:

{EXEMPLOS_GSM8K}

Agora resolva o problema abaixo.

Problema:
{montar_questao_gsm8k(problema)}

Responda somente com o número final.
Formato obrigatório:
Resposta: número
""".strip()