# Resultados experimentais — síntese para o TCC

Atualizado em 11/11/2026 12:56. Execuções consideradas: **27**. As tabelas são recriadas a partir dos JSONs sempre que este script é executado.

**Pergunta de pesquisa:** a Self-Consistency oferece ganhos de acurácia que compensam o aumento de tempo e tokens em relação a Few-shot e CoT?

**Leitura:** cada linha é uma configuração experimental. Acurácia indisponível significa ausência de veredito completo (especialmente no Censo). Execuções com falhas técnicas são sinalizadas; elas não são descartadas. A coluna de computador foi omitida porque a origem não é conhecida em todos os JSONs.

## GSM8K

### Acurácia e custo por configuração

| Técnica | Questões (limite) | Ex. | Temp. | Tokens máx. | Amostras | Exec. | Acurácia média | Tokens usados/questão | Tempo médio/questão* | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | 500 | 100 | 0.0 | 1200 | — | 3 | 9.67% | 4104 | — | 0 |
| CoT | 500 | 100 | 0.0 | 1200 | — | 6 | 55.40% | 4320 | — | 0 |
| SC | 500 | 100 | 0.7 | 1200 | 3 | 1 | 56.20% | 12933 | — | 0 |
| SC | 500 | 100 | 0.7 | 1200 | 5 | 3 | 63.73% | 21514 | — | 0 |

### Diferença de acurácia nas mesmas questões

| Comparação | N comum | Diferença B−A (pp) | p McNemar |
| --- | --- | --- | --- |
| Few-shot / t=0.0 / 1200 tokens [10-26 17:21] × CoT / t=0.0 / 1200 tokens [10-30 07:00] | 500 | 44.00 | 0.0000 |
| Few-shot / t=0.0 / 1200 tokens [10-26 17:21] × SC / t=0.7 / 3 amostras / 1200 tokens [10-23 22:51] | 500 | 46.20 | 0.0000 |
| Few-shot / t=0.0 / 1200 tokens [10-26 17:21] × SC / t=0.7 / 5 amostras / 1200 tokens [10-30 20:50] | 500 | 53.60 | 0.0000 |
| CoT / t=0.0 / 1200 tokens [10-30 07:00] × SC / t=0.7 / 3 amostras / 1200 tokens [10-23 22:51] | 500 | 2.20 | 0.3594 |
| CoT / t=0.0 / 1200 tokens [10-30 07:00] × SC / t=0.7 / 5 amostras / 1200 tokens [10-30 20:50] | 500 | 9.60 | 0.0000 |

*Tempo: só entram execuções que rodaram sozinhas no computador (0 de 13 neste conjunto); as demais rodaram em paralelo ou em outro PC e ficaram de fora. "—" = nenhuma execução isolada.*

*Tempos meramente descritivos: computadores não identificados.*

### Interpretação

Compare primeiro a diferença de acurácia em questões pareadas. O custo principal são os tokens (medida independente do computador); o tempo é complementar. Veja os custos por execução em `tabelas.xlsx` (tokens de entrada/saída e tempo médio). O limite máximo de tokens não é o número de tokens efetivamente consumidos. **Não é possível concluir que uma técnica é mais rápida apenas pelos tempos misturados de PC1 e PC2.**

## AQUA_RAT

### Acurácia e custo por configuração

| Técnica | Questões (limite) | Ex. | Temp. | Tokens máx. | Amostras | Exec. | Acurácia média | Tokens usados/questão | Tempo médio/questão* | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | 500 | 100 | 0.0 | 1200 | — | 2 | 25.50% | 4103 | — | 0 |
| CoT | 500 | 100 | 0.0 | 1200 | — | 3 | 24.20% | 4106 | — | 0 |
| SC | 500 | 100 | 0.7 | 1200 | 3 | 1 | 23.00% | 12330 | — | 0 |
| SC | 500 | 100 | 0.7 | 1200 | 5 | 2 | 24.20% | 20599 | — | 0 |

### Diferença de acurácia nas mesmas questões

