"""Experimentos Self-Consistency: GSM8K, AQuA-RAT e Censo Escolar.

"""
from datetime import datetime
from pathlib import Path
import re
from tqdm import tqdm

from codigo.utils import (
    carregar_gsm8k, carregar_aqua_rat, extrair_letra_resposta,
    extrair_resposta_numerica, extrair_gabarito_gsm8k,
    extrair_gabarito_aqua_rat, comparar_numeros, salvar_json,
)
from codigo.self_consistency.prompts import (
    prompt_self_consistency_gsm8k, prompt_self_consistency_aqua_rat,
    prompt_self_consistency_censo,
)
from codigo.self_consistency.experimentos import executar_experimento_self_consistency

# CONFIGURAÇÕES
METODO = 'self_consistency'
MODELO = 'llama3.2'
N_EXEMPLOS = 10  # Apenas GSM8K e AQuA-RAT; no Censo são sempre as 10 primeiras.
N_AMOSTRAS = 5  # Quantas respostas independentes gerar por questão.
TEMPERATURE = 0.7  # Permite explorar caminhos de resolução diferentes.
NUM_PREDICT = 800
PASTAS = {
    'gsm8k': Path('resultados/self_consistency/gsm8k'),
    'aqua_rat': Path('resultados/self_consistency/aqua_rat'),
    'censo': Path('resultados/self_consistency/censo'),
}


def criar_id_execucao(dataset, limite, pasta):
    """Gera ID sequencial, sem sobrescrever resultados anteriores."""
    pasta.mkdir(parents=True, exist_ok=True)
    data = datetime.now().strftime('%Y%m%d')
    nome_limite = str(limite) if limite is not None else 'todos'
    prefixo = f'{METODO}_{dataset}_{data}_{nome_limite}_'
    indice = 1
    while (pasta / f'{prefixo}{indice}.json').exists():
        indice += 1
    return f'{prefixo}{indice}'


def validar_limite(limite):
    if limite is not None and (not isinstance(limite, int) or isinstance(limite, bool) or limite <= 0):
        raise ValueError('limite deve ser inteiro positivo ou None.')


def selecionar_exemplos(dataset, n=None):
    """Usa os primeiros exemplos elegíveis do train, sempre na mesma ordem."""
    n = N_EXEMPLOS if n is None else n
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise ValueError('n_exemplos deve ser inteiro positivo.')
    carregar = carregar_gsm8k if dataset == 'gsm8k' else carregar_aqua_rat
    exemplos, ids = [], set()
    for q in carregar(split='train'):
        ident = str(q.get('id', '')).strip()
        if not ident or ident in ids:
            continue
        if dataset == 'gsm8k':
            if not str(q.get('question_pt') or '').strip():
                continue
            if not str(q.get('answer_pt') or q.get('answer_en') or '').strip():
                continue
            if not extrair_gabarito_gsm8k(q):
                continue
        else:
            if q.get('revisao_necessaria') is True:
                continue
            if not str(q.get('question_pt') or '').strip() or not str(q.get('rationale_pt') or '').strip():
                continue
            if not q.get('options_pt') or not q.get('correct'):
                continue
        exemplos.append(q)
        ids.add(ident)
        if len(exemplos) == n:
            break
    if len(exemplos) < n:
        raise ValueError(f'{dataset}: apenas {len(exemplos)} exemplos elegíveis para {n} solicitados.')
    return exemplos


def metricas_votacao(resultados):
    """Não presume que todo voto majoritário seja uma maioria absoluta."""
    total = len(resultados)
    return {
        'unanimidades': sum(r['votos_resposta_modelo'] == N_AMOSTRAS and not r['houve_empate'] for r in resultados),
        'vencedor_com_4_votos': sum(r['votos_resposta_modelo'] == 4 and not r['houve_empate'] for r in resultados),
        'vencedor_com_3_votos': sum(r['votos_resposta_modelo'] == 3 and not r['houve_empate'] for r in resultados),
        'empates': sum(r['houve_empate'] for r in resultados),
        'sem_resposta_valida': sum(r['total_respostas_validas'] == 0 for r in resultados),
        'media_votos_vencedor': round(sum(r['votos_resposta_modelo'] for r in resultados) / total, 2) if total else 0,
    }


