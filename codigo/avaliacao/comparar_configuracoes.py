"""Compara TODAS as configurações já executadas (técnica, temperatura, tokens, amostras,
exemplos e máquina). Apenas lê os JSONs; não executa o Ollama e não altera nenhum resultado.

Uso na raiz do projeto:
  python -m codigo.avaliacao.comparar_configuracoes --revisor layla
  python -m codigo.avaliacao.comparar_configuracoes --dataset gsm8k --limite 200 --exemplos 10
  python -m codigo.avaliacao.comparar_configuracoes --recortar 200 --exemplos 10 --revisor layla
      (compara tudo nas MESMAS primeiras 200 questões, inclusive execuções feitas com limite 300, 500...)
  python -m codigo.avaliacao.comparar_configuracoes --modelo-maquinas     (cria o arquivo para anotar pc1/pc2)

Saídas: resultados/metricas/relatorios/geral/ (relatorio_geral.md e metricas_gerais.json) e
resultados/metricas/graficos_e_tabelas/ (gráficos .png e tabelas.xlsx). O relatório traz: resumo por
configuração, técnica x tokens, mesma configuração em máquinas diferentes, comparações pareadas
(McNemar exato) entre técnicas e entre valores de um mesmo parâmetro, e todas as execuções.

Execuções com falha técnica ENTRAM no relatório, com a coluna de falhas à mostra: a acurácia
é calculada nas questões sem falha. Para o Censo, a acurácia só aparece quando todas as
pendências foram revisadas (--revisor).
"""
import argparse
import itertools
import json
import re
import statistics
from datetime import datetime
from pathlib import Path

from codigo.avaliacao.comparacao_tecnicas import (
    TECNICAS, ROTULO, _ler, _momento, carregar_execucao, comparar_pareado, custo, falhas,
    resumo_acuracia, sem_substituidas)
from codigo.avaliacao.graficos_e_planilhas import formatar_duracao

RAIZ = Path(__file__).resolve().parents[2]
DATASETS = ('gsm8k', 'aqua_rat', 'censo')
STATUS_ACEITOS = ('concluido', 'concluido_com_falhas')
SUFIXOS_IGNORADOS = ('.progresso.json', '.auditado.json', '.revisoes.json', '.final.json')
# Padrões do relatório final (valem quando você roda o comando sem opções).
RECORTE_PADRAO = 200      # GSM8K e AQuA-RAT: compara todas as execuções nas mesmas primeiras 200 questões
EXEMPLOS_PADRAO = 10      # GSM8K e AQuA-RAT
EXEMPLOS_CENSO_PADRAO = 6 # Censo (protocolo); só entram execuções do Censo com todas as questões
REVISOR_PADRAO = 'layla'  # revisões humanas do Censo
SEM_MAQUINA = 'não informada'


# ---------------------------------------------------------------- máquinas (pc1 / pc2)

def _normalizar_mapa(mapa):
    """Aceita o formato simples {"prefixo": "pc1"} ou o completo
    {"execucoes": {...}, "periodos": [...], "apelidos": {...}}."""
    mapa = mapa or {}
    if any(k in mapa for k in ('execucoes', 'periodos', 'apelidos')):
        return {'execucoes': mapa.get('execucoes') or {}, 'periodos': mapa.get('periodos') or [],
                'apelidos': mapa.get('apelidos') or {}}
    return {'execucoes': mapa, 'periodos': [], 'apelidos': {}}


def carregar_maquinas(caminho):
    """Lê o arquivo de máquinas (vazio se não existir). Valores vazios são ignorados."""
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    if not isinstance(dados, dict):
        raise ValueError(f'{caminho} deve ser um objeto JSON.')
    m = _normalizar_mapa(dados)
    return {'execucoes': {str(k): str(v).strip() for k, v in m['execucoes'].items() if str(v).strip()},
            'periodos': [x for x in m['periodos'] if isinstance(x, dict) and x.get('maquina')],
            'apelidos': {str(k): str(v) for k, v in m['apelidos'].items() if str(v).strip()}}


def maquina_de(dados, arquivo, mapa):
    """Descobre a máquina da execução, nesta ordem:
    1) 'ambiente' gravado pelo executor (nome da máquina; 'apelidos' traduz para pc1/pc2);
    2) 'execucoes': id ou início do id/nome do arquivo (vale o prefixo mais longo);
    3) 'periodos': de/ate (AAAA-MM-DD) na data de início, com tecnica e dataset opcionais."""
    m = _normalizar_mapa(mapa)
    ambiente = dados.get('ambiente') or {}
    # 'identificador' (pc1/pc2 de config_maquina.json) vale mais que o nome do computador.
    bruto = ambiente.get('identificador') or ambiente.get('maquina') or ambiente.get('sistema')
    if bruto:
        return str(m['apelidos'].get(str(bruto), bruto))
    nomes = (str(dados.get('id_execucao') or ''), Path(arquivo).stem)
    achadas = [(len(chave), valor) for chave, valor in m['execucoes'].items()
               if str(valor).strip() and any(nome.startswith(chave) for nome in nomes if nome)]
    if achadas:
        return max(achadas)[1]
    data = str(dados.get('data_inicio') or '')[:10]
    for periodo in m['periodos']:
        if (data and str(periodo.get('de') or '0000') <= data <= str(periodo.get('ate') or '9999')
                and periodo.get('tecnica') in (None, dados.get('tecnica'))
                and periodo.get('dataset') in (None, dados.get('dataset'))):
            return str(periodo['maquina'])
    return SEM_MAQUINA


