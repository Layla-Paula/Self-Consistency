"""Reavalia, sem rodar o modelo, as questões do Censo marcadas como falha do avaliador.

Execuções antigas tratavam um parecer do juiz como falha técnica. Essas questões saíam da
acurácia e da fila de revisão humana. Aqui a resposta JÁ SALVA é avaliada de novo com o
avaliar_censo atual (regras objetivas; o juiz só como apoio) e o resultado vai para uma nova
execução, NOME_recuperacao.json, que substitui a original nos relatórios (campo recuperacao_de).
O arquivo original nunca é alterado.
"""
import copy
import json
import os
from pathlib import Path

from codigo.avaliacao.avaliacao_censo import avaliar_censo

METODO_FALHA = 'falha_tecnica_avaliador'
SUFIXOS_DERIVADOS = ('.progresso.json', '.auditado.json', '.revisoes.json', '.final.json')
TECNICAS = ('chain_of_thought', 'few_shot')


def _metricas(tecnica):
    if tecnica == 'chain_of_thought':
        from codigo.chain_of_thought.executar_cot import metricas
    else:
        from codigo.few_shot.executar_few_shot import metricas
    return metricas


def _salvar(caminho, dados):
    temporario = Path(str(caminho) + '.tmp')
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporario, caminho)


def _afetadas(dados):
    return [q for q in dados.get('resultados', [])
            if q.get('falha_tecnica') and q.get('metodo_avaliacao') == METODO_FALHA]


def listar(pasta):
    """Execuções do Censo (CoT e Few-shot) com falhas do avaliador ainda não reavaliadas."""
    plano = []
    for arquivo in sorted(Path(pasta).rglob('*.json')):
        if arquivo.name.endswith(SUFIXOS_DERIVADOS) or arquivo.stem.endswith('_recuperacao'):
            continue
        try:
            dados = json.loads(arquivo.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not (isinstance(dados, dict) and dados.get('dataset') == 'censo'
                and dados.get('tecnica') in TECNICAS
                and dados.get('status') in ('concluido', 'concluido_com_falhas')
                and isinstance(dados.get('resultados'), list)):
            continue
        n = len(_afetadas(dados))
        if n and not arquivo.with_name(arquivo.stem + '_recuperacao.json').exists():
            plano.append({'arquivo': arquivo, 'falhas': n, 'total': len(dados['resultados'])})
    return plano


def reavaliar_arquivo(arquivo, enunciados, consultar_modelo=None):
    """Cria NOME_recuperacao.json. enunciados: {id: questão do JSON do Censo}."""
    arquivo = Path(arquivo)
    original = json.loads(arquivo.read_text(encoding='utf-8'))
    dados = copy.deepcopy(original)
    ids = []
    for q in _afetadas(dados):
        base = enunciados.get(str(q['id']))
        if base is None:
            raise ValueError(f"Questão {q['id']} não encontrada no JSON do Censo.")
        avaliacao = avaliar_censo(base, q.get('resposta') or '', consultar_modelo)
        acertou = avaliacao['acertou']
        q.update({
            'acertou': acertou, 'motivo': avaliacao['motivo'],
            'metodo_avaliacao': avaliacao['metodo_avaliacao'],
            'revisao_necessaria': bool(avaliacao.get('revisao_necessaria', acertou is None)),
            'falha_tecnica': False,
            'reavaliada_de': METODO_FALHA,
        })
        for chave in ('parecer_llm', 'tentativas_avaliador'):
            if chave in avaliacao:
                q[chave] = avaliacao[chave]
        ids.append(q['id'])
    nome = arquivo.stem + '_recuperacao'
    dados['id_execucao'] = nome
    dados['recuperacao_de'] = str(arquivo)
    dados['status'] = ('concluido_com_falhas' if any(q.get('falha_tecnica') for q in dados['resultados'])
                       else 'concluido')
    dados['reavaliacao_avaliador'] = {'ids': ids, 'motivo': 'parecer do juiz tratado como falha técnica'}
    dados['metricas'] = _metricas(dados['tecnica'])(
        dados['resultados'], dados.get('tempo_acumulado_segundos', 0.0),
        dados['parametros']['quantidade_exemplos'], 'censo')
    destino = arquivo.with_name(nome + '.json')
    _salvar(destino, dados)
    return destino, dados


def reavaliar_pasta(pasta, simular=False, consultar_modelo=None):
    plano = listar(pasta)
    print(f'\n{len(plano)} execução(ões) do Censo com falha do avaliador em {pasta}:')
    for item in plano:
        print(f"  - {item['arquivo'].name}: {item['falhas']} questão(ões) em {item['total']}")
    if simular or not plano:
        if simular:
            print('\nModo simulação: nada foi alterado.')
        return plano
    from codigo.utils import carregar_censo, consultar_ollama
    enunciados = {str(q['id']): q for q in carregar_censo()}
    consultar_modelo = consultar_modelo or consultar_ollama
    for item in plano:
        destino, dados = reavaliar_arquivo(item['arquivo'], enunciados, consultar_modelo)
        m = dados['metricas']
        pendentes = sum(q.get('acertou') is None and not q.get('falha_tecnica')
                        for q in dados['resultados'])
        print(f"  {destino.name}: {m['questoes_avaliadas']} avaliadas, "
              f"{pendentes} pendente(s), {m['falhas_tecnicas']} falha(s)")
    print('\nProximo passo: python -m codigo.revisao_humana revisar-pasta PASTA --revisor layla')
    return plano
