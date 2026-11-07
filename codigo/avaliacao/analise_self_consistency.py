"""Análise complementar das amostras da Self-Consistency, sem inferência.

Requer registros de questões com 'amostras' e 'gabarito'. Resultados do Censo
não são corrigidos automaticamente por igualdade textual.
"""
from codigo.self_consistency.votacao import normalizar_voto_gsm8k, voto_majoritario
from codigo.utils import comparar_numeros


def votar(respostas, dataset):
    """Usa a MESMA votação dos experimentos (votacao.voto_majoritario); empate = primeira geração."""
    normalizador = normalizar_voto_gsm8k if dataset == 'gsm8k' else (lambda x: str(x).strip().upper())
    v = voto_majoritario(list(respostas), normalizador)
    return {'resposta': v['vencedora'] or None, 'votos': v['votos'], 'empate': v['houve_empate'],
            'validas': v['total_respostas_validas']}


def _certa(resposta, gabarito, dataset):
    if not resposta or not str(resposta).strip():
        return False
    if dataset == 'aqua_rat':
        return str(resposta).strip().upper() == str(gabarito).strip().upper()
    return bool(comparar_numeros(str(resposta), str(gabarito)))


def analisar(execucao):
    """Avalia as primeiras k amostras nas mesmas questões completas para cada k."""
    if execucao['tecnica'] != 'self_consistency':
        return None
    dataset = execucao['dataset']
    if dataset not in ('gsm8k', 'aqua_rat'):
        return {'disponivel': False, 'motivo': 'Censo exige avaliação semântica e revisão humana.'}
    questoes = [q for q in execucao['questoes'] if not q.get('falha_tecnica')]
    com_amostras = [q for q in questoes if isinstance(q.get('amostras'), list) and q['amostras']]
    if not com_amostras:
        return {'disponivel': False, 'motivo': 'Nenhuma amostra registrada.'}
    maximo = max(len(q['amostras']) for q in com_amostras)
    linhas = []
    for k in range(1, maximo + 1):
        elegiveis = [q for q in com_amostras if len(q['amostras']) >= k]
        acertos = empates = sem_voto = 0
        for q in elegiveis:
            respostas = [a.get('resposta_extraida') for a in q['amostras'][:k]]
            voto = votar(respostas, dataset)
            acertos += _certa(voto['resposta'], q.get('gabarito'), dataset)
            empates += voto['empate']
            sem_voto += voto['resposta'] is None
        n = len(elegiveis)
        linhas.append({'k': k, 'questoes': n, 'acertos': acertos,
                       'acuracia': acertos / n if n else None,
                       'empates': empates, 'sem_voto': sem_voto})
    unicas = [_certa(a.get('resposta_extraida'), q.get('gabarito'), dataset)
              for q in com_amostras for a in q['amostras']]
    teto = sum(any(_certa(a.get('resposta_extraida'), q.get('gabarito'), dataset) for a in q['amostras'])
               for q in com_amostras)
    usadas = {id(q) for q in com_amostras}
    excluidas = [q['id'] for q in execucao['questoes'] if id(q) not in usadas]
    tamanhos = sorted({len(q['amostras']) for q in com_amostras})
    # Curva principal: MESMO conjunto de questões para todo k.
    # O valor máximo observado só é elegível para questões com todas as amostras.
    completas = [q for q in com_amostras if len(q['amostras']) == maximo]
    curva_fixa = []
    for k in range(1, maximo + 1):
        acertos = empates = 0
        for q in completas:
            voto = votar([a.get('resposta_extraida') for a in q['amostras'][:k]], dataset)
            acertos += _certa(voto['resposta'], q.get('gabarito'), dataset)
            empates += voto['empate']
        curva_fixa.append({'k': k, 'questoes': len(completas), 'acertos': acertos,
                           'acuracia': acertos / len(completas) if completas else None,
                           'empates': empates})
    return {'disponivel': True, 'questoes_sem_falha': len(questoes),
            'questoes_planejadas': len(execucao['questoes']),
            'questoes_excluidas': excluidas, 'amostras_por_questao': tamanhos,
            'completo': not excluidas and len(tamanhos) == 1,
            'acuracia_amostra_unica_media': sum(unicas) / len(unicas),
            'acuracia_qualquer_amostra_certa': teto / len(com_amostras),
            'questoes_com_amostras': len(com_amostras), 'por_k': linhas,
             'por_k_mesmas_questoes': curva_fixa, 'n_curva_fixa': len(completas),
            'observacao': 'Cada k usa questões com pelo menos k amostras; N pode variar.'}
