"""Avaliação experimental do TCC. Apenas lê resultados JSON; não executa Ollama.

Uso na raiz do projeto:
  python -m codigo.avaliacao.comparacao_tecnicas gsm8k --limite todos --exemplos 10
  python -m codigo.avaliacao.comparacao_tecnicas censo --revisor layla
  python -m codigo.avaliacao.comparacao_tecnicas aqua_rat --few ARQUIVO --cot ARQUIVO --sc ARQUIVO

Os arquivos selecionados são sempre identificados no relatório. Para análise
principal, prefira --few/--cot/--sc e confira os parâmetros experimentais.
"""
import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path

from codigo.revisao_humana import acertos_finais, carregar_revisoes, intervalo_wilson, mcnemar_exato
from codigo.avaliacao.analise_self_consistency import analisar

RAIZ = Path(__file__).resolve().parents[2]
TECNICAS = ('few_shot', 'chain_of_thought', 'self_consistency')
ROTULO = {'few_shot': 'Few-shot', 'chain_of_thought': 'CoT', 'self_consistency': 'SC'}
PARES = (('few_shot', 'chain_of_thought'), ('chain_of_thought', 'self_consistency'),
         ('few_shot', 'self_consistency'))


def _momento(caminho):
    m = re.search(r'(\d{8})_(\d{6})', Path(caminho).name)
    if m:
        for formato in ('%d%m%Y%H%M%S', '%Y%m%d%H%M%S'):
            try:
                return datetime.strptime(m.group(1) + m.group(2), formato)
            except ValueError:
                pass
    return datetime.fromtimestamp(Path(caminho).stat().st_mtime)


def _ler(arquivo):
    dados = json.loads(Path(arquivo).read_text(encoding='utf-8'))
    if not isinstance(dados, dict) or not isinstance(dados.get('resultados'), list):
        raise ValueError(f'JSON de execução inválido: {arquivo}')
    return dados


def sem_substituidas(arquivos):
    """Tira da lista a execução original quando existe a sua recuperação (_recuperacao).

    A recuperação refaz só as falhas técnicas e guarda o resto, então ela substitui a original."""
    substituidas = set()
    for arquivo in arquivos:
        try:
            origem = _ler(arquivo).get('recuperacao_de')
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if origem:
            substituidas.add(re.split(r'[\\/]', str(origem))[-1])
    return [a for a in arquivos if Path(a).name not in substituidas]


def escolher_execucoes(dataset, limite='qualquer', exemplos=None, pasta=None):
    pasta = Path(pasta) if pasta else RAIZ / 'resultados'
    escolhidas, avisos = {}, []
    for tecnica in TECNICAS:
        base = pasta / tecnica / dataset
        candidatas = []
        if base.exists():
            for arquivo in base.rglob('*.json'):
                if arquivo.name.endswith(('.progresso.json', '.auditado.json', '.revisoes.json', '.final.json')):
                    continue
                try:
                    d = _ler(arquivo)
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
                p = d.get('parametros') or {}
                if d.get('status') not in ('concluido', 'concluido_com_falhas') or d.get('dataset') != dataset or d.get('tecnica') != tecnica:
                    continue
                if limite != 'qualquer' and p.get('limite') != limite:
                    continue
                if exemplos is not None and p.get('quantidade_exemplos') != exemplos:
                    continue
                candidatas.append(arquivo)
        antes = len(candidatas)
        candidatas = sem_substituidas(candidatas)
        if antes != len(candidatas):
            avisos.append(f'{ROTULO[tecnica]}: {antes - len(candidatas)} execução(ões) original(is) '
                          'ignorada(s) porque existe uma recuperação de falhas técnicas.')
        if candidatas:
            escolhidas[tecnica] = max(candidatas, key=lambda a: (_momento(a), a.stat().st_mtime))
            if len(candidatas) > 1:
                avisos.append(f'{ROTULO[tecnica]}: {len(candidatas)} candidatas; selecionada a mais recente. '
                              'Verifique se pertence à condição experimental pretendida.')
        else:
            avisos.append(f'{ROTULO[tecnica]}: nenhuma execução concluída encontrada.')
    return escolhidas, avisos


