"""Execução Self-Consistency: GSM8K, AQuA-RAT e Censo Escolar.
"""
from codigo.agente_censo import consultar_censo_agente
import json
import os
import re
import statistics
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
from codigo.protocolo_experimentos import (
    selecionar_exemplos_comuns, pasta_configuracao, novo_nome, resumo_protocolo,
    N_EXEMPLOS_PADRAO, ordem_exemplos_censo,
    USAR_LIMITE_PADRAO, resolver_limite
)
from codigo.utils import (
    carregar_gsm8k, carregar_aqua_rat, carregar_censo, consultar_ollama,
    extrair_gabarito_gsm8k, extrair_gabarito_aqua_rat,
    extrair_gabarito_censo, extrair_resposta_numerica,
    extrair_letra_resposta, comparar_numeros,
    montar_questao_gsm8k, montar_questao_aqua_rat,
    normalizar_numero,
)
from codigo.self_consistency.prompts import (
    prompt_self_consistency_gsm8k, prompt_self_consistency_aqua_rat,
    prompt_self_consistency_censo,
)
from codigo.self_consistency.experimentos import executar_experimento_self_consistency
from codigo.self_consistency.votacao import voto_censo_semantico
try:
    import psutil
except ImportError:
    psutil = None

from codigo.utils import MODELO_OLLAMA, SEMENTE_OLLAMA
MODELO = MODELO_OLLAMA
TEMPERATURE = 0.7
NUM_PREDICT = 1200
N_AMOSTRAS = 5
SALVAR_CADA = 10
PASTA_BASE = Path("resultados/self_consistency")

from codigo.avaliacao.avaliacao_censo import avaliar_censo

def agora():
    return datetime.now().isoformat(timespec='seconds')


def salvar(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix('.tmp')
    with temporario.open('w', encoding='utf-8') as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)


def recursos():
    if psutil is None:
        return {'cpu_percentual': None, 'ram_percentual': None}
    return {'cpu_percentual': psutil.cpu_percent(interval=None),
            'ram_percentual': psutil.virtual_memory().percent}


def selecionar_exemplos(dataset, registros, quantidade):
    return selecionar_exemplos_comuns(dataset, registros, quantidade)