def executar_dataset(dataset, limite=None, n_exemplos=None):
    validar_limite(limite)
    exemplos = selecionar_exemplos(dataset, n_exemplos)
    carregar = carregar_gsm8k if dataset == 'gsm8k' else carregar_aqua_rat
    teste = carregar(split='test')
    if limite is not None:
        teste = teste[:limite]
    ids_exemplos = [q['id'] for q in exemplos]
    if set(ids_exemplos) & {q['id'] for q in teste}:
        raise ValueError('Vazamento de dados: exemplo do train encontrado no test.')
    pasta = PASTAS[dataset]
    ident = criar_id_execucao(dataset, limite, pasta)
    resultados = []
    prompt_fn = prompt_self_consistency_gsm8k if dataset == 'gsm8k' else prompt_self_consistency_aqua_rat
    extrair = extrair_resposta_numerica if dataset == 'gsm8k' else extrair_letra_resposta
    print(f'\nSELF-CONSISTENCY {dataset.upper()} | {len(teste)} questões | {N_AMOSTRAS} amostras/questão')
    for q in tqdm(teste, desc=f'Self-Consistency {dataset}'):
        prompt = prompt_fn(q, exemplos)
        sc = executar_experimento_self_consistency(
            prompt, extrair, n_amostras=N_AMOSTRAS,
            temperature=TEMPERATURE, num_predict=NUM_PREDICT,
        )
        gabarito = extrair_gabarito_gsm8k(q) if dataset == 'gsm8k' else extrair_gabarito_aqua_rat(q)
        acertou = (comparar_numeros(sc['resposta_modelo'], gabarito)
                   if dataset == 'gsm8k' else sc['resposta_modelo'] == gabarito)
        resultados.append({'id': q['id'], 'split': q.get('split'), 'gabarito': gabarito,
                           'acertou': acertou, **sc})
    total = len(resultados)
    acertos = sum(r['acertou'] for r in resultados)
    dados = {
        'id_execucao': ident, 'data_execucao': datetime.now().isoformat(timespec='seconds'),
        'metodo': METODO, 'dataset': dataset, 'modelo': MODELO,
        'total': total, 'acertos': acertos, 'erros': total - acertos,
        'precisao': round(100 * acertos / total, 2) if total else 0,
        'parametros': {'limite': limite, 'n_exemplos': len(exemplos), 'ids_exemplos': ids_exemplos,
                       'split_exemplos': 'train', 'split_avaliacao': 'test',
                       'n_amostras': N_AMOSTRAS, 'temperature': TEMPERATURE, 'num_predict': NUM_PREDICT},
        'metricas_votacao': metricas_votacao(resultados), 'resultados': resultados,
    }
    caminho = pasta / f'{ident}.json'
    salvar_json(str(caminho), dados)
    print(f'Salvo: {caminho} | Acertos: {acertos}/{total} | Precisão: {dados["precisao"]:.2f}%')
    return dados


def executar_gsm8k(limite=None, n_exemplos=None):
    return executar_dataset('gsm8k', limite, n_exemplos)


def executar_aqua_rat(limite=None, n_exemplos=None):
    return executar_dataset('aqua_rat', limite, n_exemplos)


# CENSO: votação por respostas numéricas não cobre respostas explicativas.
# Mantemos TODAS as gerações para avaliação humana; não votamos sobre texto livre.
def extrair_numero_censo(texto):
    """Extrai um único valor apenas quando há resposta final estritamente numérica.

    Não interpreta tabelas, porcentagens com explicações ou respostas com vários números.
    """
    if not texto:
        return None
    correspondencias = re.findall(r'(?im)^\s*Resposta final:\s*([+-]?\d[\d.,]*)\s*$', texto)
    if not correspondencias:
        return None
    valor = correspondencias[-1].strip()
    # Não tentar normalizar ambiguidades como 1.234 (milhar ou decimal).
    return valor


def executar_censo(limite=None):
    """Dez demonstrações fixas 01-10; questões 11-50 para avaliação."""
    validar_limite(limite)
    from codigo.utils import carregar_censo
    from codigo.consulta_censo import verificar_consultas, SessaoCenso
    questoes = sorted(carregar_censo(), key=lambda q: q['id'])
    esperados = [f'censo_2025_{i:02d}' for i in range(1, 51)]
    if [q['id'] for q in questoes] != esperados:
        raise ValueError('Censo deve ter exatamente IDs 01 a 50, sem duplicatas.')
    exemplos = questoes[:10]  # FIXO: não usa N_EXEMPLOS nem aleatoriedade.
    teste = questoes[10:]
    if limite is not None:
        teste = teste[:limite]
    # Exige consultas reais ao CSV para cada questão selecionada.
    verificar_consultas(exemplos + teste)
    sessao = SessaoCenso()
    contextos_exemplos = {q['id']: sessao.consultar(q) for q in exemplos}
    pasta = PASTAS['censo']
    ident = criar_id_execucao('censo', limite, pasta)
    resultados = []
    print(f'\nSELF-CONSISTENCY CENSO | {len(teste)} questões | {N_AMOSTRAS} amostras/questão')
    for q in tqdm(teste, desc='Self-Consistency Censo'):
        contexto = sessao.consultar(q)
        prompt = prompt_self_consistency_censo(q, contexto, exemplos, contextos_exemplos)
        sc = executar_experimento_self_consistency(
            prompt, extrair_numero_censo, n_amostras=N_AMOSTRAS,
            temperature=TEMPERATURE, num_predict=NUM_PREDICT,
        )
        # Uma questão aberta pode ter respostas equivalentes com textos diferentes.
        # O voto numérico é exploratório; não define acerto sem revisão.
        resultados.append({'id': q['id'], 'gabarito_referencia': q.get('resposta_esperada'),
                           'fonte_csv': str(sessao.caminho), 'avaliacao_humana_pendente': True,
                           'votacao_numerica_apenas': True, **sc})
    dados = {
        'id_execucao': ident, 'data_execucao': datetime.now().isoformat(timespec='seconds'),
        'metodo': METODO, 'dataset': 'censo', 'modelo': MODELO, 'total': len(resultados),
        'acertos': None, 'erros': None, 'precisao': None,
        'parametros': {'limite': limite, 'n_exemplos_censo_fixo': 10,
                       'ids_exemplos': [q['id'] for q in exemplos],
                       'ids_teste': [q['id'] for q in teste],
                       'n_amostras': N_AMOSTRAS, 'temperature': TEMPERATURE,
                       'num_predict': NUM_PREDICT},
        'metricas_votacao_numerica': metricas_votacao(resultados),
        'avaliacao_humana_pendente': True, 'resultados': resultados,
    }
    caminho = pasta / f'{ident}.json'
    salvar_json(str(caminho), dados)
    print(f'Salvo: {caminho} | Avaliação humana pendente')
    return dados


if __name__ == '__main__':
    executar_gsm8k(limite=500)
    executar_aqua_rat(limite=500)
    # Habilitar quando as consultas do Censo estiverem implementadas e validadas:
    executar_censo(limite=20)