def modelo_de_maquinas(arquivos):
    """Modelo para preencher. Use 'periodos' para marcar vários dias de uma vez, 'execucoes' para
    casos soltos e 'apelidos' para traduzir o nome gravado pelo executor (ex.: "MEU-PC": "pc1")."""
    ids, datas = {}, {}
    for arquivo in arquivos:
        try:
            dados = _ler(arquivo)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        ids[str(dados.get('id_execucao') or Path(arquivo).stem)] = ''
        dia = str(dados.get('data_inicio') or '')[:10]
        if dia:
            datas[dia] = datas.get(dia, 0) + 1
    return {
        '_ajuda': 'Preencha "periodos" (de/ate no formato AAAA-MM-DD, tecnica e dataset opcionais) '
                  'ou "execucoes" (id ou início do id -> pc1/pc2). "apelidos" traduz o nome da máquina '
                  'gravado pelas execuções novas. Campos que começam com _ são ignorados.',
        '_exemplo_periodo': {'de': '2026-11-05', 'ate': '2026-11-06', 'maquina': 'pc2',
                             'tecnica': 'self_consistency', 'dataset': 'gsm8k'},
        '_execucoes_por_dia': dict(sorted(datas.items())),
        'apelidos': {},
        'periodos': [],
        'execucoes': dict(sorted(ids.items())),
    }


# ---------------------------------------------------------------- leitura das execuções

def listar_arquivos(pasta, datasets=DATASETS):
    """Execuções finalizadas de cada técnica/dataset. Substitui originais pelas recuperações."""
    pasta = Path(pasta)
    encontrados = []
    for tecnica in TECNICAS:
        for dataset in datasets:
            base = pasta / tecnica / dataset
            if not base.exists():
                continue
            candidatos = []
            for arquivo in sorted(base.rglob('*.json')):
                if arquivo.name.endswith(SUFIXOS_IGNORADOS):
                    continue
                try:
                    dados = _ler(arquivo)
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
                if (dados.get('tecnica') == tecnica and dados.get('dataset') == dataset
                        and dados.get('status') in STATUS_ACEITOS):
                    candidatos.append(arquivo)
            encontrados += sem_substituidas(candidatos)
    return encontrados


def linha_execucao(arquivo, revisor=None, mapa=None, ids=None):
    """Uma linha de resumo por execução, ou None se o arquivo não puder ser lido.

    ids: se informado, só essas questões entram nas contas (recorte comum entre execuções)."""
    try:
        execucao = carregar_execucao(arquivo, revisor)
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    if ids is not None:
        execucao['questoes'] = [q for q in execucao['questoes'] if q['id'] in ids]
    dados = execucao['dados']
    p = dados.get('parametros') or {}
    r = resumo_acuracia(execucao)
    c = custo(execucao)
    f = falhas(execucao)
    inicio = dados.get('data_inicio') or ''
    return {
        'tecnica': execucao['tecnica'], 'dataset': execucao['dataset'],
        'arquivo': str(arquivo), 'id_execucao': dados.get('id_execucao') or Path(arquivo).stem,
        'data': inicio[:19] if inicio else _momento(arquivo).isoformat(timespec='seconds'),
        'status': dados.get('status'), 'modelo': p.get('modelo'),
        'temperatura': p.get('temperatura', p.get('temperature')),
        'tokens': p.get('maximo_tokens_resposta', p.get('num_predict')),
        'n_amostras': p.get('n_amostras'), 'exemplos': p.get('quantidade_exemplos'),
        'limite': p.get('limite'), 'maquina': maquina_de(dados, arquivo, mapa or {}),
        'planejadas': r['questoes'], 'avaliadas': r['avaliadas'],
        'falhas_tecnicas': r['falhas_tecnicas'], 'pendentes': r['pendentes'],
        'acertos': r['acertos'], 'acuracia': r['acuracia'], 'ic95': r['ic95'],
        'minimo': r['minimo'], 'maximo': r['maximo'],
        'tempo_medio_s': c['tempo_medio_s'], 'tokens_entrada_medio': c['tokens_entrada_medio'],
        'tokens_saida_medio': c['tokens_saida_medio'],
        'amostras_sem_extracao': f['amostras_sem_extracao'], 'total_amostras': f['total_amostras'],
        'recuperacao_de': dados.get('recuperacao_de'),
        # Nenhuma amostra gerou resposta extraível: quase sempre é defeito do extrator/agente
        # da época, não desempenho do modelo. Fica fora das médias.
        'suspeita': bool(f['total_amostras']) and f['amostras_sem_extracao'] == f['total_amostras'],
        'recorte': ids is not None,
        '_execucao': execucao,     # uso interno (comparações pareadas); não vai para o JSON/CSV
    }


def _ids_questoes(dados):
    p = dados.get('parametros') or {}
    ids = p.get('ids_questoes') or (p.get('protocolo') or {}).get('ids_questoes') or []
    return [str(i) for i in ids]


