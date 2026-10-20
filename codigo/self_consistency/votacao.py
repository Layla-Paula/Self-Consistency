"""Votação por frequência, com empate explícito."""
from collections import Counter


def voto_majoritario(respostas):
    validas = [str(r).strip() for r in respostas if r is not None and str(r).strip()]
    if not validas:
        return {'vencedora': '', 'votos': 0, 'distribuicao': {},
                'houve_empate': False, 'total_respostas_validas': 0}
    contagem = Counter(validas)
    maior = max(contagem.values())
    vencedoras = [r for r, votos in contagem.items() if votos == maior]
    empate = len(vencedoras) > 1
    return {'vencedora': '' if empate else vencedoras[0],
            'votos': maior, 'distribuicao': dict(contagem),
            'houve_empate': empate, 'total_respostas_validas': len(validas)}
