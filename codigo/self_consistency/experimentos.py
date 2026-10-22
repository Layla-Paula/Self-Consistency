"""Cinco gerações independentes, métricas e votação para Self-Consistency."""
import time
from codigo.utils import consultar_ollama, normalizar_numero
from codigo.self_consistency.votacao import voto_majoritario


def executar_experimento_self_consistency(
    prompt, extrair_resposta, n_amostras=5, temperature=0.7,
    num_predict=800, normalizar_voto=None, selecionar_votacao=None,
):
    """Cada geração tem até três tentativas de transporte feitas em utils.

    Se uma geração falhar tecnicamente, a questão inteira fica incompleta,
    sem votação sobre menos amostras que o planejado.
    """
    if not isinstance(n_amostras, int) or isinstance(n_amostras, bool) or n_amostras < 1:
        raise ValueError('n_amostras deve ser inteiro positivo.')
    amostras, respostas = [], []
    inicio = time.perf_counter()
    for indice in range(1, n_amostras + 1):
        info = consultar_ollama(
            prompt=prompt, temperature=temperature,
            num_predict=num_predict, retornar_metricas=True,
        )
        if not isinstance(info, dict):
            info = {'resposta': None, 'tentativas': 3,
                    'erro_detalhado': 'Consulta não retornou metadados.'}
        texto = info.get('resposta')
        falha = texto is None
        try:
            extraida = extrair_resposta(texto) if texto else ''
        except (ValueError, TypeError, AttributeError):
            extraida = ''
        extraida = str(extraida or '').strip()
        if extraida and normalizar_voto is not None:
            try:
                extraida = str(normalizar_voto(extraida)).strip()
            except (ValueError, TypeError, OverflowError):
                pass
        # Uma geração concluída sem letra/número final é erro do modelo,
        # não falha de transporte. A amostra não participa da votação.
        # O Ollama informa 'length' quando para por limite de tokens.
        motivo_parada = info.get('done_reason')
        limite_tokens = motivo_parada == 'length'
        amostras.append({
            'amostra': indice,
            'resposta_completa': texto,
            'resposta_extraida': extraida,
            'resposta_valida': bool(extraida),
            'sem_extracao': not bool(extraida) and not falha,
            'limite_tokens_atingido': limite_tokens,
            'motivo_parada': motivo_parada,
            'falha_tecnica': falha,
            'tentativas_consulta': info.get('tentativas', 3),
            'erro_detalhado': info.get('erro_detalhado'),
            'tokens_entrada': info.get('prompt_eval_count'),
            'tokens_saida': info.get('eval_count'),
            'tempo_consulta_segundos': info.get('tempo_total_segundos'),
        })
        respostas.append(extraida)
        if falha:
            break
    incompleto = len(amostras) != n_amostras or any(a['falha_tecnica'] for a in amostras)
    motivo_seletor = None
    if not incompleto and selecionar_votacao is not None:
        try:
            votacao = selecionar_votacao(respostas)
        except Exception as erro:
            incompleto = True
            motivo_seletor = f'{type(erro).__name__}: {erro}'
    elif not incompleto:
        votacao = voto_majoritario(respostas)
    if incompleto:
        votacao = (
               {'vencedora': '', 'votos': 0, 'distribuicao': {},
                'houve_empate': False, 'total_respostas_validas': 0})
    return {
        'respostas_extraidas': respostas,
        'distribuicao_votos': votacao['distribuicao'],
        'resposta_modelo': votacao['vencedora'],
        'votos_resposta_modelo': votacao['votos'],
        'houve_empate': votacao['houve_empate'],
        'total_respostas_validas': votacao['total_respostas_validas'],
        'amostras': amostras,
        'amostras_sem_extracao': sum(a['sem_extracao'] for a in amostras),
        'amostras_limite_tokens': sum(a['limite_tokens_atingido'] for a in amostras),
        'falha_tecnica': incompleto,
        'motivo_falha_tecnica': motivo_seletor or next(
            (a['erro_detalhado'] or 'Falha na consulta ao Ollama'
             for a in amostras if a['falha_tecnica']), None
        ),
        'tempo_segundos': round(time.perf_counter() - inicio, 3),
        'metodo_votacao': votacao.get('metodo_votacao'),
        'detalhes_votacao': {k: v for k, v in votacao.items() if k not in ('vencedora', 'votos', 'distribuicao', 'houve_empate', 'total_respostas_validas')},
        'tokens_entrada': sum(a['tokens_entrada'] or 0 for a in amostras),
        'tokens_saida': sum(a['tokens_saida'] or 0 for a in amostras),
    }
