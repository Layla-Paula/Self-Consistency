# Resultados experimentais — síntese para o TCC

Atualizado em 09/11/2026 14:38. Execuções consideradas: **57**. As tabelas são recriadas a partir dos JSONs sempre que este script é executado.

**Pergunta de pesquisa:** a Self-Consistency oferece ganhos de acurácia que compensam o aumento de tempo e tokens em relação a Few-shot e CoT?

**Leitura:** cada linha é uma configuração experimental. Acurácia indisponível significa ausência de veredito completo (especialmente no Censo). Execuções com falhas técnicas são sinalizadas; elas não são descartadas. A coluna de computador foi omitida porque a origem não é conhecida em todos os JSONs.

## GSM8K

### Acurácia e custo por configuração

| Técnica | Questões (limite) | Ex. | Temp. | Tokens máx. | Amostras | Exec. | Acurácia média | Tokens usados/questão | Tempo médio/questão* | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | 200 | 10 | 0.0 | 1200 | — | 3 | 10.33% | 1088 | 4,6 s | 0 |
| CoT | 200 | 10 | 0.0 | 1200 | — | 3 | 62.83% | 2416 | 10,1 s | 0 |
| CoT | 200 | 10 | 0.0 | 2400 | — | 1 | 64.50% | 2429 | 23,4 s | 0 |
| SC | 200 | 10 | 0.3 | 1200 | 5 | 3 | 69.50% | 8089 | 1 min 13 s | 200 |
| SC | 200 | 10 | 0.3 | 2400 | 5 | 2 | 69.25% | 12168 | 2 min 50 s | 0 |
| SC | 200 | 10 | 0.5 | 2400 | 5 | 2 | 70.75% | 12174 | 3 min 30 s | 0 |
| SC | 200 | 10 | 0.7 | 1200 | 5 | 5 | 71.30% | 12103 | 1 min 31 s | 0 |
| SC | 200 | 10 | 0.7 | 2400 | 3 | 2 | 65.25% | 7301 | 3 min 15 s | 0 |
| SC | 200 | 10 | 0.7 | 2400 | 5 | 3 | 72.50% | 12107 | 1 min 51 s | 0 |

### Diferença de acurácia nas mesmas questões

| Comparação | N comum | Diferença B−A (pp) | p McNemar |
| --- | --- | --- | --- |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:42] × CoT / t=0.0 / 1200 tokens [10-31 19:12] | 200 | 50.50 | 0.0000 |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:42] × SC / t=0.3 / 5 amostras / 1200 tokens [10-30 09:55] | 200 | 58.00 | 0.0000 |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:42] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 06:41] | 200 | 60.50 | 0.0000 |
| CoT / t=0.0 / 1200 tokens [10-31 19:12] × SC / t=0.3 / 5 amostras / 1200 tokens [10-30 09:55] | 200 | 7.50 | 0.0275 |
| CoT / t=0.0 / 1200 tokens [10-31 19:12] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 06:41] | 200 | 10.00 | 0.0022 |
| CoT / t=0.0 / 2400 tokens [11-09 12:27] × SC / t=0.3 / 5 amostras / 2400 tokens [11-07 16:38] | 200 | 4.50 | 0.2110 |
| CoT / t=0.0 / 2400 tokens [11-09 12:27] × SC / t=0.5 / 5 amostras / 2400 tokens [11-05 23:03] | 200 | 7.50 | 0.0357 |
| CoT / t=0.0 / 2400 tokens [11-09 12:27] × SC / t=0.7 / 3 amostras / 2400 tokens [11-07 19:35] | 200 | 0.50 | 1.0000 |
| CoT / t=0.0 / 2400 tokens [11-09 12:27] × SC / t=0.7 / 5 amostras / 2400 tokens [11-05 10:42] | 200 | 8.00 | 0.0166 |

*Tempos meramente descritivos: computadores não identificados.*

### Interpretação

Compare primeiro a diferença de acurácia em questões pareadas. Depois consulte os custos por execução em `tabelas.xlsx` (tokens de entrada/saída e tempo médio). O limite máximo de tokens não é o número de tokens efetivamente consumidos. **Não é possível concluir que uma técnica é mais rápida apenas pelos tempos misturados de PC1 e PC2.**

## AQUA_RAT

### Acurácia e custo por configuração

