"""Gráficos (PNG) e planilha Excel gerados a partir das configurações já agregadas.

É chamado automaticamente por `comparar_configuracoes` (mesmo comando do relatório).
Saídas, na mesma pasta do relatório:
  grafico_acuracia.png  - acurácia por técnica e dataset
  grafico_tempo.png     - tempo médio por questão por técnica e dataset
  tabelas.xlsx          - abas Few-shot, CoT e Self-Consistency (uma linha por EXECUÇÃO, com data e
                          hora) e Resumo (média das execuções de mesma configuração)
Tudo é refeito a cada vez que o relatório é gerado, e a data da atualização aparece nos arquivos.

Nos gráficos, cada técnica aparece com UMA configuração por dataset: a mais executada
(empate: a de mais tokens). A configuração usada aparece na legenda do próprio gráfico.
Todas as configurações ficam nas planilhas.
"""
from datetime import datetime

from codigo.avaliacao.comparacao_tecnicas import ROTULO, TECNICAS

DATASETS = ('gsm8k', 'aqua_rat', 'censo')
NOME_DATASET = {'gsm8k': 'GSM8K', 'aqua_rat': 'AQuA-RAT', 'censo': 'Censo Escolar'}
CORES = {'few_shot': '#9aa5b1', 'chain_of_thought': '#4f8fc0', 'self_consistency': '#e07b39'}


def _ordem(v):
    return (v is None, v if isinstance(v, (int, float)) else 0)


def _tokens_usados(a):
    if a.get('tokens_entrada_medio') is None or a.get('tokens_saida_medio') is None:
        return None
    return round(a['tokens_entrada_medio'] + a['tokens_saida_medio'])


def _questoes(a):
    return a.get('questoes_avaliadas')


def escolher_representantes(agregados):
    """{(tecnica, dataset): agregado} — a configuração mais executada de cada técnica/dataset."""
    melhor = {}
    for a in agregados:
        if a['acuracia_media'] is None:
            continue
        k = (a['tecnica'], a['dataset'])
        pontos = (a['execucoes'], a['tokens'] or 0, a['n_amostras'] or 0)
        if k not in melhor or pontos > melhor[k][0]:
            melhor[k] = (pontos, a)
    return {k: v[1] for k, v in melhor.items()}


def _desc_config(a):
    partes = [f"{a['tokens']} tokens" if a['tokens'] else None,
              f"temp. {a['temperatura']}" if a['temperatura'] is not None else None,
              f"{a['n_amostras']} amostras" if a['n_amostras'] else None]
    return ', '.join(p for p in partes if p)


def _grafico_barras(caminho, reps, campo, titulo, rotulo_y, formato, de_porcentagem=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    datasets = [d for d in DATASETS if any(k[1] == d for k in reps)]
    tecnicas = [t for t in TECNICAS if any(k[0] == t for k in reps)]
    if not datasets or not tecnicas:
        return False
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
    largura = 0.8 / len(tecnicas)
    for i, t in enumerate(tecnicas):
        xs, ys, falta = [], [], []
        for j, d in enumerate(datasets):
            a = reps.get((t, d))
            v = a.get(campo) if a else None
            if v is None:
                continue
            xs.append(j + (i - (len(tecnicas) - 1) / 2) * largura)
            ys.append(v * 100 if de_porcentagem else v)
        legenda = ROTULO[t]
        cfgs = sorted({_desc_config(reps[(t, d)]) for d in datasets if (t, d) in reps})
        if cfgs:
            legenda += f" ({'; '.join(cfgs)})" if len(cfgs) == 1 else ' (config. varia por dataset)'
        barras = ax.bar(xs, ys, largura * 0.92, label=legenda, color=CORES[t])
        for b, y in zip(barras, ys):
            ax.annotate(formato(y), (b.get_x() + b.get_width() / 2, y), ha='center', va='bottom',
                        xytext=(0, 3), textcoords='offset points', fontsize=9)
    ax.set_xticks(range(len(datasets)))
    ax.set_xticklabels([NOME_DATASET[d] for d in datasets])
    ax.set_ylabel(rotulo_y)
    ax.set_title(titulo, fontsize=12)
    if de_porcentagem:
        ax.set_ylim(0, 105)
    else:
        ax.set_ylim(0, ax.get_ylim()[1] * 1.12)
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', alpha=0.25)
    ax.legend(fontsize=8, frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.08), ncol=1)
    fig.text(0.99, 0.01, f'Atualizado em {_agora()}', ha='right', va='bottom', fontsize=7, color='#777777')
    fig.tight_layout()
    fig.savefig(caminho)
    plt.close(fig)
    return True


