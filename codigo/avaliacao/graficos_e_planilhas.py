"""Gráficos (PNG) e planilha Excel gerados a partir das configurações já agregadas.

É chamado automaticamente por `comparar_configuracoes` (mesmo comando do relatório).
Saídas, na mesma pasta do relatório:
  grafico_acuracia_<N>_tokens.png - acurácia por técnica e dataset
  grafico_tokens_<N>_tokens.png   - tokens usados por questão (custo principal)
  (N = 1200 e 2400 tokens, ou os escolhidos com --tokens; o tempo fica só nas tabelas)
  tabelas.xlsx          - abas Few-shot, CoT e Self-Consistency (uma linha por EXECUÇÃO, com data e
                          hora) e Resumo (média das execuções de mesma configuração)
Tudo é refeito a cada vez que o relatório é gerado, e a data da atualização aparece nos arquivos.

Um par de gráficos é criado para cada orçamento de tokens (1200, 2400...) em que as TRÊS técnicas
têm execuções comparáveis (mesmas questões, mesmos exemplos, mesmos tokens máx.); datasets a que
falta alguma técnica não entram naquele gráfico. A configuração de cada técnica aparece na legenda.
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


def _peso(a, campo):
    return a.get(campo) or 0


def juntar_maquinas(agregados):
    """Une, para gráficos, os grupos da mesma configuração e do mesmo conjunto de questões que só
    diferem na máquina (ou por ela não estar informada). Acurácia: acertos totais / questões totais;
    tokens: média ponderada pelas questões com registro completo. A máquina não altera a acurácia
    nem os tokens; só o tempo depende dela, e o tempo não entra nos gráficos."""
    grupos = {}
    for a in agregados:
        chave = (a['dataset'], a['limite'], a['exemplos'], a['tecnica'], a.get('temperatura'),
                 a['tokens'], a['n_amostras'], a.get('conjunto'))
        grupos.setdefault(chave, []).append(a)
    saida = []
    for itens in grupos.values():
        if len(itens) == 1:
            saida.append(itens[0])
            continue
        base = dict(max(itens, key=lambda a: a['execucoes']))
        com_acc = [a for a in itens if a['acuracia_media'] is not None]
        n_acc = sum(_peso(a, 'avaliadas_total') for a in com_acc)
        if com_acc and n_acc:
            base['acuracia_media'] = sum(a['acuracia_media'] * _peso(a, 'avaliadas_total') for a in com_acc) / n_acc
        elif com_acc:
            base['acuracia_media'] = None
        for campo in ('tokens_entrada_medio', 'tokens_saida_medio'):
            ps = [(a[campo], _peso(a, 'tokens_validas_total')) for a in itens if a.get(campo) is not None]
            tot = sum(w for _, w in ps)
            if tot:
                base[campo] = sum(v * w for v, w in ps) / tot
        for campo in ('execucoes', 'avaliadas_total', 'tokens_validas_total', 'com_acuracia'):
            base[campo] = sum(_peso(a, campo) for a in itens)
        accs = [a['acuracia_min'] for a in itens if a.get('acuracia_min') is not None]
        base['acuracia_min'] = min(accs) if accs else None
        maxs = [a['acuracia_max'] for a in itens if a.get('acuracia_max') is not None]
        base['acuracia_max'] = max(maxs) if maxs else None
        base['maquina'] = 'várias'
        saida.append(base)
    return saida


def escolher_comparaveis(agregados):
    """{orçamento_de_tokens: {dataset: {técnica: agregado}}}, só com condições comparáveis.

    Em cada dataset, as três técnicas precisam ter o MESMO orçamento de tokens e o MESMO conjunto
    de questões e de exemplos (mesma impressão digital dos ids, não só a mesma quantidade). Se alguma técnica falta, o
    dataset não entra naquele gráfico. Dentro disso, cada técnica é representada pela
    configuração mais executada (na SC costuma ser temperatura 0.7 com 5 amostras)."""
    por_chave = {}
    for a in juntar_maquinas(agregados):
        if a['acuracia_media'] is None or a['tokens'] is None or a.get('conjunto') is None:
            continue          # sem ids de exemplos/questões gravados o conjunto não é verificável
        por_chave.setdefault((a['dataset'], a['tokens'], a['limite'], a['exemplos'], a.get('conjunto')), []).append(a)
    saida = {}
    for (dataset, tokens, limite, exemplos, _conjunto), grupo in por_chave.items():
        escolhidas = {}
        for t in TECNICAS:
            candidatas = [a for a in grupo if a['tecnica'] == t]
            if candidatas:
                escolhidas[t] = max(candidatas, key=lambda a: (a['execucoes'], a['n_amostras'] or 0, a.get('temperatura') or 0))
        if len(escolhidas) < len(TECNICAS):
            continue
        atual = saida.setdefault(tokens, {})
        total = sum(a['execucoes'] for a in escolhidas.values())
        if dataset not in atual or total > sum(a['execucoes'] for a in atual[dataset].values()):
            atual[dataset] = escolhidas
    return saida


def _desc_config(a):
    partes = [f"{a['tokens']} tokens" if a['tokens'] else None,
              f"temp. {a['temperatura']}" if a['temperatura'] is not None else None,
              f"{a['n_amostras']} amostras" if a['n_amostras'] else None]
    return ', '.join(p for p in partes if p)


def _grafico_barras(caminho, reps, campo, titulo, rotulo_y, formato, de_porcentagem=False, nota=''):
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
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    if nota:
        fig.text(0.01, 0.035, nota, ha='left', va='bottom', fontsize=6.5, color='#777777', wrap=True)
    fig.text(0.99, 0.008, f'Atualizado em {_agora()}', ha='right', va='bottom', fontsize=7, color='#777777')
    fig.savefig(caminho)
    plt.close(fig)
    return True


def gerar_graficos(agregados, pasta, tempo_descritivo=False, orcamentos=(1200, 2400)):
    """Gráficos para o TCC: acurácia e tokens por questão, um par para cada orçamento de tokens.

    Só entram datasets em que as três técnicas têm execuções comparáveis. O tempo fica nas tabelas
    (poucas execuções isoladas). PNGs antigos que não são desta rodada são removidos da pasta."""
    if isinstance(orcamentos, int):
        orcamentos = (orcamentos,)
    criados = []
    comparaveis = escolher_comparaveis(agregados)
    for tokens in orcamentos:
        por_dataset = comparaveis.get(tokens, {})
        if not por_dataset:
            continue
        reps = {(t, d): a for d, por_t in por_dataset.items() for t, a in por_t.items()}
        info = {d: next(iter(por_t.values())) for d, por_t in por_dataset.items()}
        nota = ('Mesmas questões, exemplos e tokens nas três técnicas. '
                + '; '.join(f"{NOME_DATASET[d]}: {i['limite'] or 'todas'} questões, {i['exemplos']} ex."
                            for d, i in info.items()))
        a1 = f'grafico_acuracia_{tokens}_tokens.png'
        a3 = f'grafico_tokens_{tokens}_tokens.png'
        _grafico_barras(pasta / a1, reps, 'acuracia_media', f'Acurácia por técnica e dataset ({tokens} tokens máx.)',
                        'Acurácia (%)', lambda v: f'{v:.1f}%'.replace('.', ','), de_porcentagem=True, nota=nota)
        reps_tok = {k: dict(a, tokens_usados=_tokens_usados(a)) for k, a in reps.items()}
        _grafico_barras(pasta / a3, reps_tok, 'tokens_usados',
                        f'Tokens usados por questão, por técnica e dataset ({tokens} tokens máx.)',
                        'Tokens por questão (entrada + saída)', lambda v: f'{v:,.0f}'.replace(',', '.'),
                        nota=nota)
        criados += [a1, a3]
    for antigo in pasta.glob('grafico_*.png'):
        if antigo.name not in criados:
            antigo.unlink()
    return criados


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


# Execuções do GSM8K/AQuA-RAT com este número de questões (ou mais) foram feitas em outro computador,
# só como teste: entram na acurácia, mas não na comparação de tempo.
LIMITE_SEM_TEMPO = 500


def _obs(l):
    notas = []
    if l['dataset'] != 'censo' and (l.get('limite_original') or 0) >= LIMITE_SEM_TEMPO:
        notas.append('teste em outro PC: tempo fora da comparação')
    elif not l.get('isolada', True):
        notas.append('rodou em paralelo: tempo fora da comparação')
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
    cab += ['Tempo médio/questão (descritivo)', 'Tempo total (descritivo)', 'Tokens médios/questão (entrada + saída)']
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


def gerar(agregados, pasta, linhas=(), orcamentos=(1200, 2400)):
    """Cria PNGs e Excel em `pasta`. Retorna a lista de arquivos criados."""
    from pathlib import Path
    pasta = Path(pasta)
    criados = gerar_graficos(agregados, pasta, any(l['maquina'] == 'não informada' for l in linhas), orcamentos)
    gerar_planilha(list(linhas), agregados, pasta / 'tabelas.xlsx')
    return criados + ['tabelas.xlsx']