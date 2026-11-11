# Resultados experimentais — síntese para o TCC

Atualizado em 11/11/2026 07:56. Execuções consideradas: **21**. As tabelas são recriadas a partir dos JSONs sempre que este script é executado.

**Pergunta de pesquisa:** a Self-Consistency oferece ganhos de acurácia que compensam o aumento de tempo e tokens em relação a Few-shot e CoT?

**Leitura:** cada linha é uma configuração experimental. Acurácia indisponível significa ausência de veredito completo (especialmente no Censo). Execuções com falhas técnicas são sinalizadas; elas não são descartadas. A coluna de computador foi omitida porque a origem não é conhecida em todos os JSONs.

## CENSO

### Acurácia e custo por configuração

| Técnica | Questões (limite) | Ex. | Temp. | Tokens máx. | Amostras | Máquina | Exec. | Acurácia média | Tokens usados/questão | Tempo médio/questão* | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | Todas | 6 | 0.0 | 1200 | — | não informada | 2 | 17.05% | 19089 | — | 0 |
| Few-shot | Todas | 6 | 0.0 | 2400 | — | DESKTOP-72VHDHF | 1 | 20.45% | 16616 | 2 min 04 s | 0 |
| Few-shot | Todas | 6 | 0.0 | 2400 | — | não informada | 1 | 22.73% | 16364 | — | 0 |
| CoT | Todas | 6 | 0.0 | 1200 | — | DESKTOP-72VHDHF | 1 | 25.00% | 17430 | 1 min 39 s | 0 |
| CoT | Todas | 6 | 0.0 | 1200 | — | não informada | 2 | 7.95% | 20181 | — | 0 |
| CoT | Todas | 6 | 0.0 | 2400 | — | não informada | 2 | 13.64% | 16637 | — | 0 |
| SC | Todas | 6 | 0.3 | 2400 | 5 | não informada | 1 | 15.91% | 90240 | — | 0 |
| SC | Todas | 6 | 0.5 | 2400 | 5 | não informada | 1 | 15.91% | 99001 | — | 0 |
| SC | Todas | 6 | 0.5 | 2400 | 5 | não informada | 1 | 9.09% | 100233 | — | 0 |
| SC | Todas | 6 | 0.7 | 1200 | 5 | não informada | 5 | 10.23% | 112956 | — | 0 |
| SC | Todas | 6 | 0.7 | 2400 | 3 | não informada | 1 | 6.82% | 65654 | — | 0 |
| SC | Todas | 6 | 0.7 | 2400 | 3 | não informada | 1 | 13.64% | 64556 | — | 0 |
| SC | Todas | 6 | 0.7 | 2400 | 5 | não informada | 1 | 6.82% | 112575 | — | 0 |
| SC | Todas | 6 | 0.7 | 2400 | 5 | não informada | 1 | 6.82% | 114613 | — | 0 |

### Diferença de acurácia nas mesmas questões

| Comparação | N comum | Diferença B−A (pp) | p McNemar |
| --- | --- | --- | --- |
| Few-shot / t=0.0 / 1200 tokens [11-01 11:13] × CoT / t=0.0 / 1200 tokens [11-10 11:34] | 44 | 4.55 | 0.7539 |
| Few-shot / t=0.0 / 1200 tokens [11-01 11:13] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 22:13] | 44 | -9.09 | 0.2891 |
| CoT / t=0.0 / 1200 tokens [11-10 11:34] × SC / t=0.7 / 5 amostras / 1200 tokens [11-04 22:13] | 44 | -13.64 | 0.0312 |
| Few-shot / t=0.0 / 2400 tokens [11-10 04:09] × CoT / t=0.0 / 2400 tokens [11-09 21:38] | 44 | -4.55 | 0.7266 |
| Few-shot / t=0.0 / 2400 tokens [11-10 04:09] × SC / t=0.3 / 5 amostras / 2400 tokens [11-09 14:29] | 44 | -4.55 | 0.7539 |
| Few-shot / t=0.0 / 2400 tokens [11-10 04:09] × SC / t=0.5 / 5 amostras / 2400 tokens [11-06 16:52] | 44 | -11.36 | 0.1250 |
| Few-shot / t=0.0 / 2400 tokens [11-10 04:09] × SC / t=0.7 / 3 amostras / 2400 tokens [11-08 22:26] | 44 | -6.82 | 0.5078 |
| Few-shot / t=0.0 / 2400 tokens [11-10 04:09] × SC / t=0.7 / 5 amostras / 2400 tokens [11-06 10:19] | 44 | -13.64 | 0.0312 |
| CoT / t=0.0 / 2400 tokens [11-09 21:38] × SC / t=0.3 / 5 amostras / 2400 tokens [11-09 14:29] | 44 | 0.00 | 1.0000 |
| CoT / t=0.0 / 2400 tokens [11-09 21:38] × SC / t=0.5 / 5 amostras / 2400 tokens [11-06 16:52] | 44 | -6.82 | 0.4531 |
| CoT / t=0.0 / 2400 tokens [11-09 21:38] × SC / t=0.7 / 3 amostras / 2400 tokens [11-08 22:26] | 44 | -2.27 | 1.0000 |
| CoT / t=0.0 / 2400 tokens [11-09 21:38] × SC / t=0.7 / 5 amostras / 2400 tokens [11-06 10:19] | 44 | -9.09 | 0.1250 |

*Tempo: só entram execuções que rodaram sozinhas no computador (2 de 21 neste conjunto); as demais rodaram em paralelo ou em outro PC e ficaram de fora. "—" = nenhuma execução isolada.*

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
