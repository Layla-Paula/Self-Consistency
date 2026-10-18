"""Execução Chain-of-Thought para GSM8K, AQuA-RAT e Censo, com exemplos reais.

"""
from datetime import datetime
from pathlib import Path
from tqdm import tqdm

from codigo.utils import (
    carregar_gsm8k, carregar_aqua_rat, consultar_ollama,
    extrair_letra_resposta, extrair_resposta_numerica,
    extrair_gabarito_gsm8k, extrair_gabarito_aqua_rat,
    comparar_numeros, salvar_json,
)
from codigo.chain_of_thought.prompts import prompt_cot_gsm8k, prompt_cot_aqua_rat

# CONFIGURAÇÕES
METODO = 'chain_of_thought'
MODELO = 'llama3.2'
PASTAS = {
    'gsm8k': Path('resultados/chain_of_thought/gsm8k'),
    'aqua_rat': Path('resultados/chain_of_thought/aqua_rat'),
}
TEMPERATURE = 0.0  # Reduz a aleatoriedade da geração.
NUM_PREDICT = 800   # Limita o máximo de tokens de saída.
N_EXEMPLOS = 10     # Altere aqui para 15, 20 etc. Quantidade de demonstrações reais do split train.


# CRIA IDENTIFICADOR DA EXECUÇÃO

def criar_id_execucao(dataset, limite, pasta):
    """Exemplo: chain_of_thought_gsm8k_20261017_todos_1"""
    data = datetime.now().strftime('%Y%m%d')
    limite_nome = str(limite) if limite is not None else 'todos'
    prefixo = f'{METODO}_{dataset}_{data}_{limite_nome}_'
    pasta.mkdir(parents=True, exist_ok=True)  # Não gera erro se já existir.
    numero_execucao = 1
    while True:  # Procura um nome que ainda não exista.
        identificador = f'{prefixo}{numero_execucao}'
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
    id_execucao = criar_id_execucao(dataset, limite, pasta)
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


# EXECUÇÃO CENSO ESCOLAR — DEZ PRIMEIRAS QUESTÕES FIXAS.
# NÃO utiliza N_EXEMPLOS, n_exemplos, sorteio ou seed.
# Exemplos: IDs 01 a 10. Avaliação: IDs 11 a 50.

def executar_censo(limite=None):
    from codigo.utils import carregar_censo
    from codigo.chain_of_thought.prompts import prompt_cot_censo

    if limite is not None and (not isinstance(limite, int) or isinstance(limite, bool) or limite <= 0):
        raise ValueError('limite deve ser um inteiro positivo ou None.')
    questoes = carregar_censo()
    if len(questoes) != 50:
        raise ValueError('Esperadas exatamente 50 questões no Censo Escolar.')
    if len({q['id'] for q in questoes}) != 50:
        raise ValueError('IDs duplicados no Censo.')
    # Ordenar pelos IDs garante que são realmente as questões 01 a 10.
    ordenadas = sorted(questoes, key=lambda q: q['id'])
    ids_esperados = [f'censo_2025_{i:02d}' for i in range(1, 51)]
    if [q['id'] for q in ordenadas] != ids_esperados:
        raise ValueError('Os IDs do Censo devem ir de censo_2025_01 a censo_2025_50.')
    exemplos = ordenadas[:10]  # FIXO nesta técnica.
    teste = ordenadas[10:]    # Nenhuma questão de exemplo entra no teste.
    if limite is not None:
        teste = teste[:limite]

    # Valida se TODAS as questões selecionadas possuem consultas implementadas antes do Ollama.
    # Cada questão é consultada na execução desta técnica; não usamos um JSON
    # de contextos pré-calculados nem a resposta_esperada como evidência.
    from codigo.consulta_censo import verificar_consultas, SessaoCenso
    verificar_consultas(exemplos + teste)
    sessao = SessaoCenso()
    contextos_exemplos = {}
    for exemplo in exemplos:
        contextos_exemplos[exemplo['id']] = sessao.consultar(exemplo)
    # Não consultar todas as questões de avaliação antecipadamente.
    # A consulta é realizada dentro do loop, antes de cada prompt.

    pasta = Path('resultados/chain_of_thought/censo')
    identificador = criar_id_execucao('censo', limite, pasta)
    resultados = []
    for q in tqdm(teste, desc='Chain-of-Thought Censo'):
        contexto_atual = sessao.consultar(q)  # Consulta o CSV nesta questão.
        prompt = prompt_cot_censo(q, contexto_atual, exemplos, contextos_exemplos)
        resposta = consultar_ollama(prompt, temperature=TEMPERATURE, num_predict=NUM_PREDICT)
        # Questões abertas: não calcular acerto por igualdade de strings.
        resultados.append({
            'id': q['id'], 'resposta_modelo': resposta,
            'erro_ollama': resposta is None, 'fonte_csv': str(sessao.caminho),
            'gabarito_referencia': q.get('resposta_esperada'),
            'avaliacao_humana_pendente': True,
        })
    dados = {
        'id_execucao': identificador, 'metodo': METODO, 'dataset': 'censo',
        'modelo': MODELO, 'total': len(resultados),
        'data_execucao': datetime.now().isoformat(timespec='seconds'),
        'parametros': {'n_exemplos_censo_fixo': 10,
                       'temperature': TEMPERATURE, 'num_predict': NUM_PREDICT,
                       'ids_exemplos': [q['id'] for q in exemplos],
                       'ids_teste': [q['id'] for q in teste],
                       'divisao': 'primeiras_10_demonstracoes_restantes_40_avaliacao'},
        'resultados': resultados,
    }
    caminho = pasta / f'{identificador}.json'
    salvar_json(caminho, dados)
    print(f'\nSalvo: {caminho} | Questões: {len(resultados)} | Avaliação humana pendente')
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

    # Descomente após implementar e validar as consultas necessárias do Censo.
    executar_censo(
        limite=20
    )