def carregar_execucao(arquivo, revisor=None):
    dados = _ler(arquivo)
    questoes = dados['resultados']
    ids = [str(q['id']) for q in questoes]
    if len(ids) != len(set(ids)):
        raise ValueError(f'IDs duplicados em {arquivo}')
    # Padronizar IDs ANTES de associar os vereditos e comparar execuções.
    # Guardar o original apenas para rastreabilidade.
    for q in questoes:
        q['id_original'] = q['id']
        q['id'] = str(q['id'])
    if dados.get('dataset') == 'censo' and revisor:
        revisoes = carregar_revisoes(arquivo)
        # Compatibilidade com revisões antigas que guardam IDs numéricos.
        for revisao in revisoes:
            if isinstance(revisao, dict) and 'id' in revisao:
                revisao['id'] = str(revisao['id'])
        decisoes = acertos_finais(questoes, revisoes, revisor)
        veredito = {str(k): v for k, v in decisoes.items()}
    else:
        veredito = {q['id']: q.get('acertou') if isinstance(q.get('acertou'), bool) else None
                    for q in questoes}
    # Uma falha técnica nunca deve ser contabilizada como acerto ou erro de conteúdo.
    for q in questoes:
        if q.get('falha_tecnica'):
            veredito[q['id']] = None
    return {'arquivo': Path(arquivo), 'dados': dados, 'questoes': questoes,
            'tecnica': dados['tecnica'], 'dataset': dados['dataset'], 'veredito': veredito}


def _falha(q):
    if q.get('falha_tecnica'):
        return True
    return str(q.get('motivo') or '').lower().startswith('falha na consulta ao modelo')


def resumo_acuracia(e):
    qs = [q for q in e['questoes'] if not q.get('usada_como_exemplo')]
    validas = [q for q in qs if not _falha(q)]
    acertos = sum(e['veredito'].get(q['id']) is True for q in validas)
    pendentes = sum(e['veredito'].get(q['id']) is None for q in validas)
    n = len(validas)
    resultado = {'questoes': len(qs), 'avaliadas': n, 'falhas_tecnicas': len(qs) - n,
                 'pendentes': pendentes, 'acertos': acertos,
                 'acuracia': None, 'ic95': None,
                 'minimo': acertos / n if n else None,
                 'maximo': (acertos + pendentes) / n if n else None,
                 'acertos_por_questao_planejada': acertos / len(qs) if qs else None}
    if n and not pendentes:
        resultado['acuracia'] = acertos / n
        resultado['ic95'] = intervalo_wilson(acertos, n)
    return resultado


def comparar_pareado(a, b):
    qa = {q['id'] for q in a['questoes'] if not _falha(q) and not q.get('usada_como_exemplo')}
    qb = {q['id'] for q in b['questoes'] if not _falha(q) and not q.get('usada_como_exemplo')}
    pares = [(a['veredito'].get(i), b['veredito'].get(i)) for i in sorted(qa & qb)]
    pares = [(x, y) for x, y in pares if isinstance(x, bool) and isinstance(y, bool)]
    n = len(pares)
    so_a = sum(x and not y for x, y in pares)
    so_b = sum(y and not x for x, y in pares)
    aa = sum(x for x, _ in pares) / n if n else None
    ab = sum(y for _, y in pares) / n if n else None
    return {'ids_pareados': [i for i in sorted(qa & qb) if isinstance(a['veredito'].get(i), bool) and isinstance(b['veredito'].get(i), bool)],
            'n_pareado': n, 'so_a': so_a, 'so_b': so_b,
            'ambos_certos': sum(x and y for x, y in pares),
            'ambos_errados': sum(not x and not y for x, y in pares),
            'acuracia_a': aa, 'acuracia_b': ab,
            'diferenca_pp': 100 * (ab - aa) if n else None,
            'p_mcnemar': mcnemar_exato(so_a, so_b) if n else None,
            'questoes_fora_do_par': len(qa ^ qb),
            'questoes_sem_veredito_em_ambas': len(qa & qb) - n}


