"""Execução Chain-of-Thought para GSM8K, AQuA-RAT e Censo, com exemplos reais.

"""
from datetime import datetime
import time
from pathlib import Path
from tqdm import tqdm

from codigo.utils import (
    carregar_gsm8k, carregar_aqua_rat, consultar_ollama,
    extrair_letra_resposta, extrair_resposta_numerica,
    extrair_gabarito_gsm8k, extrair_gabarito_aqua_rat,
    comparar_numeros, salvar_json,
)
from codigo.chain_of_thought.prompts import prompt_cot_gsm8k, prompt_cot_aqua_rat
# Reutiliza exatamente a mesma avaliação binária do Few-shot; não depende de revisao_censo.py.
from codigo.few_shot.executar_few_shot import avaliar_censo, selecionar_exemplos as selecionar_exemplos_few_shot

# CONFIGURAÇÕES
METODO = 'chain_of_thought'
MODELO = 'llama3.2'
PASTAS = {
    'gsm8k': Path('resultados/chain_of_thought/gsm8k'),
    'aqua_rat': Path('resultados/chain_of_thought/aqua_rat'),
}
TEMPERATURE = 0.0  # Reduz a aleatoriedade da geração.
NUM_PREDICT = 800   # Limita o máximo de tokens de saída.
N_EXEMPLOS = 10     # Quantidade de demonstrações para GSM8K e AQuA-RAT.
N_EXEMPLOS_CENSO = 5  # Mesma seleção temática do Few-shot; altere se necessário.


# CRIA IDENTIFICADOR DA EXECUÇÃO

def criar_id_execucao(dataset, limite, pasta, quantidade):
    """Exemplo: chain_of_thought_gsm8k_20261017_todos_1"""
    data = datetime.now().strftime('%Y%m%d')
    limite_nome = str(limite) if limite is not None else 'todos'
    prefixo = f'{METODO}_{dataset}_{data}_q{limite_nome}_ex{quantidade}_run'
    pasta.mkdir(parents=True, exist_ok=True)  # Não gera erro se já existir.
    numero_execucao = 1
    while True:  # Procura um nome que ainda não exista.
        identificador = f'{prefixo}{numero_execucao:02d}'
        if not (pasta / f'{identificador}.json').exists():
            return identificador
        numero_execucao += 1


# SELEÇÃO REPRODUZÍVEL DOS EXEMPLOS REAIS

def selecionar_exemplos(dataset, n=None):
    if n is None:
        n = N_EXEMPLOS
    if not isinstance(n, int) or n <= 0:
        raise ValueError('A quantidade de exemplos deve ser um inteiro positivo.')
    carregar = carregar_gsm8k if dataset == 'gsm8k' else carregar_aqua_rat
    candidatos = carregar(split='train')
    exemplos = []
    ids = set()
    for q in candidatos:
        identificador = str(q.get('id', '')).strip()
        if not identificador or identificador in ids:
            continue
        try:
            if dataset == 'gsm8k':
                from codigo.utils import montar_questao_gsm8k
                montar_questao_gsm8k(q)
                if not extrair_gabarito_gsm8k(q):
                    continue
                if not (q.get('answer_pt') or q.get('answer_en') or q.get('answer')):
                    continue
            else:
                from codigo.utils import montar_questao_aqua_rat
                montar_questao_aqua_rat(q)
                extrair_gabarito_aqua_rat(q)
                if not str(q.get('rationale_pt') or '').strip():
                    continue
                # A marcação ajuda a evitar exemplos já sinalizados como problemáticos.
                # Não garante qualidade semântica; revisão humana continua recomendada.
                if q.get('revisao_necessaria') is True:
                    continue
        except (ValueError, TypeError, KeyError):
            continue
        exemplos.append(q)
        ids.add(identificador)
        if len(exemplos) == n:
            break
    if len(exemplos) != n:
        raise ValueError(f'{dataset}: apenas {len(exemplos)} exemplos elegíveis no train; necessários {n}.')
    return exemplos


