from codigo.utils import (
    montar_questao_enem,
    montar_questao_gsm8k
)


EXEMPLOS_ENEM = """
Exemplo 1:

Questão:
Uma loja vende um produto por R$ 80,00. Em uma promoção, concede desconto de 25%.
Qual é o preço final?

A) R$ 60,00
B) R$ 40,00
C) R$ 55,00
D) R$ 20,00
E) R$ 75,00

Resposta: A


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
D) R$ 36,00
E) R$ 30,00

Resposta: E

Exemplo 4 — Gráfico

Questão:
O gráfico apresenta a quantidade de estudantes
matriculados em três cursos de uma escola.

Descrição visual:
Há um gráfico de barras com três categorias.

Matemática: 40 estudantes.
Física: 30 estudantes.
Química: 50 estudantes.

Quantos estudantes estão matriculados,
ao todo, nos três cursos?

A) 80
B) 120
C) 110
D) 100
E) 130

Resposta: B


Exemplo 5 — Tabela

Questão:
Uma empresa registrou em uma tabela
a quantidade de produtos vendidos durante
três meses.

Descrição visual:
A tabela possui os seguintes valores:

Janeiro: 120 produtos.
Fevereiro: 150 produtos.
Março: 130 produtos.

Qual foi a quantidade total de produtos vendidos
nos três meses?

A) 300
B) 350
C) 400
D) 380
E) 420

Resposta: C


Exemplo 6 — Figura geométrica

Questão:
A figura representa um piso retangular.

Descrição visual:
A figura mostra um retângulo com:

comprimento = 8 m
largura = 6 m

Qual é a área do piso representado na figura?

A) 14 m²
B) 28 m²
C) 40 m²
D) 48 m²
E) 56 m²

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
Você é um resolvedor de questões de matemática do ENEM.

Observe atentamente os exemplos apresentados abaixo.

{EXEMPLOS_ENEM}


Agora resolva a nova questão.

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

Responda SOMENTE no seguinte formato:

Resposta: X

onde X deve ser apenas uma letra:
A, B, C, D ou E.
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