def _media_presente(qs, campo):
    valores = []
    for q in qs:
        valor = q.get(campo)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor):
            valores.append(float(valor))
    return sum(valores) / len(valores) if valores else None, len(valores)


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _tokens_completos(q, n_previsto=None):
    """A questão só entra na média de tokens se entrada e saída existem e, quando há gerações
    (Self-Consistency), todas as n previstas foram registradas com seus tokens."""
    if not (_numero(q.get('tokens_entrada')) and _numero(q.get('tokens_saida'))):
        return False
    amostras = q.get('amostras')
    if n_previsto and not amostras:
        return False                      # SC sem as gerações salvas: o total não é comprovável
    if amostras:
        if n_previsto and len(amostras) != n_previsto:
            return False
        if not all(_numero(a.get('tokens_entrada')) and _numero(a.get('tokens_saida')) for a in amostras):
            return False
        # o total da questão tem de ser a soma das gerações
        return (sum(a['tokens_entrada'] for a in amostras) == q['tokens_entrada']
                and sum(a['tokens_saida'] for a in amostras) == q['tokens_saida'])
    return True


def custo(e):
    qs = [q for q in e['questoes'] if not q.get('usada_como_exemplo')]
    resultado = {'questoes': len(qs)}
    for campo, nome in [('tempo_segundos', 'tempo_medio_s'),
                        ('tokens_entrada', 'tokens_entrada_medio'),
                        ('tokens_saida', 'tokens_saida_medio')]:
        media, n = _media_presente(qs, campo)
        resultado[nome] = media
        resultado[nome + '_n'] = n
    # Tokens: entrada e saída são medidas SOBRE AS MESMAS questões. Só entra a questão com os dois valores
    # e, na Self-Consistency, com todas as gerações previstas registradas (soma das n amostras).
    n_prev = (e['dados'].get('parametros') or {}).get('n_amostras')
    validas = [q for q in qs if _tokens_completos(q, n_prev)]
    ent = [float(q['tokens_entrada']) for q in validas]
    sai = [float(q['tokens_saida']) for q in validas]
    resultado['tokens_entrada_medio'] = sum(ent) / len(ent) if ent else None
    resultado['tokens_saida_medio'] = sum(sai) / len(sai) if sai else None
    resultado['tokens_total_medio'] = (sum(ent) + sum(sai)) / len(ent) if ent else None
    resultado['tokens_entrada_medio_n'] = resultado['tokens_saida_medio_n'] = len(validas)
    resultado['tempo_total_registrado_s'] = sum(q['tempo_segundos'] for q in qs
        if isinstance(q.get('tempo_segundos'), (int, float)) and not isinstance(q.get('tempo_segundos'), bool))
    return resultado


def falhas(e):
    qs = [q for q in e['questoes'] if not q.get('usada_como_exemplo')]
    n = len(qs)
    amostras = [a for q in qs for a in (q.get('amostras') or [])]
    return {'questoes': n,
            'falhas_tecnicas': sum(_falha(q) for q in qs),
            'respostas_vazias': sum(not str(q.get('resposta') or '').strip() for q in qs),
            'limite_tokens': sum(bool(q.get('amostras_limite_tokens') or q.get('limite_tokens_atingido')) for q in qs),
            'amostras_sem_extracao': sum(not str(a.get('resposta_extraida') or '').strip() for a in amostras),
            'total_amostras': len(amostras)}