# EXECUÇÃO GSM8K / AQUA-RAT


def executar_dataset(dataset, limite=None, n_exemplos=None):
    if n_exemplos is None:
        n_exemplos = N_EXEMPLOS
    if dataset not in PASTAS:
        raise ValueError(f'Dataset desconhecido: {dataset}')
    if limite is not None and (not isinstance(limite, int) or limite <= 0):
        raise ValueError('limite deve ser um inteiro positivo ou None.')

    carregar = carregar_gsm8k if dataset == 'gsm8k' else carregar_aqua_rat
    exemplos = selecionar_exemplos(dataset, n=n_exemplos)
    questoes = carregar(split='test')
    if limite is not None:
        questoes = questoes[:limite]
    if not questoes:
        raise ValueError(f'Nenhuma questão encontrada para {dataset}, split=test.')

    # Proteção contra vazamento: nenhum ID do train selecionado pode estar no test.
    ids_exemplos = [str(q['id']) for q in exemplos]
    ids_teste = {str(q.get('id', '')) for q in questoes}
    if ids_teste.intersection(ids_exemplos):
        raise ValueError('Vazamento de dados: há IDs de exemplos presentes no test.')

    pasta = PASTAS[dataset]
    id_execucao = criar_id_execucao(dataset, limite, pasta, n_exemplos)
    resultados = []
    print('\n' + '=' * 60)
    print(f'{METODO.upper()} - {dataset.upper()}')
    print(f'ID da execução: {id_execucao} | Modelo: {MODELO}')
    print(f'Questões do test: {len(questoes)} | Exemplos do train: {len(exemplos)}')
    print('IDs dos exemplos:', ', '.join(ids_exemplos))
    print('=' * 60)

    for i, q in enumerate(tqdm(questoes, desc=f'Chain-of-Thought {dataset}')):
        if dataset == 'gsm8k':
            prompt = prompt_cot_gsm8k(q, exemplos)
            gabarito = extrair_gabarito_gsm8k(q)
        else:
            prompt = prompt_cot_aqua_rat(q, exemplos)
            gabarito = extrair_gabarito_aqua_rat(q)

        resposta_completa = consultar_ollama(
            prompt=prompt, temperature=TEMPERATURE,
            num_predict=NUM_PREDICT,
        )
        if dataset == 'aqua_rat':
            resposta_modelo = extrair_letra_resposta(resposta_completa)
            acertou = bool(resposta_modelo) and resposta_modelo == gabarito
        else:
            resposta_modelo = extrair_resposta_numerica(resposta_completa)
            acertou = comparar_numeros(resposta_modelo, gabarito)

        resultados.append({
            'id': q.get('id', i), 'split': q.get('split', ''),
            'gabarito': gabarito, 'resposta_modelo': resposta_modelo,
            'acertou': acertou, 'resposta_completa': resposta_completa,
            'erro_consulta': resposta_completa is None,
        })

    # MÉTRICAS
    total = len(resultados)
    acertos = sum(1 for r in resultados if r['acertou'] is True)
    erros = total - acertos
    precisao = round(acertos / total * 100, 2) if total else None

    # DADOS DA EXECUÇÃO
    dados = {
        'id_execucao': id_execucao,
        'data_execucao': datetime.now().isoformat(timespec='seconds'),
        'metodo': METODO, 'dataset': dataset, 'modelo': MODELO,
        'total': total, 'acertos': acertos, 'erros': erros,
        'precisao': precisao,
        'parametros': {
            'temperature': TEMPERATURE, 'num_predict': NUM_PREDICT,
            'limite': limite, 'split_avaliacao': 'test',
            'split_exemplos': 'train', 'n_exemplos': n_exemplos,
            'selecao_exemplos': 'primeiros_elegiveis_na_ordem_do_json',
            'tipo_demonstracao': 'questao_resolucao_resposta',
            'ids_exemplos': ids_exemplos,
        },
        'resultados': resultados,
    }

    # SALVAMENTO
    caminho = pasta / f'{id_execucao}.json'
    salvar_json(caminho, dados)

    # RESUMO
    print(f'\nSalvo: {caminho}')
    print(f'Total: {total} | Acertos: {acertos} | Erros: {erros}')
    print(f'Precisão: {precisao:.2f}%')
    return dados