def _ids_exemplos(dados):
    p = dados.get('parametros') or {}
    ids = p.get('ids_exemplos') or (p.get('protocolo') or {}).get('ids_exemplos') or []
    return tuple(str(i) for i in ids)


def coletar_com_avisos(pasta, datasets=DATASETS, revisor=None, mapa=None, limite='qualquer',
                       exemplos=None, recortar=None, exemplos_censo=None):
    """(linhas, avisos). Com recortar=N, todas as execuções com pelo menos N questões entram
    avaliadas nas MESMAS primeiras N questões, desde que os exemplos e a ordem das questões sejam
    os mesmos (conferido pelos ids gravados em cada JSON)."""
    avisos, linhas = [], []
    arquivos = listar_arquivos(pasta, datasets)
    referencias, ids_por_arquivo = {}, {}
    if recortar:
        for arquivo in arquivos:
            try:
                dados = _ler(arquivo)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if dados.get('dataset') == 'censo':
                continue          # Censo usa todas as suas questões (não é recortado)
            ids = _ids_questoes(dados)
            grupo = (dados.get('dataset'), _ids_exemplos(dados))
            if len(ids) < recortar:
                avisos.append(f'{Path(arquivo).name}: fora do recorte (tem {len(ids)} questões, menos que {recortar}).')
                continue
            referencia = referencias.setdefault(grupo, ids[:recortar])
            if ids[:recortar] != referencia:
                avisos.append(f'{Path(arquivo).name}: fora do recorte (as primeiras {recortar} questões '
                              'ou os exemplos são diferentes dos demais).')
                continue
            ids_por_arquivo[str(arquivo)] = set(referencia)
    for arquivo in arquivos:
        ids = None
        e_censo = '/censo/' in str(arquivo).replace('\\', '/')
        if recortar and not e_censo:
            ids = ids_por_arquivo.get(str(arquivo))
            if ids is None:
                continue
        linha = linha_execucao(arquivo, revisor, mapa, ids)
        if linha is None:
            continue
        if recortar and linha['dataset'] != 'censo':
            linha['limite'] = recortar
        if limite != 'qualquer' and linha['limite'] != limite and linha['dataset'] != 'censo':
            continue
        if linha['dataset'] == 'censo':
            # relatório final: só o Censo completo (todas as questões); testes parciais ficam de fora
            if recortar and linha['limite'] is not None:
                continue
            if exemplos_censo is not None and linha['exemplos'] != exemplos_censo:
                continue
        # --exemplos vale para GSM8K/AQuA-RAT; o Censo usa o número de exemplos do protocolo.
        if exemplos is not None and linha['dataset'] != 'censo' and linha['exemplos'] != exemplos:
            continue
        linhas.append(linha)
    return linhas, avisos


def coletar(pasta, datasets=DATASETS, revisor=None, mapa=None, limite='qualquer', exemplos=None,
            recortar=None, exemplos_censo=None):
    return coletar_com_avisos(pasta, datasets, revisor, mapa, limite, exemplos, recortar, exemplos_censo)[0]


# ---------------------------------------------------------------- agregação

def _ordem(valor):
    return (valor is None, valor if isinstance(valor, (int, float)) else 0)


def _chave_cenario(l):
    return (l['dataset'], l['limite'], l['exemplos'])


def _chave_config(l):
    # Máquinas identificadas separam os grupos (permite comparar pc1 x pc2); as não identificadas
    # ficam juntas num grupo só.
    return (l['tecnica'], l['temperatura'], l['tokens'], l['n_amostras'], l['maquina'])


def agregar(linhas):
    """Agrupa as execuções de mesma configuração (e mesmo conjunto de questões)."""
    grupos = {}
    for l in linhas:
        grupos.setdefault((_chave_cenario(l), _chave_config(l)), []).append(l)
    saida = []
    for (cenario, config), itens in grupos.items():
        accs = [i['acuracia'] for i in itens if i['acuracia'] is not None and not i['suspeita']]
        tempos = [i['tempo_medio_s'] for i in itens if i['tempo_medio_s'] is not None]
        saida.append({
            'dataset': cenario[0], 'limite': cenario[1], 'exemplos': cenario[2],
            'tecnica': config[0], 'temperatura': config[1], 'tokens': config[2],
            'n_amostras': config[3], 'maquina': config[4],
            'execucoes': len(itens),
            'questoes_avaliadas': max((i['avaliadas'] for i in itens), default=None),
            'execucoes_com_falha': sum(i['falhas_tecnicas'] > 0 for i in itens),
            'execucoes_suspeitas': sum(i['suspeita'] for i in itens),
            'execucoes_com_pendencia': sum(i['pendentes'] > 0 for i in itens),
            'com_acuracia': len(accs),
            'acuracia_media': statistics.mean(accs) if accs else None,
            'acuracia_min': min(accs) if accs else None,
            'acuracia_max': max(accs) if accs else None,
            'acuracia_desvio': statistics.stdev(accs) if len(accs) > 1 else None,
            'tempo_medio_s': statistics.mean(tempos) if tempos else None,
            'tokens_entrada_medio': statistics.mean([i['tokens_entrada_medio'] for i in itens if i['tokens_entrada_medio'] is not None]) if any(i['tokens_entrada_medio'] is not None for i in itens) else None,
            'tokens_saida_medio': statistics.mean([i['tokens_saida_medio'] for i in itens if i['tokens_saida_medio'] is not None]) if any(i['tokens_saida_medio'] is not None for i in itens) else None,
            'falhas_tecnicas_total': sum(i['falhas_tecnicas'] for i in itens),
            'pendentes_total': sum(i['pendentes'] for i in itens),
            'ids_execucoes': [i['id_execucao'] for i in itens],
            'maquinas_identificadas': sorted({i['maquina'] for i in itens if i['maquina'] != SEM_MAQUINA}),
        })
    saida.sort(key=lambda a: (a['dataset'], _ordem(a['limite']), _ordem(a['exemplos']),
                              TECNICAS.index(a['tecnica']), _ordem(a['temperatura']),
                              _ordem(a['tokens']), _ordem(a['n_amostras']), a['maquina']))
    return saida