def motivos_nao_comparavel(execucoes):
    """Motivos que tornam a comparação inadequada (lista vazia = comparável)."""
    motivos = []
    if len(execucoes) < 3:
        motivos.append('faltam técnicas: ' + ', '.join(ROTULO[t] for t in TECNICAS if t not in execucoes))
    ids = {t: {q['id'] for q in e['questoes'] if not q.get('usada_como_exemplo')} for t, e in execucoes.items()}
    if len({frozenset(x) for x in ids.values()}) > 1:
        motivos.append('questões diferentes: ' + ', '.join(f'{ROTULO[t]}={len(v)}' for t, v in ids.items()))
    par = {t: e['dados'].get('parametros') or {} for t, e in execucoes.items()}
    for campo in ('modelo', 'quantidade_exemplos', 'ids_exemplos', 'maximo_tokens_resposta',
                  'num_ctx', 'top_k', 'top_p'):
        if len({json.dumps(p.get(campo), sort_keys=True) for p in par.values()}) > 1:
            motivos.append(f'parâmetro "{campo}" difere')
    # Ausência de metadados não demonstra igualdade de condições.
    for campo in ('modelo', 'quantidade_exemplos'):
        if any(p.get(campo) is None for p in par.values()):
            motivos.append(f'parâmetro obrigatório \"{campo}\" ausente')
    if len(execucoes) > 1 and any(p.get('ids_exemplos') is None for p in par.values()):
        motivos.append('identidade dos exemplos não documentada (ids_exemplos ausente)')
    return motivos


def avisos_de_comparabilidade(execucoes):
    avisos = []
    if len(execucoes) < 3:
        avisos.append('Comparação incompleta: nem todas as três técnicas foram encontradas.')
    ids = {t: {q['id'] for q in e['questoes'] if not q.get('usada_como_exemplo')}
           for t, e in execucoes.items()}
    if len({frozenset(x) for x in ids.values()}) > 1:
        avisos.append('As técnicas não usaram exatamente as mesmas questões. Comparações pareadas usam a interseção.')
    parametros = {t: e['dados'].get('parametros') or {} for t, e in execucoes.items()}
    for campo in ('modelo', 'quantidade_exemplos', 'ids_exemplos', 'maximo_tokens_resposta',
                  'num_ctx', 'top_k', 'top_p', 'temperatura', 'n_amostras'):
        valores = {json.dumps(p.get(campo), sort_keys=True, ensure_ascii=False) for p in parametros.values()}
        if len(valores) > 1:
            avisos.append(f'Parâmetro diferente: {campo} — ' + '; '.join(
                f'{ROTULO[t]}={p.get(campo)}' for t, p in parametros.items()))
    avisos.append('Tempo é comparável apenas com hardware e carga de máquina equivalentes; '
                  'diferenças de temperatura podem confundir o efeito da técnica.')
    return avisos