| Técnica | Questões (limite) | Ex. | Temp. | Tokens máx. | Amostras | Exec. | Acurácia média | Tokens usados/questão | Tempo médio/questão* | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | 200 | 10 | 0.0 | 1200 | — | 2 | 31.50% | 1591 | 11,9 s | 0 |
| CoT | 200 | 10 | 0.0 | 1200 | — | 2 | 36.75% | 3036 | 24,4 s | 0 |
| SC | 200 | 10 | 0.3 | 1200 | 5 | 2 | 50.25% | 7604 | 1 min 50 s | 201 |
| SC | 200 | 10 | 0.3 | 2400 | 5 | 2 | 50.25% | 15997 | 8 min 34 s | 6 |
| SC | 200 | 10 | 0.5 | 2400 | 5 | 2 | 51.51% | 15855 | 5 min 54 s | 2 |
| SC | 200 | 10 | 0.7 | 1200 | 5 | 5 | 47.50% | 14983 | 2 min 34 s | 0 |
| SC | 200 | 10 | 0.7 | 2400 | 3 | 2 | 43.55% | 9301 | 5 min 46 s | 7 |
| SC | 200 | 10 | 0.7 | 2400 | 5 | 2 | 44.50% | 15701 | 4 min 43 s | 0 |

### Diferença de acurácia nas mesmas questões

| Comparação | N comum | Diferença B−A (pp) | p McNemar |
| --- | --- | --- | --- |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:59] × CoT / t=0.0 / 1200 tokens [10-31 20:51] | 200 | 3.50 | 0.4767 |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:59] × SC / t=0.3 / 5 amostras / 1200 tokens [10-30 18:17] | 199 | 18.09 | 0.0001 |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:59] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 12:16] | 200 | 17.50 | 0.0001 |
| CoT / t=0.0 / 1200 tokens [10-31 20:51] × SC / t=0.3 / 5 amostras / 1200 tokens [10-30 18:17] | 199 | 15.08 | 0.0001 |
| CoT / t=0.0 / 1200 tokens [10-31 20:51] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 12:16] | 200 | 14.00 | 0.0008 |

*Tempos meramente descritivos: computadores não identificados.*

### Interpretação

Compare primeiro a diferença de acurácia em questões pareadas. Depois consulte os custos por execução em `tabelas.xlsx` (tokens de entrada/saída e tempo médio). O limite máximo de tokens não é o número de tokens efetivamente consumidos. **Não é possível concluir que uma técnica é mais rápida apenas pelos tempos misturados de PC1 e PC2.**

## CENSO

### Acurácia e custo por configuração

| Técnica | Questões (limite) | Ex. | Temp. | Tokens máx. | Amostras | Exec. | Acurácia média | Tokens usados/questão | Tempo médio/questão* | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | Todas | 6 | 0.0 | 1200 | — | 2 | 17.05% | 19089 | 1 min 13 s | 0 |
| CoT | Todas | 6 | 0.0 | 1200 | — | 1 | 2.27% | 23352 | 28,5 s | 0 |
| SC | Todas | 6 | 0.5 | 2400 | 5 | 2 | 11.19% | 83959 | 13 min 58 s | 25 |
| SC | Todas | 6 | 0.7 | 1200 | 5 | 5 | 10.23% | 112956 | 11 min 36 s | 0 |
| SC | Todas | 6 | 0.7 | 2400 | 3 | 2 | — | 63910 | 13 min 12 s | 6 |
| SC | Todas | 6 | 0.7 | 2400 | 5 | 2 | — | 112701 | 18 min 18 s | 1 |

### Diferença de acurácia nas mesmas questões

| Comparação | N comum | Diferença B−A (pp) | p McNemar |
| --- | --- | --- | --- |
| Few-shot / t=0.0 / 1200 tokens [11-01 11:13] × CoT / t=0.0 / 1200 tokens [10-24 16:50] | 44 | -18.18 | 0.0215 |
| Few-shot / t=0.0 / 1200 tokens [11-01 11:13] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 22:13] | 44 | -9.09 | 0.2891 |
| CoT / t=0.0 / 1200 tokens [10-24 16:50] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 22:13] | 44 | 9.09 | 0.2188 |

*Tempos meramente descritivos: computadores não identificados.*

### Interpretação

Compare primeiro a diferença de acurácia em questões pareadas. Depois consulte os custos por execução em `tabelas.xlsx` (tokens de entrada/saída e tempo médio). O limite máximo de tokens não é o número de tokens efetivamente consumidos. **Não é possível concluir que uma técnica é mais rápida apenas pelos tempos misturados de PC1 e PC2.**

## Limitações e cuidados

- A análise inclui todas as configurações encontradas; não pressupõe que todas as combinações foram executadas.
- Comparações pareadas usam questões com veredito válido em ambos os experimentos; confira também exemplos e parâmetros antes de interpretar causalmente.
- O Censo exige revisão humana dos casos pendentes para uma acurácia definitiva.
- Falhas técnicas e recuperações são rastreadas; os arquivos originais não são modificados.
- Tempos medidos em máquinas não identificadas devem ser tratados apenas como dados descritivos.
- A decisão custo-benefício deve considerar o ganho de acurácia e o consumo efetivo de tokens, não apenas o teto configurado.

## Avisos de processamento

- 37 execução(ões) de teste, com menos questões que o recorte, ficaram de fora.