def matriz_tokens(agregados):
    """Acurácia média por (técnica, temperatura, amostras) x tokens, juntando as máquinas."""
    linhas = {}
    for a in agregados:
        if a['acuracia_media'] is None:
            continue
        chave = (a['tecnica'], a['temperatura'], a['n_amostras'])
        celula = linhas.setdefault(chave, {}).setdefault(a['tokens'], [])
        celula.append((a['acuracia_media'], a['com_acuracia']))
    saida = {}
    for chave, por_tokens in linhas.items():
        saida[chave] = {}
        for tokens, itens in por_tokens.items():
            peso = sum(n for _, n in itens)
            saida[chave][tokens] = (sum(v * n for v, n in itens) / peso, peso)
    return saida


def entre_maquinas(agregados):
    """Configurações iguais que foram rodadas em mais de uma máquina."""
    grupos = {}
    for a in agregados:
        if a['maquina'] == SEM_MAQUINA:
            continue
        chave = (a['tecnica'], a['temperatura'], a['tokens'], a['n_amostras'])
        grupos.setdefault(chave, {})[a['maquina']] = a
    return {k: v for k, v in grupos.items() if len(v) > 1}


# ---------------------------------------------------------------- comparações pareadas

def _cfg(l):
    return (l['tecnica'], l['temperatura'], l['tokens'], l['n_amostras'])


def escolher_referencia(runs):
    """Execução que representa a configuração nas comparações pareadas: a que tem menos falhas
    técnicas e, em empate, a mais recente. Ignora suspeitas e as sem acurácia (pendentes)."""
    boas = [r for r in runs if not r['suspeita'] and r['acuracia'] is not None and '_execucao' in r]
    return max(boas, key=lambda r: (-r['falhas_tecnicas'], r['data'])) if boas else None


def descrever(l):
    c = _cfg(l)
    partes = [ROTULO[c[0]]]
    if c[1] is not None:
        partes.append(f't={c[1]}')
    if c[3] is not None:
        partes.append(f'{c[3]} amostras')
    partes.append(f'{_val(c[2])} tokens')
    return ' / '.join(partes) + f' [{l["data"][5:16].replace("T", " ")}]'


def _par(cenario, tipo, fator, a, b):
    # Não declarar comparação controlada quando os exemplos documentados divergem.
    da, db = a['_execucao']['dados'], b['_execucao']['dados']
    ea, eb = _ids_exemplos(da), _ids_exemplos(db)
    if ea and eb and ea != eb:
        return None
    pa, pb = da.get('parametros') or {}, db.get('parametros') or {}
    for chave in ('modelo', 'num_ctx', 'top_k', 'top_p'):
        if pa.get(chave) is not None and pb.get(chave) is not None and pa[chave] != pb[chave]:
            return None
    r = comparar_pareado(a['_execucao'], b['_execucao'])
    if not r['n_pareado']:
        return None
    return {'dataset': cenario[0], 'limite': cenario[1], 'exemplos': cenario[2], 'tipo': tipo,
            'fator': fator, 'a': descrever(a), 'b': descrever(b), 'execucao_a': a['id_execucao'],
            'execucao_b': b['id_execucao'], 'n': r['n_pareado'], 'acuracia_a': r['acuracia_a'],
            'acuracia_b': r['acuracia_b'], 'diferenca_pp': r['diferenca_pp'], 'so_a': r['so_a'],
            'so_b': r['so_b'], 'p': r['p_mcnemar']}


