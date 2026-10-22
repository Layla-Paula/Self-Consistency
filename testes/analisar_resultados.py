
import argparse
import csv
import json
import sys
from pathlib import Path

from codigo.avaliacao.avaliacao_censo import _criterios_censo


def ler(path):
    with Path(path).open(encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arquivos', nargs='+', help='Arquivos JSON de resultados')
    parser.add_argument('--censo', default='dados/censo_escolar/final/censo_escolar_2025.json')
    args = parser.parse_args()
    dados_censo = ler(args.censo)
    questoes = {q['id']: q for q in dados_censo.get('questoes', [])}
    linhas = []
    for caminho in args.arquivos:
        dados = ler(caminho)
        dataset = dados.get('dataset', '')
        limite = dados.get('parametros', {}).get('maximo_tokens_resposta')
        for r in dados.get('resultados', []):
            amostras = r.get('amostras', [])
            sem_extracao = sum(not str(a.get('resposta_extraida') or '').strip() for a in amostras)
            no_limite = sum(a.get('tokens_saida') == limite for a in amostras if limite)
            nova = None
            metodo = 'nao_reavaliado'
            if dataset == 'censo' and r.get('id') in questoes:
                decisao = _criterios_censo(questoes[r['id']], str(r.get('resposta') or ''))
                if decisao is not None:
                    nova = decisao['acertou']
                    metodo = 'rubrica_objetiva'
                else:
                    metodo = 'revisao_semantica_pendente'
            anterior = r.get('acertou')
            mudou = (nova is not None and isinstance(anterior, bool) and nova != anterior)
            linhas.append({
                'arquivo': Path(caminho).name, 'dataset': dataset,
                'id': r.get('id'), 'acerto_original': anterior,
                'acerto_por_rubrica': nova, 'classificacao': metodo,
                'divergencia': mudou, 'amostras_sem_extracao': sem_extracao,
                'amostras_no_limite_tokens': no_limite,
                'metodo_votacao': r.get('metodo_votacao'),
                'resposta': r.get('resposta', ''), 'gabarito': r.get('gabarito', ''),
            })
    saida = Path('resultados/metricas/auditoria_resultados.csv')
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]) if linhas else [])
        if linhas:
            w.writeheader()
            w.writerows(linhas)
    print(f'Auditoria salva em: {saida}')
    print(f'Questões: {len(linhas)}')
    print(f'Divergências de classificação objetiva: {sum(x["divergencia"] for x in linhas)}')
    print(f'Amostras sem extração: {sum(x["amostras_sem_extracao"] for x in linhas)}')
    print(f'Amostras no limite de tokens: {sum(x["amostras_no_limite_tokens"] for x in linhas)}')
    print('Atenção: rubricas não cobrem todas as questões; não use este CSV como acurácia final automática.')


if __name__ == '__main__':
    main()
