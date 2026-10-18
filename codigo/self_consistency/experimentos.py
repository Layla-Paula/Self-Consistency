"""Executa várias gerações do mesmo prompt e aplica votação majoritária."""
from codigo.utils import consultar_ollama
from codigo.self_consistency.votacao import voto_majoritario


def executar_experimento_self_consistency(prompt, extrair_resposta, n_amostras=5, temperature=0.7, num_predict=800):
    if not isinstance(n_amostras, int) or n_amostras < 1:
        raise ValueError('n_amostras deve ser um inteiro positivo.')
    amostras = []
    respostas = []
    for indice in range(n_amostras):
        completa = consultar_ollama(prompt=prompt, temperature=temperature, num_predict=num_predict)
        try:
            extraida = extrair_resposta(completa) if completa else None
        except (ValueError, TypeError, AttributeError):
            extraida = None
        amostras.append({'amostra': indice + 1, 'resposta_completa': completa, 'resposta_extraida': extraida})
        respostas.append(extraida)
    votacao = voto_majoritario(respostas)
    return {
        'respostas_extraidas': respostas,
        'distribuicao_votos': votacao['distribuicao'],
        'resposta_modelo': votacao['vencedora'],
        'votos_resposta_modelo': votacao['votos'],
        'houve_empate': votacao['houve_empate'],
        'total_respostas_validas': votacao['total_respostas_validas'],
        'amostras': amostras,
    }