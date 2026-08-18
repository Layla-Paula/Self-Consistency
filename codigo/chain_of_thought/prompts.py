from codigo.utils import (
    montar_questao_enem,
    montar_questao_gsm8k,
)


# ============================================================
# PROMPT CHAIN-OF-THOUGHT - ENEM
# ============================================================

def prompt_cot_enem(questao):

    return f"""
Você é um resolvedor de questões de matemática do ENEM.

Resolva a questão cuidadosamente e apresente o raciocínio passo a passo.

Siga esta ordem:

1. Leia todo o enunciado antes de começar a resolver.

2. Identifique os dados relevantes apresentados na questão.

3. Identifique números, porcentagens, razões, proporções,
   medidas e unidades, por exemplo:
   m, m², m³, cm, km, litros, horas, minutos e porcentagens.

4. Verifique se a questão possui algum elemento visual, como:
   - gráfico;
   - tabela;
   - figura;
   - desenho;
   - diagrama;
   - mapa;
   - esquema.

5. Quando houver uma descrição visual, trate todas as informações
   presentes nela como parte essencial do enunciado.

6. Leia cuidadosamente todos os valores, textos, rótulos,
   legendas, eixos, medidas, escalas e relações apresentados
   na informação visual.

7. Não invente valores ou informações que não estejam presentes
   no enunciado ou na descrição visual.

8. Identifique qual conceito matemático é necessário para resolver
   o problema.

9. Desenvolva os cálculos passo a passo, mantendo atenção às
   unidades de medida.

10. Confira se o resultado encontrado faz sentido no contexto
    da questão.

11. Compare o resultado obtido com todas as alternativas
    A, B, C, D e E.

12. Escolha somente a alternativa que corresponde ao resultado.

Questão:

{montar_questao_enem(questao)}

Depois do raciocínio, escreva obrigatoriamente a resposta final
no seguinte formato:

Resposta final: X

em que X deve ser apenas uma letra:
A, B, C, D ou E.
""".strip()


# ============================================================
# PROMPT CHAIN-OF-THOUGHT - GSM8K
# ============================================================

def prompt_cot_gsm8k(problema):

    return f"""
Você é um resolvedor de problemas matemáticos.

Resolva o problema passo a passo.

Apresente o raciocínio utilizado para chegar ao resultado.

Depois do raciocínio, escreva obrigatoriamente a resposta
final neste formato:

Resposta final: número

Problema:

{montar_questao_gsm8k(problema)}
""".strip()