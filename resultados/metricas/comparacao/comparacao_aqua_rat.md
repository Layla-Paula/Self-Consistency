# Avaliação experimental — aqua_rat

## Arquivos analisados

- Few-shot: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\few_shot\aqua_rat\limite_300_exemplos_10\few_shot_aqua_rat_01112026_095918_674.json`
- CoT: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\chain_of_thought\aqua_rat\limite_300_exemplos_10\chain_of_thought_aqua_rat_31102026_205138_005.json`
- SC: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\self_consistency\aqua_rat\limite_200_exemplos_10\self_consistency_aqua_rat_07112026_084757_647.json`

**ATENÇÃO — execuções NÃO comparáveis:** questões diferentes: Few-shot=300, CoT=300, SC=200; parâmetro "maximo_tokens_resposta" difere

## Avisos de comparabilidade

- Few-shot: 9 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- CoT: 7 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- SC: 15 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- As técnicas não usaram exatamente as mesmas questões. Comparações pareadas usam a interseção.
- Parâmetro diferente: maximo_tokens_resposta — Few-shot=1200; CoT=1200; SC=2400
- Parâmetro diferente: temperatura — Few-shot=0.0; CoT=0.0; SC=0.3
- Parâmetro diferente: n_amostras — Few-shot=None; CoT=None; SC=5
- Tempo é comparável apenas com hardware e carga de máquina equivalentes; diferenças de temperatura podem confundir o efeito da técnica.

## Acurácia

| Técnica | Planejadas | N sem falha | Acertos | Pendentes | Acurácia | IC Wilson 95% | Acertos / planejadas | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | 300 | 300 | 88 | 0 | 29.33% | 24.47% a 34.72% | 29.33% | 0 |
| CoT | 300 | 300 | 103 | 0 | 34.33% | 29.19% a 39.87% | 34.33% | 0 |
| SC | 200 | 196 | 96 | 0 | 48.98% | 42.07% a 55.93% | 48.00% | 4 |

"Faixa" = mínimo e máximo enquanto há revisão humana pendente; NÃO é intervalo de confiança. "Acertos / planejadas" conta falha técnica e pendência como não acerto.

## Comparações pareadas — McNemar exato

| Par | N comum | Diferença (pp) | Só A | Só B | p bicaudal |
| --- | --- | --- | --- | --- | --- |
| Few-shot × CoT | 300 | 5.00 | 45 | 60 | 0.17156 |
| CoT × SC | 196 | 13.27 | 16 | 42 | 0.00086 |
| Few-shot × SC | 196 | 16.84 | 19 | 52 | 0.00011 |

## Custo computacional

| Técnica | Tempo médio (s) | N tempo | Tokens entrada | Tokens saída |
| --- | --- | --- | --- | --- |
| Few-shot | 14.73 | 300 | 1415.42 | 174.12 |
| CoT | 39.48 | 300 | 2575.42 | 462.64 |
| SC | 522.27 | 200 | 12682.03 | 3303.07 |

## Custo-benefício (ganho pareado)

| Comparação | Ganho (pp) | Tempo adicional (s) | N tempo pareado | Multiplicador tempo | pp/s adicional | Tokens adicionais | pp/1000 tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| few_shot → self_consistency | 16.84 | 496.30 | 196 | 37.00 | 0.0339 | 14651 | 1.1492 |
| chain_of_thought → self_consistency | 13.27 | 470.50 | 196 | 12.88 | 0.0282 | 13194 | 1.0054 |

## Falhas

| Técnica | Falhas técnicas | Respostas vazias | Limite de tokens | Amostras sem extração / total |
| --- | --- | --- | --- | --- |
| Few-shot | 0 | 23 | 0 | 0/0 |
| CoT | 0 | 52 | 0 | 0/0 |
| SC | 4 | 6 | 86 | 185/989 |

## Self-Consistency — primeiras k amostras


### Curva principal: mesmas questões em todos os k

| k | Questões | Acertos | Acurácia | Empates |
| --- | --- | --- | --- | --- |
| 1 | 196 | 77 | 39.29% | 0 |
| 2 | 196 | 85 | 43.37% | 64 |
| 3 | 196 | 87 | 44.39% | 44 |
| 4 | 196 | 91 | 46.43% | 37 |
| 5 | 196 | 96 | 48.98% | 40 |

### Curva exploratória: N variável

| k | Questões | Acertos | Acurácia | Empates |
| --- | --- | --- | --- | --- |
| 1 | 196 | 77 | 39.29% | 0 |
| 2 | 196 | 85 | 43.37% | 64 |
| 3 | 196 | 87 | 44.39% | 44 |
| 4 | 196 | 91 | 46.43% | 37 |
| 5 | 196 | 96 | 48.98% | 40 |

Cada k usa questões com pelo menos k amostras; N pode variar.

Análise PARCIAL: 196 de 200 questões com amostras; fora: aqua_rat_train_00132, aqua_rat_train_00168, aqua_rat_train_00174, aqua_rat_train_00181.

Acurácia média de UMA amostra: 38.98%; alguma amostra acerta (teto): 73.47%.

Nota: significância estatística não implica benefício prático. Comparações com configurações diferentes exigem interpretação cautelosa.
