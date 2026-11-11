# Resultados experimentais — síntese para o TCC

Atualizado em 11/11/2026 07:55. Execuções consideradas: **29**. As tabelas são recriadas a partir dos JSONs sempre que este script é executado.

**Pergunta de pesquisa:** a Self-Consistency oferece ganhos de acurácia que compensam o aumento de tempo e tokens em relação a Few-shot e CoT?

**Leitura:** cada linha é uma configuração experimental. Acurácia indisponível significa ausência de veredito completo (especialmente no Censo). Execuções com falhas técnicas são sinalizadas; elas não são descartadas. A coluna de computador foi omitida porque a origem não é conhecida em todos os JSONs.

## GSM8K

### Acurácia e custo por configuração

| Técnica | Questões (limite) | Ex. | Temp. | Tokens máx. | Amostras | Máquina | Exec. | Acurácia média | Tokens usados/questão | Tempo médio/questão* | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | 200 | 10 | 0.0 | 1200 | — | não informada | 3 | 10.33% | 1088 | — | 0 |
| Few-shot | 200 | 10 | 0.0 | 2400 | — | DESKTOP-72VHDHF | 1 | 11.00% | 1088 | 42,8 s | 0 |
| Few-shot | 200 | 10 | 0.0 | 2400 | — | não informada | 1 | 9.00% | 1088 | — | 0 |
| CoT | 200 | 10 | 0.0 | 1200 | — | DESKTOP-72VHDHF | 1 | 64.50% | 2417 | 22,0 s | 0 |
| CoT | 200 | 10 | 0.0 | 1200 | — | não informada | 4 | 62.75% | 2416 | — | 0 |
| CoT | 200 | 10 | 0.0 | 2400 | — | não informada | 3 | 63.17% | 2428 | — | 0 |
| SC | 200 | 10 | 0.3 | 1200 | 5 | não informada | 2 | 69.50% | 12133 | — | 0 |
| SC | 200 | 10 | 0.3 | 2400 | 5 | não informada | 2 | 69.25% | 12168 | — | 0 |
| SC | 200 | 10 | 0.5 | 2400 | 5 | não informada | 2 | 70.75% | 12174 | — | 0 |
| SC | 200 | 10 | 0.7 | 1200 | 5 | não informada | 5 | 71.30% | 12103 | — | 0 |
| SC | 200 | 10 | 0.7 | 2400 | 3 | não informada | 2 | 65.25% | 7301 | — | 0 |
| SC | 200 | 10 | 0.7 | 2400 | 5 | não informada | 3 | 72.50% | 12107 | — | 0 |

### Diferença de acurácia nas mesmas questões

| Comparação | N comum | Diferença B−A (pp) | p McNemar |
| --- | --- | --- | --- |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:42] × CoT / t=0.0 / 1200 tokens [11-10 07:59] | 200 | 51.00 | 0.0000 |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:42] × SC / t=0.3 / 5 amostras / 1200 tokens [10-30 09:55] | 200 | 58.00 | 0.0000 |
| Few-shot / t=0.0 / 1200 tokens [11-01 09:42] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 06:41] | 200 | 60.50 | 0.0000 |
| CoT / t=0.0 / 1200 tokens [11-10 07:59] × SC / t=0.3 / 5 amostras / 1200 tokens [10-30 09:55] | 200 | 7.00 | 0.0243 |
| CoT / t=0.0 / 1200 tokens [11-10 07:59] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 06:41] | 200 | 9.50 | 0.0019 |
| Few-shot / t=0.0 / 2400 tokens [11-10 00:38] × CoT / t=0.0 / 2400 tokens [11-09 14:21] | 200 | 53.50 | 0.0000 |
| Few-shot / t=0.0 / 2400 tokens [11-10 00:38] × SC / t=0.3 / 5 amostras / 2400 tokens [11-07 16:38] | 200 | 60.00 | 0.0000 |
| Few-shot / t=0.0 / 2400 tokens [11-10 00:38] × SC / t=0.5 / 5 amostras / 2400 tokens [11-05 23:03] | 200 | 63.00 | 0.0000 |
| Few-shot / t=0.0 / 2400 tokens [11-10 00:38] × SC / t=0.7 / 3 amostras / 2400 tokens [11-07 19:35] | 200 | 56.00 | 0.0000 |
| Few-shot / t=0.0 / 2400 tokens [11-10 00:38] × SC / t=0.7 / 5 amostras / 2400 tokens [11-05 10:42] | 200 | 63.50 | 0.0000 |
| CoT / t=0.0 / 2400 tokens [11-09 14:21] × SC / t=0.3 / 5 amostras / 2400 tokens [11-07 16:38] | 200 | 6.50 | 0.0351 |
| CoT / t=0.0 / 2400 tokens [11-09 14:21] × SC / t=0.5 / 5 amostras / 2400 tokens [11-05 23:03] | 200 | 9.50 | 0.0034 |
| CoT / t=0.0 / 2400 tokens [11-09 14:21] × SC / t=0.7 / 3 amostras / 2400 tokens [11-07 19:35] | 200 | 2.50 | 0.4869 |
| CoT / t=0.0 / 2400 tokens [11-09 14:21] × SC / t=0.7 / 5 amostras / 2400 tokens [11-05 10:42] | 200 | 10.00 | 0.0022 |

*Tempo: só entram execuções que rodaram sozinhas no computador (2 de 29 neste conjunto); as demais rodaram em paralelo ou em outro PC e ficaram de fora. "—" = nenhuma execução isolada.*

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

- 20 execução(ões) de teste, com menos questões que o recorte, ficaram de fora.
