"""Cinco gerações independentes, métricas e votação para Self-Consistency."""
import time
from codigo.utils import consultar_ollama, normalizar_numero, SEMENTE_OLLAMA
from codigo.self_consistency.votacao import voto_majoritario


def executar_experimento_self_consistency(
    prompt, extrair_resposta, n_amostras=5, temperature=0.7,
    num_predict=1200, normalizar_voto=None, selecionar_votacao=None,
    consultar_modelo=None, semente_base=SEMENTE_OLLAMA,
):
    """Cada geração tem até três tentativas de transporte feitas em utils.

    Se uma geração falhar tecnicamente, a questão inteira fica incompleta,
    sem votação sobre menos amostras que o planejado.

    Cada amostra usa uma semente própria (semente_base + número da amostra).
    Com a mesma semente, o Ollama repete o mesmo texto, e as 5 amostras seriam iguais.
    """
    if not isinstance(n_amostras, int) or isinstance(n_amostras, bool) or n_amostras < 1:
        raise ValueError('n_amostras deve ser inteiro positivo.')
    consultar_modelo = consultar_modelo or consultar_ollama
    amostras, respostas = [], []
    inicio = time.perf_counter()
    for indice in range(1, n_amostras + 1):
        info = consultar_modelo(
            prompt=prompt, temperature=temperature,
            num_predict=num_predict, retornar_metricas=True,
            seed=semente_base + indice,
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
            'semente': semente_base + indice,
            'resposta_completa': texto,
            'consultas_censo': info.get('consultas_censo', []),
            'texto_descartado': info.get('texto_descartado', ''),
            'transcricoes_censo': info.get('transcricoes_censo', []),
            'motivo_encerramento_censo': info.get('motivo_encerramento_censo'),
            'consultas_repetidas_bloqueadas': info.get('consultas_repetidas_bloqueadas', 0),
            'rodadas_censo': info.get('rodadas_censo', 0),
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
            'cpu_ollama_percentual': info.get('cpu_ollama_percentual'),
            'ram_ollama_pico_mib': info.get('ram_ollama_pico_mib'),
            'ram_ollama_media_mib': info.get('ram_ollama_media_mib'),
            'amostras_monitoramento': info.get('amostras_monitoramento', 0),
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
        'cpu_ollama_percentual': (round(sum(a['cpu_ollama_percentual'] for a in amostras if a['cpu_ollama_percentual'] is not None) / sum(a['cpu_ollama_percentual'] is not None for a in amostras), 2) if any(a['cpu_ollama_percentual'] is not None for a in amostras) else None),
        'ram_ollama_pico_mib': max((a['ram_ollama_pico_mib'] for a in amostras if a['ram_ollama_pico_mib'] is not None), default=None),
        'ram_ollama_media_mib': (round(sum(a['ram_ollama_media_mib'] for a in amostras if a['ram_ollama_media_mib'] is not None) / sum(a['ram_ollama_media_mib'] is not None for a in amostras), 2) if any(a['ram_ollama_media_mib'] is not None for a in amostras) else None),
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
