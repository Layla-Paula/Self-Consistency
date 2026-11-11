# Resultados experimentais — síntese para o TCC

Atualizado em 11/11/2026 07:55. Execuções consideradas: **24**. As tabelas são recriadas a partir dos JSONs sempre que este script é executado.

**Pergunta de pesquisa:** a Self-Consistency oferece ganhos de acurácia que compensam o aumento de tempo e tokens em relação a Few-shot e CoT?

**Leitura:** cada linha é uma configuração experimental. Acurácia indisponível significa ausência de veredito completo (especialmente no Censo). Execuções com falhas técnicas são sinalizadas; elas não são descartadas. A coluna de computador foi omitida porque a origem não é conhecida em todos os JSONs.

## AQUA_RAT

### Acurácia e custo por configuração

| Técnica | Questões (limite) | Ex. | Temp. | Tokens máx. | Amostras | Máquina | Exec. | Acurácia média | Tokens usados/questão | Tempo médio/questão* | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | 200 | 10 | 0.0 | 1200 | — | não informada | 2 | 31.50% | 1591 | — | 0 |
| Few-shot | 200 | 10 | 0.0 | 2400 | — | DESKTOP-72VHDHF | 1 | 30.00% | 1644 | 20,9 s | 0 |
| Few-shot | 200 | 10 | 0.0 | 2400 | — | não informada | 1 | 32.00% | 1638 | — | 0 |
| CoT | 200 | 10 | 0.0 | 1200 | — | DESKTOP-72VHDHF | 1 | 39.50% | 3060 | 45,8 s | 0 |
| CoT | 200 | 10 | 0.0 | 1200 | — | não informada | 3 | 37.83% | 3039 | — | 0 |
| CoT | 200 | 10 | 0.0 | 2400 | — | não informada | 2 | 41.50% | 3268 | — | 0 |
| SC | 200 | 10 | 0.3 | 1200 | 5 | não informada | 1 | 50.50% | 15241 | — | 0 |
| SC | 200 | 10 | 0.3 | 2400 | 5 | não informada | 1 | 48.50% | 16267 | — | 0 |
| SC | 200 | 10 | 0.3 | 2400 | 5 | não informada | 1 | 51.00% | 16089 | — | 0 |
| SC | 200 | 10 | 0.5 | 2400 | 5 | não informada | 1 | 52.00% | 15942 | — | 0 |
| SC | 200 | 10 | 0.5 | 2400 | 5 | não informada | 1 | 51.00% | 15851 | — | 0 |
| SC | 200 | 10 | 0.7 | 1200 | 5 | não informada | 5 | 47.50% | 14983 | — | 0 |
| SC | 200 | 10 | 0.7 | 2400 | 3 | não informada | 1 | 47.00% | 9360 | — | 0 |
| SC | 200 | 10 | 0.7 | 2400 | 3 | não informada | 1 | 40.50% | 9384 | — | 0 |
| SC | 200 | 10 | 0.7 | 2400 | 5 | não informada | 2 | 44.50% | 15701 | — | 0 |

### Diferença de acurácia nas mesmas questões

| Comparação | N comum | Diferença B−A (pp) | p McNemar |
| --- | --- | --- | --- |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:59] × CoT / t=0.0 / 1200 tokens [11-10 09:04] | 200 | 8.00 | 0.0805 |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:59] × SC / t=0.3 / 5 amostras / 1200 tokens [10-30 18:17] | 200 | 18.50 | 0.0000 |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:59] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 12:16] | 200 | 17.50 | 0.0001 |
| CoT / t=0.0 / 1200 tokens [11-10 09:04] × SC / t=0.3 / 5 amostras / 1200 tokens [10-30 18:17] | 200 | 10.50 | 0.0019 |
| CoT / t=0.0 / 1200 tokens [11-10 09:04] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 12:16] | 200 | 9.50 | 0.0163 |
| Few-shot / t=0.0 / 2400 tokens [11-10 02:59] × CoT / t=0.0 / 2400 tokens [11-09 16:59] | 200 | 10.00 | 0.0286 |
| Few-shot / t=0.0 / 2400 tokens [11-10 02:59] × SC / t=0.3 / 5 amostras / 2400 tokens [11-08 03:30] | 200 | 21.00 | 0.0000 |
| Few-shot / t=0.0 / 2400 tokens [11-10 02:59] × SC / t=0.5 / 5 amostras / 2400 tokens [11-06 16:12] | 200 | 21.00 | 0.0000 |
| Few-shot / t=0.0 / 2400 tokens [11-10 02:59] × SC / t=0.7 / 3 amostras / 2400 tokens [11-08 04:09] | 200 | 10.50 | 0.0275 |
| Few-shot / t=0.0 / 2400 tokens [11-10 02:59] × SC / t=0.7 / 5 amostras / 2400 tokens [11-05 16:46] | 200 | 14.50 | 0.0019 |
| CoT / t=0.0 / 2400 tokens [11-09 16:59] × SC / t=0.3 / 5 amostras / 2400 tokens [11-08 03:30] | 200 | 11.00 | 0.0062 |
| CoT / t=0.0 / 2400 tokens [11-09 16:59] × SC / t=0.5 / 5 amostras / 2400 tokens [11-06 16:12] | 200 | 11.00 | 0.0092 |
| CoT / t=0.0 / 2400 tokens [11-09 16:59] × SC / t=0.7 / 3 amostras / 2400 tokens [11-08 04:09] | 200 | 0.50 | 1.0000 |
| CoT / t=0.0 / 2400 tokens [11-09 16:59] × SC / t=0.7 / 5 amostras / 2400 tokens [11-05 16:46] | 200 | 4.50 | 0.2717 |

*Tempo: só entram execuções que rodaram sozinhas no computador (2 de 24 neste conjunto); as demais rodaram em paralelo ou em outro PC e ficaram de fora. "—" = nenhuma execução isolada.*

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

- 19 execução(ões) de teste, com menos questões que o recorte, ficaram de fora.
