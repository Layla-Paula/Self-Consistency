# Avaliação experimental — censo

## Arquivos analisados

- Few-shot: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\few_shot\censo\limite_todos_exemplos_6\few_shot_censo_01112026_111329_820.json`
- CoT: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\chain_of_thought\censo\limite_todos_exemplos_12\chain_of_thought_censo_28102026_144236_101.json`
- SC: `C:\Users\lahyl\OneDrive\Documentos\Self-Consistency\resultados\self_consistency\censo\limite_todos_exemplos_6\self_consistency_censo_06112026_165221_362.json`

**ATENÇÃO — execuções NÃO comparáveis:** questões diferentes: Few-shot=44, CoT=38, SC=44; parâmetro "quantidade_exemplos" difere; parâmetro "ids_exemplos" difere; parâmetro "maximo_tokens_resposta" difere

## Avisos de comparabilidade

- Few-shot: 7 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- CoT: 4 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- SC: 12 candidatas; selecionada a mais recente. Verifique se pertence à condição experimental pretendida.
- As técnicas não usaram exatamente as mesmas questões. Comparações pareadas usam a interseção.
- Parâmetro diferente: quantidade_exemplos — Few-shot=6; CoT=12; SC=6
- Parâmetro diferente: ids_exemplos — Few-shot=['censo_2025_04', 'censo_2025_12', 'censo_2025_21', 'censo_2025_30', 'censo_2025_39', 'censo_2025_47']; CoT=['censo_2025_04', 'censo_2025_12', 'censo_2025_21', 'censo_2025_30', 'censo_2025_39', 'censo_2025_47', 'censo_2025_05', 'censo_2025_13', 'censo_2025_20', 'censo_2025_31', 'censo_2025_40', 'censo_2025_46']; SC=['censo_2025_04', 'censo_2025_12', 'censo_2025_21', 'censo_2025_30', 'censo_2025_39', 'censo_2025_47']
- Parâmetro diferente: maximo_tokens_resposta — Few-shot=1200; CoT=1200; SC=2400
- Parâmetro diferente: temperatura — Few-shot=0.0; CoT=0.0; SC=0.5
- Parâmetro diferente: n_amostras — Few-shot=None; CoT=None; SC=5
- Tempo é comparável apenas com hardware e carga de máquina equivalentes; diferenças de temperatura podem confundir o efeito da técnica.

## Acurácia

| Técnica | Planejadas | N sem falha | Acertos | Pendentes | Acurácia | IC Wilson 95% | Acertos / planejadas | Falhas técnicas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Few-shot | 44 | 44 | 9 | 0 | 20.45% | 11.15% a 34.50% | 20.45% | 0 |
| CoT | 38 | 38 | 12 | 0 | 31.58% | 19.08% a 47.46% | 31.58% | 0 |
| SC | 44 | 32 | 1 | 10 | faixa 3.12% a 34.38% | não se aplica | 2.27% | 12 |

"Faixa" = mínimo e máximo enquanto há revisão humana pendente; NÃO é intervalo de confiança. "Acertos / planejadas" conta falha técnica e pendência como não acerto.

## Comparações pareadas — McNemar exato

| Par | N comum | Diferença (pp) | Só A | Só B | p bicaudal |
| --- | --- | --- | --- | --- | --- |
| Few-shot × CoT | 38 | 7.89 | 2 | 5 | 0.45312 |
| CoT × SC | 16 | -18.75 | 3 | 0 | 0.25000 |
| Few-shot × SC | 22 | -13.64 | 3 | 0 | 0.25000 |

## Custo computacional

| Técnica | Tempo médio (s) | N tempo | Tokens entrada | Tokens saída |
| --- | --- | --- | --- | --- |
| Few-shot | 118.79 | 44 | 18247.05 | 738.86 |
| CoT | 231.40 | 38 | 18631.58 | 638.26 |
| SC | 857.94 | 44 | 81969.43 | 3388.68 |

## Custo-benefício (ganho pareado)

| Comparação | Ganho (pp) | Tempo adicional (s) | N tempo pareado | Multiplicador tempo | pp/s adicional | Tokens adicionais | pp/1000 tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| few_shot → self_consistency | -13.64 | 564.22 | 22 | 7.32 | -0.0242 | 77926 | -0.1750 |
| chain_of_thought → self_consistency | -18.75 | 398.43 | 16 | 2.71 | -0.0471 | 74979 | -0.2501 |

## Falhas

| Técnica | Falhas técnicas | Respostas vazias | Limite de tokens | Amostras sem extração / total |
| --- | --- | --- | --- | --- |
| Few-shot | 0 | 20 | 0 | 0/0 |
| CoT | 0 | 10 | 0 | 0/0 |
| SC | 12 | 12 | 0 | 79/191 |

## Self-Consistency — primeiras k amostras

Censo exige avaliação semântica e revisão humana.

Nota: significância estatística não implica benefício prático. Comparações com configurações diferentes exigem interpretação cautelosa.
