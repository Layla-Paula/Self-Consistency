from codigo.utils import consultar_ollama
from codigo.self_consistency.votacao import voto_majoritario


def executar_experimento_self_consistency(
    prompt,
    extrair_resposta,
    n_amostras=5,
    temperature=0.7,
    num_predict=800
):
    respostas_brutas = []
    respostas_extraidas = []

    for i in range(n_amostras):
        resposta_completa = consultar_ollama(
            prompt=prompt,
            temperature=temperature,
            num_predict=num_predict
        )

        resposta_extraida = extrair_resposta(
            resposta_completa
        )

        respostas_brutas.append(
            {
                "amostra": i + 1,
                "resposta_completa": resposta_completa,
                "resposta_extraida": resposta_extraida
            }
        )

        respostas_extraidas.append(
            resposta_extraida
        )

    resposta_final, votos, distribuicao = voto_majoritario(
        respostas_extraidas
    )

    return {
        "respostas_extraidas": respostas_extraidas,
        "distribuicao_votos": distribuicao,
        "resposta_modelo": resposta_final,
        "votos_resposta_modelo": votos,
        "amostras": respostas_brutas
    }