# EXECUÇÃO CENSO ESCOLAR — exemplos distribuídos pelos blocos temáticos.
# Seleção idêntica à do Few-shot; cada exemplo é excluído da avaliação pelo ID.
# As resoluções CoT são geradas para as demonstrações a partir dos dados do CSV.

def criar_raciocinios_censo(exemplos, contextos):
    """Prepara uma resolução passo a passo para cada exemplo, sem usar questões de teste."""
    from codigo.utils import montar_questao_censo

    raciocinios = {}
    for exemplo in tqdm(exemplos, desc='Preparando demonstrações CoT do Censo'):
        identificador = str(exemplo['id'])
        gabarito = str(exemplo['resposta_esperada']).strip()
        contexto = contextos[identificador]
        prompt = f"""Elabore uma resolução didática, passo a passo, para esta questão já resolvida
sobre os microdados do Censo Escolar 2025. Esta resolução será uma demonstração
Chain-of-Thought para outra questão.

Use SOMENTE a pergunta, os dados fornecidos e o resultado de referência.
Identifique as variáveis relevantes, explique os cálculos, filtros e comparações
que os dados permitirem, e conclua com o resultado informado.
Não invente números, cálculos ou justificativas que não possam ser verificados
nos dados. Não copie a pergunta nem repita o gabarito inteiro como explicação.
Se o contexto não permitir justificar alguma parte, indique essa limitação.

{montar_questao_censo(exemplo, contexto)}
Resultado de referência: {gabarito}

Resolução passo a passo:"""
        resolucao = consultar_ollama(prompt, temperature=0, num_predict=NUM_PREDICT)
        if not resolucao or not str(resolucao).strip():
            raise RuntimeError(f'Não foi possível preparar a demonstração CoT {identificador}.')
        raciocinios[identificador] = str(resolucao).strip()
    return raciocinios