def comparacoes_pareadas(linhas):
    """McNemar exato (nas questões em comum) entre:
    - técnicas, com o mesmo orçamento de tokens (Few-shot x CoT, e cada um contra cada SC);
    - configurações da MESMA técnica que diferem em um único parâmetro (tokens, temperatura, amostras).
    Cada configuração é representada por uma execução (ver escolher_referencia)."""
    saida = []
    cenarios = {}
    for l in linhas:
        cenarios.setdefault(_chave_cenario(l), {}).setdefault(_cfg(l), []).append(l)
    for cenario, por_cfg in sorted(cenarios.items(), key=lambda kv: (kv[0][0], _ordem(kv[0][1]), _ordem(kv[0][2]))):
        refs = {c: escolher_referencia(runs) for c, runs in por_cfg.items()}
        refs = {c: r for c, r in refs.items() if r is not None}
        tokens = sorted({c[2] for c in refs}, key=_ordem)
        for tk in tokens:
            do_tk = {c: r for c, r in refs.items() if c[2] == tk}
            few = [r for c, r in do_tk.items() if c[0] == 'few_shot']
            cot = [r for c, r in do_tk.items() if c[0] == 'chain_of_thought']
            sc = [r for c, r in sorted(do_tk.items(), key=lambda kv: (_ordem(kv[0][1]), _ordem(kv[0][3])))
                  if c[0] == 'self_consistency']
            pares = [(a, b) for a in few for b in cot] + [(a, b) for a in few + cot for b in sc]
            for a, b in pares:
                linha = _par(cenario, 'tecnicas', f'{tk} tokens', a, b)
                if linha:
                    saida.append(linha)
        for c1, c2 in itertools.combinations(sorted(refs, key=lambda c: (TECNICAS.index(c[0]), _ordem(c[1]), _ordem(c[2]), _ordem(c[3]))), 2):
            if c1[0] != c2[0]:
                continue
            diferentes = [i for i in (1, 2, 3) if c1[i] != c2[i]]
            if len(diferentes) != 1:
                continue
            nome = {1: 'temperatura', 2: 'tokens', 3: 'amostras'}[diferentes[0]]
            a, b = sorted((refs[c1], refs[c2]), key=lambda r: _ordem(_cfg(r)[diferentes[0]]))
            linha = _par(cenario, 'fator', nome, a, b)
            if linha:
                saida.append(linha)
    return saida


# ---------------------------------------------------------------- relatório

def _pct(v):
    return '—' if v is None else f'{100 * v:.2f}%'


def _num(v, casas=1):
    return '—' if v is None else f'{v:.{casas}f}'


def _val(v):
    return '—' if v is None else str(v)


def _tabela(cabecalho, linhas):
    return '\n'.join(['| ' + ' | '.join(cabecalho) + ' |',
                      '| ' + ' | '.join('---' for _ in cabecalho) + ' |'] +
                     ['| ' + ' | '.join(map(str, l)) + ' |' for l in linhas])


def _obs(l):
    notas = []
    if l['suspeita']:
        notas.append('SUSPEITA: nenhuma amostra com resposta (fora das médias)')
    if l['falhas_tecnicas']:
        notas.append(f'{l["falhas_tecnicas"]} falha(s) técnica(s)')
    if l['pendentes']:
        notas.append(f'{l["pendentes"]} pendente(s) de revisão')
    if l['recuperacao_de']:
        notas.append('recuperação')
    return '; '.join(notas) or '—'


def _titulo_cenario(dataset, limite, exemplos):
    q = 'todas as questões' if limite is None else f'limite {limite}'
    return f'{dataset.upper()} — {q}, {_val(exemplos)} exemplos'


