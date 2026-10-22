"""Auditoria offline dos resultados; não consulta o Ollama nem altera originais."""
import copy
import json
import sys
from collections import Counter
from pathlib import Path

from codigo.utils import extrair_letra_resposta, extrair_resposta_numerica, comparar_numeros
from codigo.avaliacao.avaliacao_censo import _criterios_censo

RAIZ = Path(__file__).resolve().parents[1]
PASTA_RESULTADOS = RAIZ / 'resultados'
PASTA_METRICAS = PASTA_RESULTADOS / 'metricas' / 'auditorias'
TECNICAS = ('few_shot', 'chain_of_thought', 'self_consistency')
DATASETS = ('gsm8k', 'aqua_rat', 'censo')


def encontrar_arquivos():
    arquivos = []
    for tecnica in TECNICAS:
        for dataset in DATASETS:
            pasta = PASTA_RESULTADOS / tecnica / dataset
            if pasta.is_dir():
                arquivos.extend(p for p in pasta.rglob('*.json')
                                if not p.name.endswith('.auditado.json'))
    return sorted(set(arquivos))


def reavaliar_censo(questao):
    """Veredito sempre booleano; sem juiz, não simula uma avaliação semântica."""
    resposta = str(questao.get('resposta') or '').strip()
    if not resposta:
        return False, 'Resposta ausente.', 'resposta_vazia', True
    dados_questao = {
        'id': questao.get('id'),
        'gabarito': questao.get('gabarito', ''),
    }
    resultado = _criterios_censo(dados_questao, resposta)
    if resultado is not None:
        return bool(resultado['acertou']), resultado.get('motivo', ''), 'rubrica_objetiva_censo', True
    anterior = questao.get('acertou')
    if isinstance(anterior, bool):
        return anterior, questao.get('motivo') or 'Veredito original preservado.', 'veredito_original_nao_revalidado', False
    return False, 'Sem rubrica aplicável e sem veredito anterior: erro conservador.', 'sem_veredito_anterior', False


