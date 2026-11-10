"""Consolida os três relatórios experimentais já gerados, sem recalcular dados.

Uso: python -m codigo.avaliacao.relatorio_tcc
"""
import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ROTULO = {'few_shot': 'Few-shot', 'chain_of_thought': 'CoT', 'self_consistency': 'SC'}


def consolidar(pasta):
    pasta = Path(pasta)
    relatorios = {}
    for dataset in ('gsm8k', 'aqua_rat', 'censo'):
        # padrão: relatorios/<dataset>/comparacao_<dataset>.json (também aceita o arquivo direto na pasta)
        caminho = pasta / dataset / f'comparacao_{dataset}.json'
        if not caminho.exists():
            caminho = pasta / f'comparacao_{dataset}.json'
        if caminho.exists():
            relatorios[dataset] = json.loads(caminho.read_text(encoding='utf-8'))
    if not relatorios:
        raise FileNotFoundError(f'Nenhum comparacao_<dataset>.json em {pasta}')
    linhas = ['# Síntese experimental do TCC', '',
             '| Dataset | Técnica | Questões válidas | Acertos | Acurácia | Pendentes | Tempo médio (s) |',
             '|---|---|---:|---:|---:|---:|---:|']
    for dataset, rel in relatorios.items():
        for tecnica, r in rel['acuracia'].items():
            custo = rel['custo'].get(tecnica, {})
            ac = f'{r["acuracia"] * 100:.2f}%' if r.get('acuracia') is not None else 'Pendente'
            tempo = custo.get('tempo_medio_s')
            linhas.append(f'| {dataset} | {ROTULO[tecnica]} | {r["avaliadas"]} | {r["acertos"]} | '
                         f'{ac} | {r["pendentes"]} | {tempo:.2f}' + ' |' if tempo is not None else
                         f'| {dataset} | {ROTULO[tecnica]} | {r["avaliadas"]} | {r["acertos"]} | '
                         f'{ac} | {r["pendentes"]} | — |')
    linhas += ['', '## Limitações de interpretação', '',
              '- Não agregar diretamente questões dos três datasets sem justificar pesos e diferenças de tarefa.',
              '- Resultados com revisão humana pendente não representam acurácia definitiva.',
              '- Comparações estatísticas devem usar somente questões comuns e decisões definitivas.',
              '- O custo-benefício não possui limiar universal de aceitação.',
              '- Verificar avisos de comparabilidade nos relatórios individuais.', '']
    nao_comp = [d for d, rel in relatorios.items() if not rel.get('comparavel', True)]
    if nao_comp:
        linhas += ['**Atenção — execuções NÃO comparáveis em:** ' + ', '.join(nao_comp)
                   + '. ' + ' | '.join(f'{d}: ' + '; '.join(relatorios[d].get('motivos_nao_comparavel', []))
                                      for d in nao_comp), '']
    faltantes = set(('gsm8k', 'aqua_rat', 'censo')) - set(relatorios)
    if faltantes:
        linhas += [f'**Datasets ainda não disponíveis:** {", ".join(sorted(faltantes))}.', '']
    return '\n'.join(linhas)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--pasta', default=str(RAIZ / 'resultados' / 'metricas' / 'relatorios'))
    args = p.parse_args(argv)
    try:
        texto = consolidar(args.pasta)
    except FileNotFoundError:
        print('Nenhum relatório de comparação encontrado em:', args.pasta)
        print('Execute primeiro comparacao_tecnicas.py para gerar os arquivos comparacao_*.json.')
        return 1
    destino = Path(args.pasta) / 'geral' / 'sintese_tcc.md'
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding='utf-8')
    print(texto)
    print('Salvo em:', destino)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