def metricas(resultados, tempo_total, quantidade, dataset):
    avaliadas = [r for r in resultados if not r.get('falha_tecnica', False)
                 and isinstance(r.get('acertou'), bool)]
    falhas = [r for r in resultados if r.get('falha_tecnica', False)]
    pendentes_avaliacao = [r for r in resultados if not r.get('falha_tecnica', False) and r.get('acertou') is None]
    def acuracia(itens):
        return round(100 * sum(r['acertou'] for r in itens) / len(itens), 2) if itens else None
    def media(chave):
        valores = [r[chave] for r in avaliadas
                   if isinstance(r.get(chave), (int, float))]
        return round(statistics.mean(valores), 2) if valores else None
    por_split = {}
    if dataset != 'censo':
        for split in ('train', 'validation', 'test'):
            itens = [r for r in avaliadas if r.get('split') == split]
            if itens:
                por_split[split] = {
                    'questoes': len(itens),
                    'acertos': sum(r['acertou'] for r in itens),
                    'erros': sum(not r['acertou'] for r in itens),
                    'acuracia_percentual': acuracia(itens),
                }
    votos = [r for r in avaliadas if 'votos_resposta_modelo' in r]
    return {
        'exemplos_utilizados': quantidade,
        'amostras_por_questao': N_AMOSTRAS,
        'votacao_censo': 'equivalencia_deterministica_ou_selecao_semantica_cega',
        'questoes_executadas': len(resultados),
        'questoes_avaliadas': len(avaliadas),
        'acertos': sum(r['acertou'] for r in avaliadas),
        'erros': sum(not r['acertou'] for r in avaliadas),
        'falhas_tecnicas': len(falhas),
        'avaliacoes_pendentes': len(pendentes_avaliacao),
        'detalhes_falhas_tecnicas': [
            {'id': r['id'], 'motivo': r.get('motivo'),
             'amostras_realizadas': len(r.get('amostras', [])),
             'tentativas': [a.get('tentativas_consulta') for a in r.get('amostras', [])]}
            for r in falhas
        ],
        'acuracia_percentual': acuracia(avaliadas),
        'acuracia_por_split': por_split,
        'respostas_sem_extracao': sum(r.get('total_respostas_validas', 0) < N_AMOSTRAS
                                     for r in avaliadas),
        'questoes_com_amostras_invalidas': sum(any(not a.get('resposta_extraida') and not a.get('falha_tecnica')
                                                   for a in r.get('amostras', [])) for r in avaliadas),
        'amostras_sem_extracao': sum(sum(not a.get('resposta_extraida') and not a.get('falha_tecnica')
                                        for a in r.get('amostras', [])) for r in avaliadas),
        'amostras_limite_tokens': sum(sum(a.get('limite_tokens_atingido', False)
                                       for a in r.get('amostras', [])) for r in avaliadas),
        'questoes_com_limite_tokens': sum(any(a.get('limite_tokens_atingido', False)
                                              for a in r.get('amostras', [])) for r in avaliadas),
        'questoes_sem_vencedor': sum(not r.get('resposta_modelo') for r in avaliadas),
        'questoes_maioria_incorreta': sum(bool(r.get('resposta_modelo')) and not r['acertou']
                                         for r in avaliadas),
        'questoes_empate': sum(bool(r.get('houve_empate')) for r in avaliadas),
        'ids_questoes_sem_vencedor': [r['id'] for r in avaliadas if not r.get('resposta_modelo')],
        'ids_questoes_maioria_incorreta': [r['id'] for r in avaliadas
                                          if r.get('resposta_modelo') and not r['acertou']],
        'ids_questoes_com_limite_tokens': [r['id'] for r in avaliadas
                                           if any(a.get('limite_tokens_atingido', False)
                                                  for a in r.get('amostras', []))],
        'revisoes_necessarias': sum(bool(r.get('revisao_necessaria')) for r in resultados),
        'tempo_total_segundos': round(tempo_total, 2),
        'tempo_medio_segundos': media('tempo_segundos'),
        'tokens_entrada': sum(r.get('tokens_entrada') or 0 for r in avaliadas),
        'tokens_saida': sum(r.get('tokens_saida') or 0 for r in avaliadas),
        'cpu_ollama_media_percentual': media('cpu_ollama_percentual'),
        'ram_ollama_pico_mib': max((r['ram_ollama_pico_mib'] for r in avaliadas if r.get('ram_ollama_pico_mib') is not None), default=None),
        'ram_ollama_media_mib': media('ram_ollama_media_mib'),
        'metricas_votacao': {
            'unanimidades': sum(r['votos_resposta_modelo'] == N_AMOSTRAS for r in votos),
            'empates': sum(r['houve_empate'] for r in votos),
            'sem_resposta_valida': sum(r['total_respostas_validas'] == 0 for r in votos),
            'media_votos_vencedor': (round(statistics.mean(
                r['votos_resposta_modelo'] for r in votos if isinstance(r['votos_resposta_modelo'], int)), 2)
                if any(isinstance(r['votos_resposta_modelo'], int) for r in votos) else None),
        },
    }


def identificador_novo(dataset, limite, quantidade):
    pasta = pasta_configuracao("self_consistency", dataset, limite, quantidade)
    return novo_nome("self_consistency", dataset, pasta)

def tempo_legivel(segundos):
    horas, resto = divmod(round(segundos), 3600)
    minutos, segundos = divmod(resto, 60)
    return (f'{horas}h {minutos}min {segundos}s' if horas
            else f'{minutos}min {segundos}s')