def para_markdown(linhas, agregados, filtros=None, pareadas=None, avisos=None):
    out = ['# Comparação de configurações', '',
           f'Gerado em {datetime.now().isoformat(timespec="minutes")}. '
           f'{len(linhas)} execuções lidas. Filtros: {filtros or "nenhum"}.', '',
           'Leitura: só se comparam execuções do MESMO conjunto de questões (cada seção abaixo). '
           '"Com falha" = execuções com ao menos uma falha técnica; a acurácia delas usa só as '
           'questões sem falha. "Suspeitas" = execuções em que nenhuma amostra gerou resposta; ficam fora das médias. '
           'Tempo só é comparável dentro da mesma máquina. Repetir a MESMA configuração com a mesma semente '
           'repete (quase) o mesmo resultado: a variação entre repetições mede repetibilidade, não a incerteza '
           'de uma amostragem nova.', '']
    if avisos:
        out += ['Avisos:', ''] + [f'- {a}' for a in avisos] + ['']
    com_maquina = any(l['maquina'] != SEM_MAQUINA for l in linhas)
    cenarios = sorted({(a['dataset'], a['limite'], a['exemplos']) for a in agregados},
                      key=lambda c: (c[0], _ordem(c[1]), _ordem(c[2])))
    for dataset, limite, exemplos in cenarios:
        ags = [a for a in agregados if (a['dataset'], a['limite'], a['exemplos']) == (dataset, limite, exemplos)]
        runs = [l for l in linhas if _chave_cenario(l) == (dataset, limite, exemplos)]
        out += [f'## {_titulo_cenario(dataset, limite, exemplos)}', '', '### Resumo por configuração', '']
        out.append(_tabela(
            ('Técnica', 'Temp.', 'Tokens', 'Amostras') + (('Máquina',) if com_maquina else ()) +
            ('Execuções', 'Com falha', 'Suspeitas', 'Pendentes', 'Acurácia média', 'Mín–Máx', 'Tempo médio (s)'),
            [(ROTULO[a['tecnica']], _val(a['temperatura']), _val(a['tokens']), _val(a['n_amostras'])) +
             ((a['maquina'],) if com_maquina else ()) + (a['execucoes'], a['execucoes_com_falha'], a['execucoes_suspeitas'], a['pendentes_total'],
              _pct(a['acuracia_media']),
              f'{_pct(a["acuracia_min"])} – {_pct(a["acuracia_max"])}' if a['acuracia_media'] is not None else '—',
              _num(a['tempo_medio_s'])) for a in ags]))
        matriz = matriz_tokens(ags)
        tokens = sorted({t for v in matriz.values() for t in v}, key=_ordem)
        if matriz and len(tokens) > 1:
            out += ['', '### Técnica × tokens (acurácia média; n = execuções com acurácia)', '']
            out.append(_tabela(
                ('Técnica', 'Temp.', 'Amostras') + tuple(f'{t} tokens' for t in tokens),
                [(ROTULO[k[0]], _val(k[1]), _val(k[2])) + tuple(
                    f'{_pct(v[t][0])} (n={v[t][1]})' if t in v else '—' for t in tokens)
                 for k, v in sorted(matriz.items(), key=lambda kv: (TECNICAS.index(kv[0][0]), _ordem(kv[0][1]), _ordem(kv[0][2])))]))
        maq = entre_maquinas(ags)
        if maq:
            nomes = sorted({m for v in maq.values() for m in v})
            out += ['', '### Mesma configuração em máquinas diferentes', '']
            out.append(_tabela(
                ('Técnica', 'Temp.', 'Tokens', 'Amostras') + tuple(f'{m}: acurácia / tempo (s)' for m in nomes),
                [(ROTULO[k[0]], _val(k[1]), _val(k[2]), _val(k[3])) + tuple(
                    f'{_pct(v[m]["acuracia_media"])} / {_num(v[m]["tempo_medio_s"])}' if m in v else '—' for m in nomes)
                 for k, v in sorted(maq.items(), key=lambda kv: (TECNICAS.index(kv[0][0]), _ordem(kv[0][1]), _ordem(kv[0][2]), _ordem(kv[0][3])))]))
        pares = [x for x in (pareadas or []) if (x['dataset'], x['limite'], x['exemplos']) == (dataset, limite, exemplos)]
        cab = ('A', 'B', 'N comum', 'Acurácia A', 'Acurácia B', 'Diferença B−A (pp)', 'Só A', 'Só B', 'p (McNemar exato)')

        def linha_par(x):
            return (x['a'], x['b'], x['n'], _pct(x['acuracia_a']), _pct(x['acuracia_b']),
                    _num(x['diferenca_pp'], 2), x['so_a'], x['so_b'], _num(x['p'], 4))
        entre = [x for x in pares if x['tipo'] == 'tecnicas']
        if entre:
            out += ['', '### Comparação entre técnicas (mesmo orçamento de tokens; McNemar exato)', '']
            out.append(_tabela(('Tokens',) + cab, [(x['fator'].split()[0],) + linha_par(x) for x in entre]))
        fator = [x for x in pares if x['tipo'] == 'fator']
        if fator:
            out += ['', '### Efeito de um parâmetro isolado (mesma técnica; só um parâmetro muda; McNemar exato)', '']
            out.append(_tabela(('Parâmetro',) + cab, [(x['fator'],) + linha_par(x) for x in fator]))
        if entre or fator:
            out += ['', 'Cada configuração é representada por UMA execução (a com menos falhas técnicas e, em empate, '
                    'a mais recente), nas questões em comum. São vários testes sem correção de múltiplas '
                    'comparações; p-valores baixos isolados devem ser lidos com cautela. Diferença estatística não '
                    'implica benefício prático.']
        out += ['', '### Todas as execuções', '']
        runs.sort(key=lambda l: (TECNICAS.index(l['tecnica']), _ordem(l['temperatura']),
                                 _ordem(l['tokens']), _ordem(l['n_amostras']), l['data']))
        out.append(_tabela(
            ('Execução', 'Técnica', 'Temp.', 'Tokens', 'Amostras') + (('Máquina',) if com_maquina else ()) +
            ('Questões', 'Falhas', 'Pendentes',
             'Acertos', 'Acurácia', 'IC Wilson 95%', 'Tempo (s)', 'Amostras sem extração', 'Obs.'),
            [(l['id_execucao'], ROTULO[l['tecnica']], _val(l['temperatura']), _val(l['tokens']),
              _val(l['n_amostras'])) + ((l['maquina'],) if com_maquina else ()) + (l['avaliadas'], l['falhas_tecnicas'], l['pendentes'],
              l['acertos'],
              _pct(l['acuracia']) if l['acuracia'] is not None else f'{_pct(l["minimo"])} a {_pct(l["maximo"])} (pendente)',
              f'{_pct(l["ic95"][0])} a {_pct(l["ic95"][1])}' if l['ic95'] else '—',
              _num(l['tempo_medio_s']),
              f'{l["amostras_sem_extracao"]}/{l["total_amostras"]}' if l['total_amostras'] else '—',
              _obs(l)) for l in runs]))
        out.append('')
    sem_maquina = sum(l['maquina'] == SEM_MAQUINA for l in linhas)
    if com_maquina and sem_maquina:
        out += [f'Atenção: {sem_maquina} execuções sem máquina informada. Use --modelo-maquinas e '
                'preencha pc1/pc2 para separar as máquinas.', '']
    return '\n'.join(out)


def _publica(linha):
    return {k: v for k, v in linha.items() if not k.startswith('_')}




