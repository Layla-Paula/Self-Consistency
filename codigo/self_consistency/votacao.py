from collections import Counter



# VOTAÇÃO MAJORITÁRIA


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
            "houve_empate": False,
            "total_respostas_validas": 0
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

    if houve_empate:
        vencedora = ""
    else:
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
        ),

        "total_respostas_validas": (
            len(respostas_validas)
        )
    }