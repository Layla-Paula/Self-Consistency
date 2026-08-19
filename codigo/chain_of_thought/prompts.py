from codigo.utils import (
    montar_questao_enem,
    montar_questao_gsm8k,
)



# PROMPT CHAIN-OF-THOUGHT - ENEM

def prompt_cot_enem(questao):

    return f"""
Você é um resolvedor de questões de matemática do ENEM.

Resolva a questão cuidadosamente.

Antes de escolher a alternativa correta, siga estas regras:

1. Leia todo o enunciado da questão antes de responder.

2. Identifique todos os números, medidas, porcentagens,
   expressões matemáticas e unidades apresentadas.

3. Preste atenção especial às unidades de medida, por exemplo:
   m, m², m³, cm, km, litros, porcentagem, horas e minutos.

4. Verifique se a questão possui algum elemento visual,
   como:
   - gráfico;
   - tabela;
   - figura;
   - desenho;
   - diagrama;
   - mapa;
   - esquema.

5. Quando houver informação visual ou descrição visual,
   considere TODO o seu conteúdo como parte da questão.

6. Leia cuidadosamente todos os valores, textos, rótulos,
   legendas, eixos, medidas e relações apresentados
   na descrição visual.

7. Não ignore informações provenientes de gráficos,
   tabelas ou figuras.

8. Compare o resultado obtido com TODAS as alternativas
   A, B, C, D e E antes de escolher a resposta.

9. Não invente valores que não estejam presentes
   no enunciado ou na informação visual.

10. Se uma informação necessária não estiver disponível,
    não suponha um valor arbitrário.

Questão:

{montar_questao_enem(questao)}

Resolva a questão apresentando o raciocínio passo a passo.

Depois do raciocínio, escreva obrigatoriamente a resposta final
no seguinte formato:

Resposta final: X

onde X deve ser apenas uma letra:
A, B, C, D ou E.
""".strip()



# PROMPT CHAIN-OF-THOUGHT - GSM8K

def prompt_cot_gsm8k(problema):

    return f"""
Você é um resolvedor de problemas matemáticos.

Resolva o problema abaixo passo a passo.

Problema:

{montar_questao_gsm8k(problema)}

Apresente o raciocínio utilizado para chegar ao resultado.

Depois do raciocínio, escreva obrigatoriamente a resposta
final neste formato:

Resposta final: número
""".strip()