def relatorio_principal(linhas, agregados, pareadas, avisos):
    """Síntese legível para TCC. Dados detalhados permanecem no JSON.

    Não combina resultados de configurações diferentes em uma acurácia única.
    Acurácias são médias entre execuções da mesma configuração, não uma
    estimativa agrupada por questão. Comparações pareadas ficam no JSON.
    """
    out = ['# Resultados experimentais — síntese para o TCC', '',
           f'Atualizado em {datetime.now():%d/%m/%Y %H:%M}. Execuções consideradas: **{len(linhas)}**. '
           'As tabelas são recriadas a partir dos JSONs sempre que este script é executado.', '',
           '**Pergunta de pesquisa:** a Self-Consistency oferece ganhos de acurácia '
           'que compensam o aumento de tempo e tokens em relação a Few-shot e CoT?', '',
           '**Leitura:** cada linha é uma configuração experimental. Acurácia indisponível '
           'significa ausência de veredito completo (especialmente no Censo). '
           'Execuções com falhas técnicas são sinalizadas; elas não são descartadas. '
           'A coluna de computador foi omitida porque a origem não é conhecida em todos os JSONs.', '']
    sem_identificacao = any(l['maquina'] == SEM_MAQUINA for l in linhas)
    com_maquina = any(l['maquina'] != SEM_MAQUINA for l in linhas)
    for ds in DATASETS:
        grupos = [a for a in agregados if a['dataset'] == ds]
        if not grupos:
            continue
        out += [f'## {ds.upper()}', '',
                '### Acurácia e custo por configuração', '']
        grupos.sort(key=lambda a: (_ordem(a['limite']), _ordem(a['exemplos']),
                    TECNICAS.index(a['tecnica']), _ordem(a['temperatura']),
                    _ordem(a['tokens']), _ordem(a['n_amostras'])))
        out.append(_tabela(
            ('Técnica', 'Questões (limite)', 'Ex.', 'Temp.', 'Tokens máx.', 'Amostras') +
            (('Máquina',) if com_maquina else ()) + ('Exec.', 'Acurácia média', 'Tokens usados/questão', 'Tempo médio/questão*', 'Falhas técnicas'),
            [(ROTULO[a['tecnica']], _val(a['limite']) if a['limite'] is not None else 'Todas',
              _val(a['exemplos']), _val(a['temperatura']), _val(a['tokens']),
              _val(a['n_amostras'])) + ((a['maquina'],) if com_maquina else ()) + (a['execucoes'], _pct(a['acuracia_media']),
              _num((a['tokens_entrada_medio'] or 0) + (a['tokens_saida_medio'] or 0), 0)
              if a['tokens_entrada_medio'] is not None and a['tokens_saida_medio'] is not None else '—',
              formatar_duracao(a['tempo_medio_s']), a['falhas_tecnicas_total']) for a in grupos]))
        ds_pares = [x for x in pareadas if x['dataset'] == ds and x['tipo'] == 'tecnicas']
        if ds_pares:
            out += ['', '### Diferença de acurácia nas mesmas questões', '']
            out.append(_tabela(('Comparação', 'N comum', 'Diferença B−A (pp)', 'p McNemar'),
                [(f'{x["a"]} × {x["b"]}', x['n'], _num(x['diferenca_pp'], 2),
                  _num(x['p'], 4)) for x in ds_pares]))
        if sem_identificacao:
            out += ['', '*Tempos meramente descritivos: computadores não identificados.*']
        out += ['', '### Interpretação', '',
                'Compare primeiro a diferença de acurácia em questões pareadas. '
                'Depois consulte os custos por execução em `tabelas.xlsx` '
                '(tokens de entrada/saída e tempo médio). O limite máximo de tokens '
                'não é o número de tokens efetivamente consumidos. '
                + ('**Não é possível concluir que uma técnica é mais rápida apenas '
                   'pelos tempos misturados de PC1 e PC2.**' if sem_identificacao else
                   'Compare tempos apenas entre execuções da mesma máquina.'), '']
    out += ['## Limitações e cuidados', '',
            '- A análise inclui todas as configurações encontradas; não pressupõe que todas as combinações foram executadas.',
            '- Comparações pareadas usam questões com veredito válido em ambos os experimentos; confira também exemplos e parâmetros antes de interpretar causalmente.',
            '- O Censo exige revisão humana dos casos pendentes para uma acurácia definitiva.',
            '- Falhas técnicas e recuperações são rastreadas; os arquivos originais não são modificados.',
            *(['- Tempos medidos em máquinas não identificadas devem ser tratados apenas como dados descritivos.']
              if sem_identificacao else []),
            '- A decisão custo-benefício deve considerar o ganho de acurácia e o consumo efetivo de tokens, não apenas o teto configurado.', '']
    if avisos:
        out += ['## Avisos de processamento', ''] + [f'- {a}' for a in avisos] + ['']
    return '\n'.join(out)

def _resumir_avisos(avisos):
    """Junta os avisos repetitivos de 'fora do recorte (menos questões)' numa linha só."""
    curtos = [a for a in avisos if 'menos que' in a and 'fora do recorte' in a]
    outros = [a for a in avisos if a not in curtos]
    if curtos:
        outros.insert(0, f'{len(curtos)} execução(ões) de teste, com menos questões que o recorte, ficaram de fora.')
    return outros