def mostrar_resumo(dataset, dados, caminho):
    m = dados['metricas']
    print(f'\n{dataset.upper()} | Self-Consistency')
    print(f"Questões executadas: {m['questoes_executadas']}")
    print(f"Questões avaliadas: {m['questoes_avaliadas']}")
    print(f"Exemplos utilizados: {m['exemplos_utilizados']}")
    print(f"Acertos: {m['acertos']}")
    print(f"Erros: {m['erros']}")
    print(f"Falhas técnicas: {m['falhas_tecnicas']}")
    print(f"Amostras sem extração: {m['amostras_sem_extracao']}")
    print(f"Amostras interrompidas pelo limite de tokens: {m['amostras_limite_tokens']}")
    print(f"Questões com empate: {m['questoes_empate']}")
    print(f"Questões sem resposta vencedora: {m['questoes_sem_vencedor']}")
    print(f"Questões com vencedora incorreta: {m['questoes_maioria_incorreta']}")
    print(f"Avaliações pendentes: {m.get('avaliacoes_pendentes', 0)}")
    a = m['acuracia_percentual']
    print(f'Acurácia: {a:.2f}%' if a is not None else 'Acurácia: indisponível')
    print(f"Tempo de execução: {tempo_legivel(m['tempo_total_segundos'])}")
    print(f'Resultados salvos em: {caminho}')


