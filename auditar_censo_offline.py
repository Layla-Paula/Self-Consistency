"""Audita o JSON de Self-Consistency do Censo sem Ollama e sem alterar o original.
Uso: python auditar_censo_offline.py caminho/resultado.json
Rode na raiz do projeto, após instalar os arquivos corrigidos.
"""
import copy
import json
import sys
from pathlib import Path
from codigo.avaliacao.avaliacao_censo import avaliar_censo
from codigo.self_consistency.votacao import voto_censo_semantico


def auditar(caminho):
    caminho = Path(caminho)
    original = json.loads(caminho.read_text(encoding='utf-8'))
    if original.get('dataset') != 'censo' or original.get('tecnica') != 'self_consistency':
        raise ValueError('Arquivo não é Self-Consistency do Censo.')
    dados = copy.deepcopy(original)
    contagem = {'acertos_objetivos': 0, 'erros_objetivos': 0, 'pendentes_revisao': 0,
                'sem_resposta': 0, 'respostas_formato_invalido': 0}
    for questao in dados.get('resultados', []):
        amostras = questao.get('amostras') or []
        if amostras:
            # Não recupera amostras vazias: texto bruto pode ter sido rejeitado pelo agente.
            respostas = [a.get('resposta_extraida') or '' for a in amostras]
            votacao = voto_censo_semantico('', respostas, None)
            resposta = votacao['vencedora']
            questao.update(resposta=resposta, resposta_modelo=resposta,
                           distribuicao_votos=votacao['distribuicao'],
                           votos_resposta_modelo=votacao['votos'],
                           houve_empate=votacao['houve_empate'],
                           total_respostas_validas=votacao['total_respostas_validas'])
        else:
            resposta = questao.get('resposta') or ''
        # A função de avaliação NÃO recebe o Ollama; resultados sem rubrica são pendentes.
        avaliacao = avaliar_censo({'id': questao.get('id'),
                                   'pergunta': questao.get('pergunta', ''),
                                   'resposta_esperada': questao.get('gabarito', '')}, resposta, None)
        questao['acertou'] = avaliacao['acertou']
        questao['motivo'] = avaliacao['motivo']
        questao['metodo_avaliacao'] = avaliacao['metodo_avaliacao']
        questao['revisao_necessaria'] = avaliacao['revisao_necessaria']
        if not resposta:
            contagem['sem_resposta'] += 1
        elif avaliacao['metodo_avaliacao'] == 'formato_invalido_censo':
            contagem['respostas_formato_invalido'] += 1
        elif avaliacao['acertou'] is None:
            contagem['pendentes_revisao'] += 1
        elif avaliacao['acertou']:
            contagem['acertos_objetivos'] += 1
        else:
            contagem['erros_objetivos'] += 1
    dados['metricas_originais'] = dados.pop('metricas', None)
    dados['auditoria_offline'] = {
        'criterio': 'rubricas_objetivas; outros casos pendentes para revisao humana',
        'observacao': 'Não altera nem valida o experimento original. Sem consultas SQL novas.',
        **contagem,
    }
    dados['status'] = 'auditoria_offline_nao_equivale_a_nova_execucao'
    saida = caminho.with_name(caminho.stem + '.auditado.json')
    if saida.exists():
        raise FileExistsError(f'Já existe: {saida}; não será sobrescrito.')
    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(contagem, ensure_ascii=False, indent=2))
    print('Auditoria salva em:', saida)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Uso: python auditar_censo_offline.py caminho/resultado.json')
    auditar(sys.argv[1])