def gerar(dataset, limite='qualquer', exemplos=None, revisor=None, pasta=None, arquivos=None,
          estrito=False):
    """estrito=True: sem comparação pareada quando as execuções não são comparáveis."""
    if arquivos:
        selecionados = {t: Path(p) for t, p in arquivos.items() if p}
        avisos = []
    else:
        selecionados, avisos = escolher_execucoes(dataset, limite, exemplos, pasta)
    execucoes = {t: carregar_execucao(p, revisor) for t, p in selecionados.items()}
    for t, e in execucoes.items():
        if e['dataset'] != dataset or e['tecnica'] != t:
            raise ValueError(f'Execução incompatível: {e["arquivo"]}')
        if e['dados'].get('status') not in ('concluido', 'concluido_com_falhas'):
            raise ValueError(f'Execução ainda não concluída: {e["arquivo"]}')
    avisos.extend(avisos_de_comparabilidade(execucoes))
    rel = {'dataset': dataset, 'execucoes': {t: str(e['arquivo']) for t, e in execucoes.items()},
           'parametros': {t: e['dados'].get('parametros', {}) for t, e in execucoes.items()},
           'comparavel': not motivos_nao_comparavel(execucoes),
           'motivos_nao_comparavel': motivos_nao_comparavel(execucoes), 'estrito': estrito,
           'avisos': avisos, 'acuracia': {}, 'comparacoes': {}, 'custo': {}, 'falhas': {},
           'self_consistency_amostras': None, 'custo_beneficio': {}}
    for t, e in execucoes.items():
        rel['acuracia'][t] = resumo_acuracia(e)
        rel['custo'][t] = custo(e)
        rel['falhas'][t] = falhas(e)
    bloquear = estrito and rel['motivos_nao_comparavel']
    if bloquear:
        avisos.append('Comparação pareada NÃO feita (modo estrito): ' + '; '.join(rel['motivos_nao_comparavel']))
    for a, b in ([] if bloquear else PARES):
        if a in execucoes and b in execucoes:
            rel['comparacoes'][f'{a}__vs__{b}'] = comparar_pareado(execucoes[a], execucoes[b])
    if 'self_consistency' in execucoes:
        rel['self_consistency_amostras'] = analisar(execucoes['self_consistency'])
    for base in ('few_shot', 'chain_of_thought'):
        chave = f'{base}__vs__self_consistency'
        if chave not in rel['comparacoes']:
            continue
        diferenca = rel['comparacoes'][chave]['diferenca_pp']
        ids = set(rel['comparacoes'][chave]['ids_pareados'])
        custos_pareados = {}
        for tecnica in (base, 'self_consistency'):
            qs = [q for q in execucoes[tecnica]['questoes'] if q['id'] in ids]
            custos_pareados[tecnica] = {}
            for campo in ('tempo_segundos', 'tokens_entrada', 'tokens_saida'):
                media, quantidade = _media_presente(qs, campo)
                custos_pareados[tecnica][campo] = {'media': media, 'n': quantidade}
        # Comparação de custos somente nas questões com medidas presentes em AMBAS as técnicas.
        def custo_comum(campo):
            registros = []
            qa = {q['id']: q for q in execucoes[base]['questoes']}
            qb = {q['id']: q for q in execucoes['self_consistency']['questoes']}
            for i in ids:
                x, y = qa[i].get(campo), qb[i].get(campo)
                if all(isinstance(v, (int, float)) and not isinstance(v, bool)
                       and math.isfinite(v) and v >= 0 for v in (x, y)):
                    registros.append((float(x), float(y)))
            if not registros:
                return None, None, 0
            return (sum(x for x, _ in registros) / len(registros),
                    sum(y for _, y in registros) / len(registros), len(registros))
        tb, ts, n_tempo = custo_comum('tempo_segundos')
        entrada_b, entrada_s, n_entrada = custo_comum('tokens_entrada')
        saida_b, saida_s, n_saida = custo_comum('tokens_saida')
        adicional = ts - tb if tb is not None else None
        qa = {q['id']: q for q in execucoes[base]['questoes']}
        qb = {q['id']: q for q in execucoes['self_consistency']['questoes']}
        pares_tokens = []
        for identificador in ids:
            x, y = qa[identificador], qb[identificador]
            valores = [x.get('tokens_entrada'), x.get('tokens_saida'),
                       y.get('tokens_entrada'), y.get('tokens_saida')]
            if all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   and math.isfinite(v) and v >= 0 for v in valores):
                pares_tokens.append((valores[0] + valores[1], valores[2] + valores[3]))
        tokens_adicionais = (sum(y - x for x, y in pares_tokens) / len(pares_tokens)
                             if pares_tokens else None)
        rel['custo_beneficio'][chave] = {
            'ganho_pp_pareado': diferenca, 'tempo_adicional_s': adicional,
            'n_tempo_pareado': n_tempo, 'n_tokens_entrada_pareado': n_entrada,
            'n_tokens_saida_pareado': n_saida, 'n_tokens_totais_pareados': len(pares_tokens),
            'tokens_adicionais_medios': tokens_adicionais,
            'ganho_pp_por_1000_tokens_adicionais': (1000 * diferenca / tokens_adicionais
                if diferenca is not None and tokens_adicionais is not None and tokens_adicionais > 0 else None),
            'ganho_pp_por_segundo_adicional': (diferenca / adicional if diferenca is not None
                and adicional is not None and adicional > 0 else None),
            'multiplicador_tempo': ts / tb if tb and ts is not None else None}
    return rel