def gerar_graficos(agregados, pasta):
    reps = escolher_representantes(agregados)
    g1 = _grafico_barras(pasta / 'grafico_acuracia.png', reps, 'acuracia_media',
                         'Acurácia por técnica e dataset', 'Acurácia (%)',
                         lambda v: f'{v:.1f}%', de_porcentagem=True)
    g2 = _grafico_barras(pasta / 'grafico_tempo.png', reps, 'tempo_medio_s',
                         'Tempo médio por questão, por técnica e dataset', 'Segundos por questão',
                         formatar_duracao)
    return [n for n, ok in (('grafico_acuracia.png', g1), ('grafico_tempo.png', g2)) if ok]


def formatar_duracao(seg):
    """91.2 -> '1 min 31 s'; 4.62 -> '4,6 s'; 3700 -> '1 h 01 min'."""
    if seg is None:
        return '—'
    if seg < 60:
        return f'{seg:.1f}'.replace('.', ',') + ' s'
    seg = round(seg)
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return f'{h} h {m:02d} min' if h else f'{m} min {s:02d} s'


def formatar_data(iso):
    try:
        return datetime.fromisoformat(str(iso)[:19]).strftime('%d/%m/%Y %H:%M')
    except ValueError:
        return str(iso or '')


def _agora():
    return datetime.now().strftime('%d/%m/%Y %H:%M')


def _obs(l):
    notas = []
    if l.get('suspeita'):
        notas.append('suspeita: nenhuma resposta extraída (fora das médias)')
    if l.get('falhas_tecnicas'):
        notas.append(f"{l['falhas_tecnicas']} falha(s) técnica(s)")
    if l.get('pendentes'):
        notas.append(f"{l['pendentes']} pendente(s) de revisão")
    if l.get('recuperacao_de'):
        notas.append('recuperação de falhas')
    return '; '.join(notas)


def _tempo_total(l):
    execucao = l.get('_execucao') or {}
    tempos = [q.get('tempo_segundos') for q in execucao.get('questoes', [])
              if q.get('tempo_segundos') is not None and not q.get('falha_tecnica')]
    return sum(tempos) if tempos else None


def _ordem_linha(l):
    return (DATASETS.index(l['dataset']), str(l.get('data') or ''))


def cabecalho_execucao(tecnica, com_maquina):
    cab = ['Data e hora', 'Dataset', 'Acurácia (%)', 'Acertos', 'Erros', 'Pendentes', 'Falhas técnicas',
           'Questões avaliadas', 'Exemplos', 'Tokens máx.']
    if tecnica == 'self_consistency':
        cab += ['Temperatura', 'Amostras']
    cab += ['Tempo médio/questão', 'Tempo total', 'Tokens médios/questão (entrada + saída)']
    if com_maquina:
        cab.append('Máquina')
    return cab + ['Observação']