def executar_dataset(dataset, limite=USAR_LIMITE_PADRAO, n_exemplos=None, retomar=None):
    carregadores = {'gsm8k': carregar_gsm8k,
                    'aqua_rat': carregar_aqua_rat, 'censo': carregar_censo}
    if dataset not in carregadores:
        raise ValueError(f'Dataset desconhecido: {dataset}')
    limite = resolver_limite(dataset, limite)
    quantidade = N_EXEMPLOS_PADRAO[dataset] if n_exemplos is None else n_exemplos
    registros = carregadores[dataset](split=None)
    ids = [str(q.get('id', '')) for q in registros]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError('Há IDs ausentes ou duplicados no dataset.')
    exemplos = selecionar_exemplos(dataset, registros, quantidade)
    ids_exemplos = {str(q['id']) for q in exemplos}
    questoes_disponiveis = [q for q in registros if str(q['id']) not in ids_exemplos]
    questoes = (questoes_disponiveis[:limite]
               if limite is not None else questoes_disponiveis)
    if not questoes:
        raise ValueError('Nenhuma questão disponível após excluir demonstrações.')
    sessao, contextos_exemplos, raciocinios_exemplos = None, None, None
    if dataset == 'censo':
        from codigo.consulta_censo import SessaoCenso, verificar_consultas
        verificar_consultas(exemplos + questoes)
        sessao = SessaoCenso()
        contextos_exemplos = {str(q['id']): "Consulte a tabela matriculas por SQL." for q in exemplos}
        raciocinios_exemplos = {str(q['id']): str(q['raciocinio']).strip()
                                for q in exemplos}
    pasta = pasta_configuracao("self_consistency", dataset, limite, quantidade)
    nome = (Path(retomar).name.removesuffix('.progresso.json') if retomar
            else identificador_novo(dataset, limite, quantidade))
    caminho = pasta / f'{nome}.json'
    progresso = pasta / f'{nome}.progresso.json'
    parametros = {
        'modelo': MODELO, 'seed': SEMENTE_OLLAMA, 'temperatura': TEMPERATURE,
        'limite': limite, 'maximo_tokens_resposta': NUM_PREDICT,
        'quantidade_exemplos': quantidade, 'n_amostras': N_AMOSTRAS,
        'ids_exemplos': [str(q['id']) for q in exemplos],
        'ids_questoes': [str(q['id']) for q in questoes],
        'criterio_avaliacao': 'todos_splits_sem_demonstracoes',
        'tipo_demonstracao': 'questao_raciocinio_resposta',
        'votacao_censo': 'seletor_semantico_sem_gabarito_v1' if dataset == 'censo' else 'frequencia_simples',
        'origem_raciocinios_censo': 'json_preparado' if dataset == 'censo' else None,
        'versao_prompt_aqua_rat': 'curto_com_resposta_prioritaria_v4' if dataset == 'aqua_rat' else None,
    }
    if dataset == 'censo':
        parametros['arquitetura_censo'] = 'agente_sql_direto_v1_max_5_consultas'
    parametros['protocolo'] = resumo_protocolo(dataset, exemplos, questoes, limite, quantidade)
    parametros['top_k'] = 40
    parametros['top_p'] = 0.9
    parametros['num_ctx'] = 8192
    if retomar:
        with progresso.open('r', encoding='utf-8') as arquivo:
            dados = json.load(arquivo)
        if dados['parametros'] != parametros:
            raise ValueError('Os parâmetros atuais diferem do checkpoint.')
        resultados = dados['resultados']
    else:
        resultados = []
        dados = {
            'id_execucao': nome, 'tecnica': 'self_consistency',
            'dataset': dataset, 'data_inicio': agora(),
            'parametros': parametros, 'resultados': resultados,
            'status': 'em_andamento',
        }
    concluidos = {str(r['id']) for r in resultados}
    if len(concluidos) != len(resultados):
        raise ValueError('Checkpoint contém questões duplicadas.')
    pendentes = [q for q in questoes if str(q['id']) not in concluidos]
    tempo_anterior = dados.get('tempo_acumulado_segundos', 0.0)
    inicio = time.perf_counter()
    print(f'\n{dataset.upper()} | {len(questoes)} questões | '
          f'{quantidade} exemplos | {N_AMOSTRAS} amostras/questão')

    def checkpoint():
        total = tempo_anterior + time.perf_counter() - inicio
        dados['tempo_acumulado_segundos'] = total
        dados['metricas_parciais'] = metricas(resultados, total, quantidade, dataset)
        salvar(progresso, dados)

    try:
        for questao in tqdm(pendentes, desc=f'Self-Consistency {dataset}', bar_format="{desc}: {percentage:3.0f}%|{bar:16}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]", ascii=" #", mininterval=1.0, leave=True):
            if dataset == 'gsm8k':
                prompt = prompt_self_consistency_gsm8k(questao, exemplos)
                gabarito = extrair_gabarito_gsm8k(questao)
                extrair = extrair_resposta_numerica
            elif dataset == 'aqua_rat':
                prompt = prompt_self_consistency_aqua_rat(questao, exemplos)
                gabarito = extrair_gabarito_aqua_rat(questao)
                extrair = extrair_letra_resposta
            else:
                contexto = sessao.consultar(questao)
                prompt = prompt_self_consistency_censo(
                    questao, contexto, exemplos, contextos_exemplos,
                    raciocinios_exemplos,
                )
                gabarito = extrair_gabarito_censo(questao)
                extrair = extrair_resposta_final_censo
            sc = executar_experimento_self_consistency(
                prompt, extrair, n_amostras=N_AMOSTRAS,
                temperature=TEMPERATURE, num_predict=NUM_PREDICT,
                normalizar_voto=(normalizar_voto_gsm8k if dataset == 'gsm8k' else None),
                consultar_modelo=((lambda **kwargs: consultar_censo_agente(
                    sessao=sessao, **kwargs)) if dataset == 'censo' else None),
                semente_base=SEMENTE_OLLAMA,
                selecionar_votacao=(
                    (lambda respostas: voto_censo_semantico(
                        str(questao.get('pergunta') or questao.get('enunciado') or ''),
                        respostas, consultar_ollama)) if dataset == 'censo' else None),
            )
            if sc['falha_tecnica']:
                acertou = None
                motivo = sc['motivo_falha_tecnica']
                metodo = 'falha_tecnica_consulta'
                revisao = False
            elif dataset == 'gsm8k':
                acertou = (comparar_numeros(sc['resposta_modelo'], gabarito)
                           if sc['resposta_modelo'] else False)
                motivo = None if acertou else 'Resposta incorreta ou ausência de resposta válida.'
                metodo = 'comparacao_exata'
                revisao = False
            elif dataset == 'aqua_rat':
                acertou = (sc['resposta_modelo'] == gabarito
                           if sc['resposta_modelo'] else False)
                motivo = None if acertou else 'Resposta incorreta ou ausência de resposta válida.'
                metodo = 'comparacao_exata'
                revisao = False
            else:
                # Avalia a resposta vencedora; empate ou ausência de voto é erro,
                # não falha de transporte. A avaliação semântica é automática.
                if not sc['resposta_modelo']:
                    acertou = False
                    motivo = 'Nenhuma resposta final extraída.'
                    metodo = 'votacao_sem_vencedor'
                    revisao = False
                else:
                    avaliacao = avaliar_censo(questao, sc['resposta_modelo'], consultar_ollama)
                    acertou = avaliacao['acertou']
                    motivo = avaliacao['motivo']
                    metodo = avaliacao['metodo_avaliacao']
                    revisao = bool(avaliacao.get('revisao_necessaria', acertou is None))
            resultado = {
                'id': str(questao['id']), 'split': questao.get('split'),
                'usada_como_exemplo': False, 'gabarito': gabarito,
                'resposta': sc['resposta_modelo'],
                'resposta_valida': bool(sc['resposta_modelo']),
                'acertou': acertou, 'falha_tecnica': sc['falha_tecnica'],
                'motivo': motivo, 'metodo_avaliacao': metodo,
                'revisao_necessaria': revisao, **sc,
                'tipo_resultado': ('falha_tecnica' if sc['falha_tecnica'] else
                                   'sem_vencedor' if not sc['resposta_modelo'] else
                                   'acerto' if acertou else 'vencedora_incorreta'),
            }
            # Os campos finais de avaliação prevalecem sobre metadados de sc.
            resultado.update(acertou=acertou, motivo=motivo,
                             metodo_avaliacao=metodo, falha_tecnica=sc['falha_tecnica'])
            resultados.append(resultado)
            if sc['falha_tecnica']:
                print(f"\n[FALHA TÉCNICA] {dataset}/{questao['id']}: {motivo}. Avançando.")
                checkpoint()
            elif revisao:
                print(f"\n[AVALIAÇÃO PENDENTE] {dataset}/{questao['id']}: {motivo}. Resposta preservada.")
                checkpoint()
            elif len(resultados) % SALVAR_CADA == 0:
                checkpoint()
    except BaseException:
        checkpoint()
        raise
    dados['data_fim'] = agora()
    dados['status'] = 'concluido'
    dados['tempo_acumulado_segundos'] = tempo_anterior + time.perf_counter() - inicio
    dados['metricas'] = metricas(resultados, dados['tempo_acumulado_segundos'], quantidade, dataset)
    dados.pop('metricas_parciais', None)
    salvar(caminho, dados)
    if progresso.exists():
        progresso.unlink()
    mostrar_resumo(dataset, dados, caminho)
    return dados


