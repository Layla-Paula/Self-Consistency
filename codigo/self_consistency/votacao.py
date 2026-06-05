from collections import Counter


def voto_majoritario(respostas):
    respostas_validas = [
        r for r in respostas
        if r not in ["", None]
    ]

    if not respostas_validas:
        return "", 0, {}

    contagem = Counter(respostas_validas)
    vencedora, votos = contagem.most_common(1)[0]

    return vencedora, votos, dict(contagem)