def linha_da_execucao(l, tecnica, com_maquina):
    erros = l['avaliadas'] - l['acertos'] - l['pendentes']
    tokens = (round(l['tokens_entrada_medio'] + l['tokens_saida_medio'])
              if l.get('tokens_entrada_medio') is not None and l.get('tokens_saida_medio') is not None else None)
    seg = l.get('tempo_medio_s')
    total = _tempo_total(l)
    linha = [formatar_data(l['data']), NOME_DATASET[l['dataset']], _pct(l['acuracia']), l['acertos'],
             erros, l['pendentes'], l['falhas_tecnicas'], l['avaliadas'], l['exemplos'], l['tokens']]
    if tecnica == 'self_consistency':
        linha += [l['temperatura'], l['n_amostras']]
    linha += [None if seg is None else seg / 86400, None if total is None else total / 86400, tokens]
    if com_maquina:
        linha.append(l['maquina'])
    return linha + [_obs(l)]


CAB_RESUMO = ('Técnica', 'Dataset', 'Temperatura', 'Amostras', 'Tokens máx.', 'Questões', 'Exemplos',
              'Execuções (nº de vezes que rodou)', 'Acurácia média (%)', 'Tempo médio/questão',
              'Tokens médios/questão (entrada + saída)')


def _pct(v):
    return None if v is None else round(v * 100, 2)


def linhas_resumo(agregados):
    ordenados = sorted(agregados, key=lambda a: (DATASETS.index(a['dataset']), TECNICAS.index(a['tecnica']),
                                                  _ordem(a['temperatura']), _ordem(a['tokens']),
                                                  _ordem(a['n_amostras'])))
    return [[ROTULO[a['tecnica']], NOME_DATASET[a['dataset']], a['temperatura'], a['n_amostras'], a['tokens'],
             a.get('questoes_avaliadas'), a['exemplos'], a['execucoes'], _pct(a['acuracia_media']),
             None if a['tempo_medio_s'] is None else a['tempo_medio_s'] / 86400, _tokens_usados(a)]
            for a in ordenados]


def gerar_planilha(linhas, agregados, caminho):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)
    com_maquina = any(l['maquina'] != 'não informada' for l in linhas)
    nomes = {'few_shot': 'Few-shot', 'chain_of_thought': 'CoT', 'self_consistency': 'Self-Consistency'}
    abas = []
    for t in TECNICAS:
        cab = cabecalho_execucao(t, com_maquina)
        dados = [linha_da_execucao(l, t, com_maquina)
                 for l in sorted([x for x in linhas if x['tecnica'] == t], key=_ordem_linha)]
        abas.append((nomes[t], cab, dados))
    abas.append(('Resumo', CAB_RESUMO, linhas_resumo(agregados)))
    for nome, cab, dados in abas:
        ws = wb.create_sheet(nome)
        ws.append([f'Atualizado em {_agora()} (gerado automaticamente a partir dos JSONs de resultados)'])
        ws['A1'].font = Font(italic=True, color='666666')
        ws.append(cab)
        for c in ws[2]:
            c.font = Font(bold=True, color='FFFFFF')
            c.fill = PatternFill('solid', fgColor='305496')
            c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        for linha in dados:
            ws.append(['' if v is None else v for v in linha])
        for i, titulo in enumerate(cab, 1):
            ws.column_dimensions[get_column_letter(i)].width = 44 if titulo == 'Observação' else max(12, min(24, len(titulo) // 2 + 6))
            for c in ws[get_column_letter(i)][2:]:
                if titulo.startswith('Tempo'):
                    c.number_format = '[h]:mm:ss'
                elif 'Acurácia' in titulo:
                    c.number_format = '0.00'
        ws.freeze_panes = 'A3'
        ws.auto_filter.ref = f'A2:{get_column_letter(len(cab))}{max(ws.max_row, 2)}'
        ws.row_dimensions[2].height = 46
    wb.save(caminho)


def gerar(agregados, pasta, linhas=()):
    """Cria PNGs e Excel em `pasta`. Retorna a lista de arquivos criados."""
    from pathlib import Path
    pasta = Path(pasta)
    criados = gerar_graficos(agregados, pasta)
    gerar_planilha(list(linhas), agregados, pasta / 'tabelas.xlsx')
    return criados + ['tabelas.xlsx']