def analisar(caminho):
    caminho = Path(caminho).resolve()
    original = json.loads(caminho.read_text(encoding='utf-8'))
    dados = copy.deepcopy(original)
    dataset = dados.get('dataset')
    tecnica = dados.get('tecnica')
    if dataset not in DATASETS or tecnica not in TECNICAS:
        raise ValueError(f'Dataset ou técnica desconhecidos: {dataset!r}, {tecnica!r}')
    extrator = extrair_letra_resposta if dataset == 'aqua_rat' else extrair_resposta_numerica
    alteracoes = []
    nao_revalidados = []

    for questao in dados.get('resultados', []):
        identificador = questao.get('id')
        amostras = questao.get('amostras') or []
        if dataset != 'censo':
            if amostras:
                for amostra in amostras:
                    antigo = amostra.get('resposta_extraida', '')
                    novo = extrator(amostra.get('resposta_completa') or '') if not amostra.get('falha_tecnica') else ''
                    if novo != antigo:
                        alteracoes.append({'id': identificador, 'amostra': amostra.get('amostra'), 'antes': antigo, 'depois': novo})
                    amostra['resposta_extraida'] = novo
                votos = Counter(a['resposta_extraida'] for a in amostras if a.get('resposta_extraida'))
                maior = max(votos.values(), default=0)
                lideres = [v for v, n in votos.items() if n == maior]
                resposta = lideres[0] if len(lideres) == 1 else ''
                questao.update({
                    'respostas_extraidas': [a.get('resposta_extraida', '') for a in amostras],
                    'distribuicao_votos': dict(votos),
                    'resposta_modelo': resposta,
                    'resposta': resposta,
                    'votos_resposta_modelo': maior if resposta else 0,
                    'houve_empate': len(lideres) > 1,
                    'total_respostas_validas': sum(votos.values()),
                })
            else:
                texto = questao.get('texto_modelo')
                if texto is None:
                    # Sem texto bruto não é possível refazer a extração.
                    nao_revalidados.append(identificador)
                else:
                    novo = extrator(texto)
                    antigo = questao.get('resposta', '')
                    if novo != antigo:
                        alteracoes.append({'id': identificador, 'antes': antigo, 'depois': novo})
                    questao['resposta'] = novo
            resposta = questao.get('resposta') or ''
            questao['resposta_valida'] = bool(resposta)
            if not questao.get('falha_tecnica'):
                gabarito = questao.get('gabarito', '')
                questao['acertou'] = (resposta == gabarito) if dataset == 'aqua_rat' else (bool(resposta) and comparar_numeros(resposta, gabarito))
        else:
            # Preserva a seleção semântica original do Self-Consistency.
            questao['resposta_valida'] = bool(questao.get('resposta'))
            acertou, motivo, metodo, validado = reavaliar_censo(questao)
            questao['acertou'] = acertou
            questao['motivo'] = motivo
            questao['metodo_avaliacao'] = metodo
            questao['revisao_necessaria'] = not validado
            if not validado:
                nao_revalidados.append(identificador)
            # Falha do juiz não é falha de geração; registrar a origem para auditoria.
            if questao.get('falha_tecnica') and 'veredito' in str(questao.get('motivo_falha_tecnica', '')).lower():
                questao['falha_tecnica'] = False
                questao['motivo_falha_tecnica'] = None

    resultados = dados.get('resultados', [])
    falhas = [q for q in resultados if q.get('falha_tecnica')]
    avaliadas = [q for q in resultados if not q.get('falha_tecnica')]
    acertos = sum(q.get('acertou') is True for q in avaliadas)
    erros = len(avaliadas) - acertos
    dados['auditoria'] = {
        'tipo': 'reanálise_offline', 'arquivo_origem': str(caminho),
        'metricas_originais': original.get('metricas', {}),
        'alteracoes_extracao': alteracoes,
        'ids_nao_revalidados_offline': nao_revalidados,
        'observacao': 'Censo sem rubrica objetiva mantém veredito anterior; não houve nova avaliação semântica.',
    }
    dados['metricas'] = {
        **original.get('metricas', {}),
        'questoes_executadas': len(resultados),
        'questoes_avaliadas': len(avaliadas),
        'acertos': acertos, 'erros': erros,
        'falhas_tecnicas': len(falhas),
        'acuracia_percentual': round(100 * acertos / len(avaliadas), 2) if avaliadas else None,
        'revisoes_necessarias': len(nao_revalidados),
    }
    destino_dir = PASTA_METRICAS / tecnica / dataset
    destino_dir.mkdir(parents=True, exist_ok=True)
    # Preserva nomes de subpastas para evitar colisões entre execuções com mesmo nome.
    try:
        relativo = caminho.relative_to(PASTA_RESULTADOS / tecnica / dataset)
        destino = destino_dir / relativo.parent / (caminho.stem + '.auditado.json')
    except ValueError:
        destino = destino_dir / (caminho.stem + '.auditado.json')
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{tecnica}/{dataset}: {acertos}/{len(avaliadas)} = {dados["metricas"]["acuracia_percentual"]}%')
    print(f'Extrações alteradas: {len(alteracoes)} | Sem revalidação offline: {len(nao_revalidados)}')
    print(f'Salvo em: {destino}\n')
    return destino


def main():
    arquivos = [Path(sys.argv[1])] if len(sys.argv) == 2 else encontrar_arquivos()
    if not arquivos:
        print('Nenhum JSON de resultados encontrado.')
        return
    falhas = []
    for arquivo in arquivos:
        try:
            analisar(arquivo)
        except (OSError, ValueError, KeyError, TypeError) as erro:
            falhas.append((str(arquivo), str(erro)))
            print(f'ERRO em {arquivo}: {erro}')
    print(f'Arquivos: {len(arquivos)} | Falhas de análise: {len(falhas)}')
    if falhas:
        raise SystemExit(1)


if __name__ == '__main__':
    if len(sys.argv) > 2:
        raise SystemExit('Uso: python -m codigo.analisar_resultados [arquivo.json]')
    main()