| Comparação | N comum | Diferença B−A (pp) | p McNemar |
| --- | --- | --- | --- |
| Few-shot / t=0.0 / 1200 tokens [10-27 02:19] × CoT / t=0.0 / 1200 tokens [10-28 05:26] | 500 | -1.20 | 0.5386 |
| Few-shot / t=0.0 / 1200 tokens [10-27 02:19] × SC / t=0.7 / 3 amostras / 1200 tokens [10-25 06:59] | 500 | -2.40 | 0.3875 |
| Few-shot / t=0.0 / 1200 tokens [10-27 02:19] × SC / t=0.7 / 5 amostras / 1200 tokens [10-31 13:00] | 500 | -1.20 | 0.7031 |
| CoT / t=0.0 / 1200 tokens [10-28 05:26] × SC / t=0.7 / 3 amostras / 1200 tokens [10-25 06:59] | 500 | -1.20 | 0.7125 |
| CoT / t=0.0 / 1200 tokens [10-28 05:26] × SC / t=0.7 / 5 amostras / 1200 tokens [10-31 13:00] | 500 | 0.00 | 1.0000 |

*Tempo: só entram execuções que rodaram sozinhas no computador (0 de 8 neste conjunto); as demais rodaram em paralelo ou em outro PC e ficaram de fora. "—" = nenhuma execução isolada.*

*Tempos meramente descritivos: computadores não identificados.*

### Interpretação

Compare primeiro a diferença de acurácia em questões pareadas. O custo principal são os tokens (medida independente do computador); o tempo é complementar. Veja os custos por execução em `tabelas.xlsx` (tokens de entrada/saída e tempo médio). O limite máximo de tokens não é o número de tokens efetivamente consumidos. **Não é possível concluir que uma técnica é mais rápida apenas pelos tempos misturados de PC1 e PC2.**

## CENSO

### Acurácia e custo por configuração

| Técnica | Questões (limite) | Ex. | Temp. | Tokens máx. | Amostras | Exec. | Acurácia média | Tokens usados/questão | Tempo médio/questão* | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | Todas | 12 | 0.0 | 1200 | — | 1 | 13.16% | 25109 | — | 0 |
| CoT | Todas | 12 | 0.0 | 1200 | — | 1 | 31.58% | 19270 | — | 0 |
| SC | Todas | 12 | 0.7 | 1200 | 3 | 2 | — | 95423 | — | 0 |
| SC | Todas | 12 | 0.7 | 1200 | 5 | 2 | — | 167212 | — | 0 |

### Diferença de acurácia nas mesmas questões

| Comparação | N comum | Diferença B−A (pp) | p McNemar |
| --- | --- | --- | --- |
| Few-shot / t=0.0 / 1200 tokens [10-27 11:13] × CoT / t=0.0 / 1200 tokens [10-28 14:42] | 38 | 18.42 | 0.0654 |

*Tempo: só entram execuções que rodaram sozinhas no computador (0 de 6 neste conjunto); as demais rodaram em paralelo ou em outro PC e ficaram de fora. "—" = nenhuma execução isolada.*

*Tempos meramente descritivos: computadores não identificados.*

### Interpretação

Compare primeiro a diferença de acurácia em questões pareadas. O custo principal são os tokens (medida independente do computador); o tempo é complementar. Veja os custos por execução em `tabelas.xlsx` (tokens de entrada/saída e tempo médio). O limite máximo de tokens não é o número de tokens efetivamente consumidos. **Não é possível concluir que uma técnica é mais rápida apenas pelos tempos misturados de PC1 e PC2.**

## Limitações e cuidados

- A análise inclui todas as configurações encontradas; não pressupõe que todas as combinações foram executadas.
- Comparações pareadas usam questões com veredito válido em ambos os experimentos; confira também exemplos e parâmetros antes de interpretar causalmente.
- O Censo exige revisão humana dos casos pendentes para uma acurácia definitiva.
- Falhas técnicas e recuperações são rastreadas; os arquivos originais não são modificados.
- Tempos medidos em máquinas não identificadas devem ser tratados apenas como dados descritivos.
- Tempo: parte das execuções rodou em paralelo no mesmo computador (ou em outro PC, como teste) e foi descartada do tempo; ela continua valendo para acurácia e tokens. Os tokens são a medida principal de custo.
- A decisão custo-benefício deve considerar o ganho de acurácia e o consumo efetivo de tokens, não apenas o teto configurado.

## Avisos de processamento

- 83 execução(ões) de teste, com menos questões que o recorte, ficaram de fora.