def normalizar_voto_gsm8k(texto):
    from codigo.self_consistency.votacao import normalizar_voto_gsm8k as normalizador
    return normalizador(texto)


def normalizar_voto_censo(texto):
    """Padroniza espaços/caixa, sem tratar respostas semanticamente diferentes como iguais."""
    return ' '.join(str(texto).casefold().split()).strip(' .;')


def extrair_resposta_final_censo(texto):
    """Retém a resposta final aberta (texto, lista ou número) sem inventar extração."""
    if not texto:
        return ''
    texto = str(texto).strip()
    match = re.search(r'(?im)^\s*resposta\s+final\s*:\s*(.*)$', texto)
    if not match:
        return ''
    resposta = (match.group(1) + texto[match.end():]).strip()
    return resposta


def executar_gsm8k(limite=USAR_LIMITE_PADRAO, n_exemplos=None, retomar=None):
    return executar_dataset('gsm8k', limite, n_exemplos, retomar)


def executar_aqua_rat(limite=USAR_LIMITE_PADRAO, n_exemplos=None, retomar=None):
    return executar_dataset('aqua_rat', limite, n_exemplos, retomar)


def executar_censo(limite=USAR_LIMITE_PADRAO, n_exemplos=None, retomar=None):
    return executar_dataset('censo', limite, n_exemplos, retomar)


if __name__ == '__main__':
    executar_gsm8k()
    executar_aqua_rat()
    executar_censo()
    
