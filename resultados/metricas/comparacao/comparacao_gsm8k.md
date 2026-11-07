# Avaliação experimental — gsm8k

## Arquivos analisados

- Few-shot: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\few_shot\gsm8k\limite_300_exemplos_10\few_shot_gsm8k_01112026_094258_337.json`
- CoT: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\chain_of_thought\gsm8k\limite_300_exemplos_10\chain_of_thought_gsm8k_31102026_191245_813.json`
- SC: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\self_consistency\gsm8k\limite_200_exemplos_10\self_consistency_gsm8k_07112026_004415_418.json`

**ATENÇÃO — execuções NÃO comparáveis:** questões diferentes: Few-shot=300, CoT=300, SC=200; parâmetro "maximo_tokens_resposta" difere

## Avisos de comparabilidade

- Few-shot: 11 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- CoT: 11 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- SC: 18 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- As técnicas não usaram exatamente as mesmas questões. Comparações pareadas usam a interseção.
- Parâmetro diferente: maximo_tokens_resposta — Few-shot=1200; CoT=1200; SC=2400
- Parâmetro diferente: temperatura — Few-shot=0.0; CoT=0.0; SC=0.3
- Parâmetro diferente: n_amostras — Few-shot=None; CoT=None; SC=5
- Tempo é comparável apenas com hardware e carga de máquina equivalentes; diferenças de temperatura podem confundir o efeito da técnica.

## Acurácia

| Técnica | Planejadas | N sem falha | Acertos | Pendentes | Acurácia | IC Wilson 95% | Acertos / planejadas | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | 300 | 300 | 27 | 0 | 9.00% | 6.26% a 12.78% | 9.00% | 0 |
| CoT | 300 | 300 | 181 | 0 | 60.33% | 54.70% a 65.71% | 60.33% | 0 |
| SC | 200 | 200 | 139 | 0 | 69.50% | 62.80% a 75.46% | 69.50% | 0 |

"Faixa" = mínimo e máximo enquanto há revisão humana pendente; NÃO é intervalo de confiança. "Acertos / planejadas" conta falha técnica e pendência como não acerto.

## Comparações pareadas — McNemar exato

| Par | N comum | Diferença (pp) | Só A | Só B | p bicaudal |
| --- | --- | --- | --- | --- | --- |
| Few-shot × CoT | 300 | 51.33 | 7 | 161 | 0.00000 |
| CoT × SC | 200 | 7.50 | 12 | 27 | 0.02370 |
| Few-shot × SC | 200 | 58.00 | 6 | 122 | 0.00000 |

## Custo computacional

| Técnica | Tempo médio (s) | N tempo | Tokens entrada | Tokens saída |
| --- | --- | --- | --- | --- |
| Few-shot | 3.26 | 300 | 1081.41 | 6.15 |
| CoT | 19.77 | 300 | 2165.41 | 254.52 |
| SC | 145.08 | 200 | 10831.40 | 1341.24 |

## Custo-benefício (ganho pareado)

| Comparação | Ganho (pp) | Tempo adicional (s) | N tempo pareado | Multiplicador tempo | pp/s adicional | Tokens adicionais | pp/1000 tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| few_shot → self_consistency | 58.00 | 141.80 | 200 | 44.16 | 0.4090 | 11084 | 5.2327 |
| chain_of_thought → self_consistency | 7.50 | 125.44 | 200 | 7.39 | 0.0598 | 9754 | 0.7689 |

## Falhas

| Técnica | Falhas técnicas | Respostas vazias | Limite de tokens | Amostras sem extração / total |
| --- | --- | --- | --- | --- |
| Few-shot | 0 | 0 | 0 | 0/0 |
| CoT | 0 | 7 | 0 | 0/0 |
| SC | 0 | 0 | 7 | 16/1000 |

## Self-Consistency — primeiras k amostras


### Curva principal: mesmas questões em todos os k

| k | Questões | Acertos | Acurácia | Empates |
| --- | --- | --- | --- | --- |
| 1 | 200 | 127 | 63.50% | 0 |
| 2 | 200 | 127 | 63.50% | 82 |
| 3 | 200 | 135 | 67.50% | 41 |
| 4 | 200 | 135 | 67.50% | 33 |
| 5 | 200 | 139 | 69.50% | 19 |

### Curva exploratória: N variável

| k | Questões | Acertos | Acurácia | Empates |
| --- | --- | --- | --- | --- |
| 1 | 200 | 127 | 63.50% | 0 |
| 2 | 200 | 127 | 63.50% | 82 |
| 3 | 200 | 135 | 67.50% | 41 |
| 4 | 200 | 135 | 67.50% | 33 |
| 5 | 200 | 139 | 69.50% | 19 |

Cada k usa questões com pelo menos k amostras; N pode variar.

Análise COMPLETA: 200 de 200 questões com amostras.

Acurácia média de UMA amostra: 60.30%; alguma amostra acerta (teto): 84.00%.

Nota: significância estatística não implica benefício prático. Comparações com configurações diferentes exigem interpretação cautelosa.