def executar_censo(limite=None, n_exemplos=None):
    from codigo.utils import carregar_censo
    from codigo.chain_of_thought.prompts import prompt_cot_censo
    from codigo.consulta_censo import verificar_consultas, SessaoCenso

    if limite is not None and (not isinstance(limite, int) or isinstance(limite, bool) or limite <= 0):
        raise ValueError('limite deve ser um inteiro positivo ou None.')
    quantidade = N_EXEMPLOS_CENSO if n_exemplos is None else n_exemplos
    registros = carregar_censo()
    ids = [str(q.get('id', '')) for q in registros]
    if not registros or not all(ids) or len(set(ids)) != len(ids):
        raise ValueError('O Censo precisa conter questões com IDs únicos e válidos.')

    # Usa a mesma distribuição entre blocos temáticos adotada no Few-shot.
    exemplos = selecionar_exemplos_few_shot('censo', registros, quantidade)
    ids_exemplos = {str(q['id']) for q in exemplos}
    disponiveis = [q for q in registros if str(q['id']) not in ids_exemplos]
    teste = disponiveis[:limite] if limite is not None else disponiveis
    if not teste:
        raise ValueError('Nenhuma questão independente disponível para avaliação.')

    verificar_consultas(exemplos + teste)
    sessao = SessaoCenso()
    contextos_exemplos = {str(e['id']): sessao.consultar(e) for e in exemplos}
    inicio = time.perf_counter()
    raciocinios_exemplos = criar_raciocinios_censo(exemplos, contextos_exemplos)

    pasta = Path('resultados/chain_of_thought/censo')
    identificador = criar_id_execucao('censo', limite, pasta, len(exemplos))
    resultados = []
    print(f'\nCENSO | Chain-of-Thought | {len(teste)} questões | {len(exemplos)} exemplos')
    print('IDs das demonstrações:', ', '.join(str(e['id']) for e in exemplos))

    for q in tqdm(teste, desc='Chain-of-Thought Censo'):
        contexto_atual = sessao.consultar(q)
        prompt = prompt_cot_censo(q, contexto_atual, exemplos, contextos_exemplos,
                                  raciocinios_exemplos)
        inicio_questao = time.perf_counter()
        info = consultar_ollama(prompt, temperature=TEMPERATURE,
                               num_predict=NUM_PREDICT, retornar_metricas=True)
        duracao = round(time.perf_counter() - inicio_questao, 3)
        if not isinstance(info, dict):
            info = {'resposta': None}
        resposta = str(info.get('resposta') or '').strip()
        avaliacao = avaliar_censo(q, resposta, consultar_ollama)
        resultados.append({
            'id': str(q['id']),
            'split': q.get('split'),
            'usada_como_exemplo': False,
            'avaliacao_independente': True,
            'gabarito': q.get('resposta_esperada'),
            'resposta': resposta,
            'texto_modelo': resposta,
            'resposta_valida': bool(resposta),
            'acertou': bool(avaliacao['acertou']),
            'motivo': avaliacao['motivo'],
            'metodo_avaliacao': avaliacao['metodo_avaliacao'],
            'tempo_segundos': duracao,
            'tokens_entrada': info.get('prompt_eval_count'),
            'tokens_saida': info.get('eval_count'),
            'fonte_csv': str(sessao.caminho),
        })

    total = len(resultados)
    acertos = sum(r['acertou'] for r in resultados)
    erros = total - acertos
    acuracia = round(100 * acertos / total, 2) if total else None
    dados = {
        'id_execucao': identificador,
        'tecnica': METODO,
        'metodo': METODO,
        'dataset': 'censo',
        'modelo': MODELO,
        'data_execucao': datetime.now().isoformat(timespec='seconds'),
        'parametros': {
            'temperatura': TEMPERATURE,
            'maximo_tokens_resposta': NUM_PREDICT,
            'limite': limite,
            'quantidade_exemplos': len(exemplos),
            'ids_exemplos': [str(q['id']) for q in exemplos],
            'ids_questoes': [str(q['id']) for q in teste],
            'criterio_avaliacao': 'fora_das_demonstracoes',
            'criterio_correcao': 'resposta_final_binaria',
            'selecao_exemplos': 'blocos_tematicos_igual_few_shot',
            'raciocinios_exemplos': raciocinios_exemplos,
        },
        'metricas': {
            'questoes_executadas': total,
            'questoes_independentes': total,
            'questoes_corrigidas': total,
            'exemplos_utilizados': len(exemplos),
            'acertos': acertos,
            'erros': erros,
            'acuracia_geral_percentual': acuracia,
            'acuracia_independente_percentual': acuracia,
            'tempo_total_segundos': round(time.perf_counter() - inicio, 2),
        },
        'resultados': resultados,
    }
    caminho = pasta / f'{identificador}.json'
    salvar_json(caminho, dados)
    print(f'\nAcertos: {acertos} | Erros: {erros} | Acurácia: {acuracia:.2f}%')
    print(f'Resultados salvos em: {caminho}')
    return dados


# FUNÇÕES DE EXECUÇÃO POR DATASET


def executar_gsm8k(limite=None, n_exemplos=None):
    return executar_dataset('gsm8k', limite=limite, n_exemplos=n_exemplos)


def executar_aqua_rat(limite=None, n_exemplos=None):
    return executar_dataset('aqua_rat', limite=limite, n_exemplos=n_exemplos)


# EXECUÇÃO PRINCIPAL

if __name__ == '__main__':
    executar_gsm8k(
        limite=500
    )

    executar_aqua_rat(
        limite=500
    )

    executar_censo(
        limite=20
    )