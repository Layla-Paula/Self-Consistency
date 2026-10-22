
"""Convenções compartilhadas para seleção, parâmetros e armazenamento."""

from datetime import datetime
from pathlib import Path
import hashlib
import json
import random

SEMENTE_EXEMPLOS = 42

VERSAO_PROTOCOLO = '2.2'

# Omissão do argumento: utiliza o limite configurado aqui.
# None explícito: avalia todas as questões elegíveis.
USAR_LIMITE_PADRAO = object()

LIMITES_PADRAO = {'gsm8k': 500, 
                  'aqua_rat': 500, 
                  'censo': 30}

def resolver_limite(dataset, limite=USAR_LIMITE_PADRAO):
    if dataset not in LIMITES_PADRAO:
        raise ValueError(f'Dataset desconhecido: {dataset}')
    if limite is USAR_LIMITE_PADRAO:
        limite = LIMITES_PADRAO[dataset]
    if limite is not None and (isinstance(limite, bool) or not isinstance(limite, int) or limite < 1):
        raise ValueError('O limite deve ser None ou inteiro positivo.')
    return limite

N_EXEMPLOS_PADRAO = {'gsm8k': 10, 
                     'aqua_rat': 10, 
                     'censo': 5}

#LIMITES_PADRAO = {'gsm8k': None, 
#                  'aqua_rat': None, 
#                  'censo': None}

BLOCOS_CENSO = [(1, 8), (9, 16), (17, 25), (26, 35), (36, 43), (44, 50)]

def ordem_exemplos_censo(registros):
    blocos = []
    for inicio, fim in BLOCOS_CENSO:
        posicoes = list(range(inicio - 1, min(fim, len(registros))))
        centro = (inicio + fim - 2) / 2
        posicoes.sort(key=lambda i: (abs(i - centro), i))
        blocos.append(posicoes)
    ordem = []
    for rodada in range(max(map(len, blocos), default=0)):
        for bloco in blocos:
            if rodada < len(bloco):
                ordem.append(bloco[rodada])
    ordem.extend(range(min(50, len(registros)), len(registros)))
    return ordem

def selecionar_exemplos_comuns(dataset, registros, quantidade):
    from codigo.utils import (montar_questao_gsm8k, montar_questao_aqua_rat,
                              extrair_gabarito_gsm8k, extrair_gabarito_aqua_rat)
    if not isinstance(quantidade, int) or isinstance(quantidade, bool) or quantidade < 1:
        raise ValueError('Quantidade de exemplos inválida.')
    if dataset == 'censo':
        if quantidade >= len(registros):
            raise ValueError('O Censo precisa ter questões fora das demonstrações.')
        exemplos = [registros[i] for i in ordem_exemplos_censo(registros)[:quantidade]]
        if any(not str(e.get('resposta_esperada') or '').strip() for e in exemplos):
            raise ValueError('Exemplo Censo sem resposta_esperada.')
        if any(not str(e.get('raciocinio') or '').strip() for e in exemplos):
            raise ValueError('Exemplo Censo sem raciocinio; necessário para CoT e SC.')
        return exemplos
    exemplos, vistos = [], set()
    for q in registros:
        if q.get('split') != 'train':
            continue
        identificador = str(q.get('id') or '')
        if not identificador or identificador in vistos:
            continue
        try:
            if dataset == 'gsm8k':
                montar_questao_gsm8k(q)
                if not extrair_gabarito_gsm8k(q):
                    continue
                if not str(q.get('answer_pt') or q.get('answer_en') or q.get('answer') or '').strip():
                    continue
            elif dataset == 'aqua_rat':
                montar_questao_aqua_rat(q)
                if not extrair_gabarito_aqua_rat(q):
                    continue
                if not str(q.get('rationale_pt') or '').strip() or q.get('revisao_necessaria') is True:
                    continue
            else:
                raise ValueError(f'Dataset desconhecido: {dataset}')
        except (ValueError, KeyError, TypeError):
            continue
        exemplos.append(q)
        vistos.add(identificador)
    if len(exemplos) < quantidade:
        raise ValueError(f'Apenas {len(exemplos)} exemplos elegíveis de {quantidade}.')
    # Ordenação por ID impede diferenças se a ordem de leitura do JSON mudar.
    exemplos.sort(key=lambda q: str(q['id']))
    gerador = random.Random(SEMENTE_EXEMPLOS)
    return gerador.sample(exemplos, quantidade)

def pasta_configuracao(tecnica, dataset, limite, quantidade):
    pasta = Path('resultados') / tecnica / dataset / f"limite_{'todos' if limite is None else limite}_exemplos_{quantidade}"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta

def novo_nome(tecnica, dataset, pasta):
    base = f'{tecnica}_{dataset}_{datetime.now().strftime("%d%m%Y_%H%M%S_%f")[:-3]}'
    candidato, indice = base, 2
    while (pasta / f'{candidato}.json').exists() or (pasta / f'{candidato}.progresso.json').exists():
        candidato = f'{base}_{indice}'
        indice += 1
    return candidato

def resumo_protocolo(dataset, exemplos, questoes, limite, quantidade):
    ids_exemplos = [str(q['id']) for q in exemplos]
    ids_questoes = [str(q['id']) for q in questoes]
    assinatura = hashlib.sha256(json.dumps(ids_questoes, ensure_ascii=False).encode()).hexdigest()
    return {'versao': VERSAO_PROTOCOLO, 'dataset': dataset,
            'split_censo': None if dataset == 'censo' else 'splits_originais',
            'criterio_censo': 'avaliacao_propria_sem_split' if dataset == 'censo' else None,
            'limite': limite, 'quantidade_exemplos': quantidade,
            'ids_exemplos': ids_exemplos, 'ids_questoes': ids_questoes,
            'sha256_ids_questoes': assinatura,
            'selecao': ('blocos_tematicos_censo' if dataset == 'censo'
                        else 'pseudoaleatoria_treino_sem_reposicao'),
            'semente_exemplos': None if dataset == 'censo' else SEMENTE_EXEMPLOS,
            'ordem_avaliacao': 'ordem_original_apos_excluir_demonstracoes'}