def gerar(pasta, saida, datasets=DATASETS, revisor=None, maquinas=None, limite='qualquer', exemplos=None,
          recortar=None, detalhado=False, exemplos_censo=None, saida_dados=None):
    """saida: gráficos e Excel. saida_dados: relatório .md e .json (padrão: a mesma pasta)."""
    mapa = carregar_maquinas(maquinas) if maquinas else {}
    linhas, avisos = coletar_com_avisos(pasta, datasets, revisor, mapa, limite, exemplos, recortar, exemplos_censo)
    avisos = _resumir_avisos(avisos)
    agregados = agregar(linhas)
    pareadas = comparacoes_pareadas(linhas)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    dados_dir = Path(saida_dados) if saida_dados else saida
    dados_dir.mkdir(parents=True, exist_ok=True)
    filtros = ', '.join(f'{k}={v}' for k, v in (('datasets', ','.join(datasets)), ('revisor', revisor),
                        ('limite', None if limite == 'qualquer' else limite), ('exemplos', exemplos),
                        ('recorte', f'primeiras {recortar} questões' if recortar else None))
                        if v not in (None, ''))
    texto = (para_markdown(linhas, agregados, filtros, pareadas, avisos) if detalhado
             else relatorio_principal(linhas, agregados, pareadas, avisos))
    (dados_dir / 'relatorio_geral.md').write_text(texto, encoding='utf-8')
    (dados_dir / 'metricas_gerais.json').write_text(
        json.dumps({'execucoes': [_publica(l) for l in linhas], 'configuracoes': agregados,
                    'comparacoes_pareadas': pareadas, 'avisos': avisos},
                   ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    try:
        from codigo.avaliacao.graficos_e_planilhas import gerar as gerar_extras
        gerar_extras(agregados, saida, linhas)
    except ImportError as erro:   # matplotlib/openpyxl ausentes: o relatório segue sem gráficos
        avisos.append(f'Gráficos/Excel não gerados ({erro}). Instale: pip install matplotlib openpyxl')
    return linhas, agregados, texto


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--pasta', default=str(RAIZ / 'resultados'))
    p.add_argument('--dataset', action='append', choices=DATASETS)
    p.add_argument('--limite', default='qualquer', help='número, "todos" ou "qualquer"')
    p.add_argument('--exemplos', type=int, default=EXEMPLOS_PADRAO,
                   help=f'exemplos de GSM8K/AQuA-RAT (padrão {EXEMPLOS_PADRAO}; 0 = qualquer)')
    p.add_argument('--recortar', type=int, metavar='N', default=RECORTE_PADRAO,
                   help=f'avalia as execuções com >= N questões nas MESMAS primeiras N (padrão {RECORTE_PADRAO}; 0 = sem recorte)')
    p.add_argument('--exemplos-censo', type=int, default=EXEMPLOS_CENSO_PADRAO,
                   help=f'exemplos do Censo (padrão {EXEMPLOS_CENSO_PADRAO}; 0 = qualquer)')
    p.add_argument('--revisor', default=REVISOR_PADRAO, help=f'revisor do Censo (padrão {REVISOR_PADRAO})')
    p.add_argument('--maquinas', default=None, help='JSON {"id_ou_prefixo": "pc1"}')
    p.add_argument('--saida', default=None, help='gráficos e Excel (padrão resultados/metricas/graficos_e_tabelas)')
    p.add_argument('--saida-dados', default=None, help='relatório e JSON (padrão resultados/metricas/relatorios/geral)')
    p.add_argument('--detalhado', action='store_true',
                   help='relatório longo, com todas as execuções e testes estatísticos')
    p.add_argument('--modelo-maquinas', action='store_true',
                   help='cria resultados/metricas/maquinas.json (se não existir) com todas as execuções')
    args = p.parse_args(argv)
    pasta = Path(args.pasta)
    destino_maquinas = Path(args.maquinas) if args.maquinas else pasta / 'metricas' / 'maquinas.json'
    if args.modelo_maquinas:
        if destino_maquinas.exists():
            print(f'Já existe: {destino_maquinas}. Edite-o; nada foi sobrescrito.')
            return 1
        arquivos = listar_arquivos(pasta, args.dataset or DATASETS)
        destino_maquinas.parent.mkdir(parents=True, exist_ok=True)
        destino_maquinas.write_text(json.dumps(modelo_de_maquinas(arquivos), ensure_ascii=False, indent=2),
                                    encoding='utf-8')
        print(f'Modelo criado em {destino_maquinas}: troque "" por "pc1" ou "pc2" em cada execução '
              '(também vale escrever só o início do nome, ex. "self_consistency_censo_08112026").')
        return 0
    limite = args.limite if args.limite == 'qualquer' else (None if args.limite == 'todos' else int(args.limite))
    saida = Path(args.saida) if args.saida else pasta / 'metricas' / 'graficos_e_tabelas'
    saida_dados = Path(args.saida_dados) if args.saida_dados else pasta / 'metricas' / 'relatorios' / 'geral'
    linhas, _, texto = gerar(pasta, saida, tuple(args.dataset or DATASETS), args.revisor,
                             destino_maquinas, limite, args.exemplos or None, args.recortar or None, args.detalhado,
                             args.exemplos_censo or None, saida_dados)
    if not linhas:
        print('Nenhuma execução concluída encontrada em', pasta)
        return 1
    print(texto)
    print('Gráficos e Excel em:', saida)
    print('Relatório (relatorio_geral.md) e JSON (metricas_gerais.json) em:', saida_dados)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
