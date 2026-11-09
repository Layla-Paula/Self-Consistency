# Avaliação experimental — gsm8k

## Arquivos analisados

- Few-shot: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\few_shot\gsm8k\limite_300_exemplos_10\few_shot_gsm8k_01112026_094258_337.json`
- CoT: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\chain_of_thought\gsm8k\limite_200_exemplos_10\chain_of_thought_gsm8k_09112026_122742_240.json`
- SC: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\self_consistency\gsm8k\limite_1_exemplos_1\self_consistency_gsm8k_09112026_095636_524.json`

**ATENÇÃO — execuções NÃO comparáveis:** questões diferentes: Few-shot=300, CoT=200, SC=1; parâmetro "quantidade_exemplos" difere; parâmetro "ids_exemplos" difere; parâmetro "maximo_tokens_resposta" difere

## Avisos de comparabilidade

- Few-shot: 11 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- CoT: 12 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- SC: 33 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- As técnicas não usaram exatamente as mesmas questões. Comparações pareadas usam a interseção.
- Parâmetro diferente: quantidade_exemplos — Few-shot=10; CoT=10; SC=1
- Parâmetro diferente: ids_exemplos — Few-shot=['train_5712', 'train_1819', 'train_1181', 'train_6465', 'train_3025', 'train_2803', 'train_2643', 'train_2026', 'train_6428', 'train_1753']; CoT=['train_5712', 'train_1819', 'train_1181', 'train_6465', 'train_3025', 'train_2803', 'train_2643', 'train_2026', 'train_6428', 'train_1753']; SC=['train_5712']
- Parâmetro diferente: maximo_tokens_resposta — Few-shot=1200; CoT=2400; SC=2400
- Parâmetro diferente: temperatura — Few-shot=0.0; CoT=0.0; SC=0.7
- Parâmetro diferente: n_amostras — Few-shot=None; CoT=None; SC=3
- Tempo é comparável apenas com hardware e carga de máquina equivalentes; diferenças de temperatura podem confundir o efeito da técnica.

## Acurácia

| Técnica | Planejadas | N sem falha | Acertos | Pendentes | Acurácia | IC Wilson 95% | Acertos / planejadas | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | 300 | 300 | 27 | 0 | 9.00% | 6.26% a 12.78% | 9.00% | 0 |
| CoT | 200 | 200 | 129 | 0 | 64.50% | 57.65% a 70.80% | 64.50% | 0 |
| SC | 1 | 1 | 1 | 0 | 100.00% | 20.65% a 100.00% | 100.00% | 0 |

"Faixa" = mínimo e máximo enquanto há revisão humana pendente; NÃO é intervalo de confiança. "Acertos / planejadas" conta falha técnica e pendência como não acerto.

## Comparações pareadas — McNemar exato

| Par | N comum | Diferença (pp) | Só A | Só B | p bicaudal |
| --- | --- | --- | --- | --- | --- |
| Few-shot × CoT | 200 | 53.00 | 8 | 114 | 0.00000 |
| CoT × SC | 1 | 0.00 | 0 | 0 | 1.00000 |
| Few-shot × SC | 1 | 0.00 | 0 | 0 | 1.00000 |

## Custo computacional

| Técnica | Tempo médio (s) | N tempo | Tokens entrada | Tokens saída |
| --- | --- | --- | --- | --- |
| Few-shot | 3.26 | 300 | 1081.41 | 6.15 |
| CoT | 23.40 | 200 | 2166.28 | 262.52 |
| SC | 30.91 | 1 | 900.00 | 490.00 |

## Custo-benefício (ganho pareado)

| Comparação | Ganho (pp) | Tempo adicional (s) | N tempo pareado | Multiplicador tempo | pp/s adicional | Tokens adicionais | pp/1000 tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| few_shot → self_consistency | 0.00 | 15.59 | 1 | 2.02 | 0.0000 | 331 | 0.0000 |
| chain_of_thought → self_consistency | 0.00 | -10.07 | 1 | 0.75 | — | -932 | — |

## Falhas

| Técnica | Falhas técnicas | Respostas vazias | Limite de tokens | Amostras sem extração / total |
| --- | --- | --- | --- | --- |
| Few-shot | 0 | 0 | 0 | 0/0 |
| CoT | 0 | 3 | 0 | 0/0 |
| SC | 0 | 0 | 0 | 1/3 |

## Self-Consistency — primeiras k amostras


### Curva principal: mesmas questões em todos os k

| k | Questões | Acertos | Acurácia | Empates |
| --- | --- | --- | --- | --- |
| 1 | 1 | 0 | 0.00% | 0 |
| 2 | 1 | 1 | 100.00% | 0 |
| 3 | 1 | 1 | 100.00% | 0 |

### Curva exploratória: N variável

| k | Questões | Acertos | Acurácia | Empates |
| --- | --- | --- | --- | --- |
| 1 | 1 | 0 | 0.00% | 0 |
| 2 | 1 | 1 | 100.00% | 0 |
| 3 | 1 | 1 | 100.00% | 0 |

Cada k usa questões com pelo menos k amostras; N pode variar.

Análise COMPLETA: 1 de 1 questões com amostras.

Acurácia média de UMA amostra: 66.67%; alguma amostra acerta (teto): 100.00%.

Nota: significância estatística não implica benefício prático. Comparações com configurações diferentes exigem interpretação cautelosa.
