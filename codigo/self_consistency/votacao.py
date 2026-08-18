from collections import Counter


# ============================================================
# VOTAÇÃO MAJORITÁRIA
# ============================================================

def voto_majoritario(respostas):

    respostas_validas = [
        resposta
        for resposta in respostas
        if resposta not in [
            "",
            None
        ]
    ]

    if not respostas_validas:

        return {
            "vencedora": "",
            "votos": 0,
            "distribuicao": {},
            "houve_empate": False
        }

    contagem = Counter(
        respostas_validas
    )

    maior_numero_votos = max(
        contagem.values()
    )

    vencedoras = [
        resposta
        for resposta, votos
        in contagem.items()
        if votos == maior_numero_votos
    ]

    houve_empate = (
        len(vencedoras) > 1
    )

    # Mantemos a primeira resposta mais frequente
    # para garantir que sempre exista uma saída final.
    vencedora = vencedoras[0]

    return {
        "vencedora": vencedora,

        "votos": (
            maior_numero_votos
        ),

        "distribuicao": dict(
            contagem
        ),

        "houve_empate": (
            houve_empate
        )
    }