def _pct(valor):
    return '—' if valor is None else f'{100 * valor:.2f}%'


def _num(valor, casas=2):
    return '—' if valor is None else f'{valor:.{casas}f}'


def _tabela(cabecalho, linhas):
    return '\n'.join(['| ' + ' | '.join(cabecalho) + ' |',
                      '| ' + ' | '.join('---' for _ in cabecalho) + ' |'] +
                     ['| ' + ' | '.join(map(str, linha)) + ' |' for linha in linhas])


def para_markdown(rel):
    out = [f'# Avaliação experimental — {rel["dataset"]}', '', '## Arquivos analisados', '']
    out.extend(f'- {ROTULO[t]}: `{p}`' for t, p in rel['execucoes'].items())
    if not rel.get('comparavel', True):
        out += ['', '**ATENÇÃO — execuções NÃO comparáveis:** ' + '; '.join(rel['motivos_nao_comparavel'])]
    out += ['', '## Avisos de comparabilidade', '']
    out.extend(f'- {a}' for a in rel['avisos'])
    out += ['', '## Acurácia', '']
    out.append(_tabela(('Técnica', 'Planejadas', 'N sem falha', 'Acertos', 'Pendentes', 'Acurácia',
                        'IC Wilson 95%', 'Acertos / planejadas', 'Falhas técnicas'), [
        (ROTULO[t], r['questoes'], r['avaliadas'], r['acertos'], r['pendentes'],
         _pct(r['acuracia']) if r['acuracia'] is not None
         else f'faixa {_pct(r["minimo"])} a {_pct(r["maximo"])}',
         f'{_pct(r["ic95"][0])} a {_pct(r["ic95"][1])}' if r['ic95'] else 'não se aplica',
         _pct(r['acertos_por_questao_planejada']), r['falhas_tecnicas'])
        for t, r in rel['acuracia'].items()]))
    out.append('\n"Faixa" = mínimo e máximo enquanto há revisão humana pendente; NÃO é intervalo de '
               'confiança. "Acertos / planejadas" conta falha técnica e pendência como não acerto.')
    out += ['', '## Comparações pareadas — McNemar exato', '']
    out.append(_tabela(('Par', 'N comum', 'Diferença (pp)', 'Só A', 'Só B', 'p bicaudal'), [
        (f'{ROTULO[a]} × {ROTULO[b]}', r['n_pareado'], _num(r['diferenca_pp']),
         r['so_a'], r['so_b'], _num(r['p_mcnemar'], 5))
        for chave, r in rel['comparacoes'].items() for a, b in [chave.split('__vs__')]]))
    out += ['', '## Custo computacional', '']
    out.append(_tabela(('Técnica', 'Tempo médio (s)', 'N tempo', 'Tokens entrada', 'Tokens saída'), [
        (ROTULO[t], _num(r['tempo_medio_s']), r['tempo_medio_s_n'],
         _num(r['tokens_entrada_medio']), _num(r['tokens_saida_medio']))
        for t, r in rel['custo'].items()]))
    out += ['', '## Custo-benefício (ganho pareado)', '']
    out.append(_tabela(('Comparação', 'Ganho (pp)', 'Tempo adicional (s)', 'N tempo pareado', 'Multiplicador tempo', 'pp/s adicional', 'Tokens adicionais', 'pp/1000 tokens'), [
        (chave.replace('__vs__', ' → '), _num(r['ganho_pp_pareado']),
         _num(r['tempo_adicional_s']), r.get('n_tempo_pareado', 0),
         _num(r['multiplicador_tempo']), _num(r['ganho_pp_por_segundo_adicional'], 4),
         _num(r.get('tokens_adicionais_medios'), 0),
         _num(r.get('ganho_pp_por_1000_tokens_adicionais'), 4))
        for chave, r in rel['custo_beneficio'].items()]))
    out += ['', '## Falhas', '']
    out.append(_tabela(('Técnica', 'Falhas técnicas', 'Respostas vazias', 'Limite de tokens', 'Amostras sem extração / total'), [
        (ROTULO[t], r['falhas_tecnicas'], r['respostas_vazias'], r['limite_tokens'],
         f'{r["amostras_sem_extracao"]}/{r["total_amostras"]}') for t, r in rel['falhas'].items()]))
    sc = rel['self_consistency_amostras']
    if sc:
        out += ['', '## Self-Consistency — primeiras k amostras', '']
        if sc['disponivel']:
            if sc.get('por_k_mesmas_questoes'):
                out += ['', '### Curva principal: mesmas questões em todos os k', '']
                out.append(_tabela(('k', 'Questões', 'Acertos', 'Acurácia', 'Empates'), [
                    (r['k'], r['questoes'], r['acertos'], _pct(r['acuracia']), r['empates'])
                    for r in sc['por_k_mesmas_questoes']]))
            out += ['', '### Curva exploratória: N variável', '']
            out.append(_tabela(('k', 'Questões', 'Acertos', 'Acurácia', 'Empates'), [
                (r['k'], r['questoes'], r['acertos'], _pct(r['acuracia']), r['empates'])
                for r in sc['por_k']]))
            out.append('\n' + sc['observacao'])
            out.append(f'\nAnálise {"COMPLETA" if sc["completo"] else "PARCIAL"}: '
                       f'{sc["questoes_com_amostras"]} de {sc["questoes_planejadas"]} questões com amostras'
                       + (f'; fora: {", ".join(map(str, sc["questoes_excluidas"][:10]))}'
                          if sc['questoes_excluidas'] else '') + '.')
            out.append(f'\nAcurácia média de UMA amostra: {_pct(sc["acuracia_amostra_unica_media"])}; '
                       f'alguma amostra acerta (teto): {_pct(sc["acuracia_qualquer_amostra_certa"])}.')
        else:
            out.append(sc['motivo'])
    out += ['', 'Nota: significância estatística não implica benefício prático. '
           'Comparações com configurações diferentes exigem interpretação cautelosa.']
    return '\n'.join(out) + '\n'


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('dataset', choices=('gsm8k', 'aqua_rat', 'censo'))
    p.add_argument('--limite', default='qualquer')
    p.add_argument('--exemplos', type=int)
    p.add_argument('--revisor')
    p.add_argument('--pasta')
    p.add_argument('--saida')
    p.add_argument('--few')
    p.add_argument('--cot')
    p.add_argument('--sc')
    p.add_argument('--estrito', action='store_true',
                   help='não faz comparação pareada se as execuções não forem comparáveis')
    args = p.parse_args(argv)
    limite = args.limite if args.limite == 'qualquer' else (None if args.limite == 'todos' else int(args.limite))
    arquivos = {'few_shot': args.few, 'chain_of_thought': args.cot, 'self_consistency': args.sc}
    arquivos = {t: caminho for t, caminho in arquivos.items() if caminho}
    rel = gerar(args.dataset, limite, args.exemplos, args.revisor, args.pasta, arquivos or None,
                estrito=args.estrito)
    if not rel['execucoes']:
        print('Nenhuma execução concluída encontrada.\n' + '\n'.join(rel['avisos']))
        return 1
    destino = Path(args.saida) if args.saida else RAIZ / 'resultados' / 'metricas' / 'relatorios' / args.dataset
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f'comparacao_{args.dataset}.json').write_text(
        json.dumps(rel, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    markdown = para_markdown(rel)
    (destino / f'comparacao_{args.dataset}.md').write_text(markdown, encoding='utf-8')
    print(markdown)
    print('Salvo em:', destino)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
