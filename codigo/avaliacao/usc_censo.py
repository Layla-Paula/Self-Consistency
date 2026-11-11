"""Teste EXPLORATÓRIO de juiz de consenso (estilo Universal Self-Consistency, Chen et al., 2023).

Não faz parte do método principal do trabalho. Aplica, sobre as gerações JÁ SALVAS da
Self-Consistency do Censo, um juiz (o mesmo llama3.2:3b, temperatura 0) que escolhe entre as
respostas extraídas de cada questão. Nenhuma geração é refeita e nenhum arquivo existente é
alterado: o resultado vai para uma pasta nova (usc_exploratorio).

Fluxo por questão:
  1. todas as respostas equivalentes (mesma chave da votação: número normalizado ou texto canônico) -> não há o que julgar; mantém a votação;
  2. respostas diferentes -> o juiz escolhe uma (1 chamada, até 3 tentativas se a saída for ilegível);
  3. se a escolhida é equivalente à da votação -> nada muda;
  4. se muda -> a resposta escolhida é avaliada pelas mesmas rubricas do trabalho; quando a rubrica
     não decide, a questão fica PENDENTE para revisão humana (acertou=None).
A comparação com a votação usa o veredito final já revisado (.final.json), quando existir.
"""
import argparse
import json
import os
import re
import traceback
import unicodedata
from pathlib import Path

from codigo.avaliacao.avaliacao_censo import avaliar_censo
from codigo.self_consistency.votacao import _canonico, _numero_unico

SUFIXOS_DERIVADOS = ('.progresso.json', '.auditado.json', '.revisoes.json', '.final.json')
PASTA_SAIDA = 'usc_exploratorio'


def _norm(texto):
    texto = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', '', texto.lower())


def _chave(texto):
    """Mesma equivalência da votação do trabalho: número único normalizado ou texto canônico."""
    return _numero_unico(texto) or 'texto:' + _canonico(texto)


def montar_prompt(pergunta, respostas):
    """Prompt de seleção por consenso, sem gabarito."""
    blocos = '\n\n'.join(f'Resposta {i}: {r}' for i, r in enumerate(respostas, 1))
    return (f'Gerei as respostas abaixo para a pergunta a seguir.\n\nPergunta: {pergunta}\n\n{blocos}\n\n'
            'Escolha a resposta mais consistente, isto é, a que concorda com a maioria das demais. '
            f'Responda apenas no formato: "A resposta mais consistente é a Resposta X", com X de 1 a {len(respostas)}.')


def ler_escolha(texto, n):
    """Número da resposta escolhida (1..n) ou None."""
    achados = re.findall(r'(?i)resposta\s*(\d+)', str(texto or ''))
    if not achados:
        achados = re.findall(r'\b(\d+)\b', str(texto or ''))
    if achados and 1 <= int(achados[-1]) <= n:
        return int(achados[-1])
    return None


def escolher(pergunta, respostas, consultar_modelo):
    """Chama o juiz até 3 vezes; retorna (índice 0-based ou None, saída bruta, tentativas)."""
    prompt = montar_prompt(pergunta, respostas)
    bruta = ''
    for tentativa in range(1, 4):
        info = consultar_modelo(prompt, temperature=0, num_predict=60, retornar_metricas=True)
        bruta = (info or {}).get('resposta') if isinstance(info, dict) else info
        escolha = ler_escolha(bruta, len(respostas))
        if escolha:
            return escolha - 1, bruta, tentativa
    return None, bruta, 3


def listar(pasta):
    """SC do Censo concluídas (usa o original; o .final.json só fornece o veredito revisado)."""
    achadas = []
    for arq in sorted(Path(pasta).rglob('*.json')):
        if arq.name.endswith(SUFIXOS_DERIVADOS) or arq.stem.endswith('_recuperacao'):
            continue
        try:
            d = json.loads(arq.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if (isinstance(d, dict) and d.get('dataset') == 'censo' and d.get('tecnica') == 'self_consistency'
                and d.get('status') in ('concluido', 'concluido_com_falhas')
                and isinstance(d.get('resultados'), list)):
            achadas.append(arq)
    return achadas


def _veredito_votacao(arquivo, dados):
    """{id: True/False/None} da votação, preferindo o .final.json (revisado)."""
    final = arquivo.with_name(arquivo.stem + '.final.json')
    if final.exists():
        f = json.loads(final.read_text(encoding='utf-8'))
        return {str(q['id']): q.get('veredito_final') for q in f.get('resultados', [])}, True
    return {str(q['id']): q.get('acertou') for q in dados['resultados']}, False


def aplicar(arquivo, enunciados, consultar_modelo):
    arquivo = Path(arquivo)
    dados = json.loads(arquivo.read_text(encoding='utf-8'))
    votacao, revisado = _veredito_votacao(arquivo, dados)
    linhas = []
    for q in dados['resultados']:
        if q.get('usada_como_exemplo') or q.get('falha_tecnica'):
            continue
        qid = str(q['id'])
        base = enunciados[qid]
        respostas = [r for r in (q.get('respostas_extraidas') or []) if str(r).strip()]
        linha = {'id': qid, 'n_respostas': len(respostas), 'votacao_acertou': votacao.get(qid),
                 'resposta_votacao': q.get('resposta'), 'juiz_chamado': False, 'mudou': False, 'todas_diferentes': False,
                 'usc_acertou': votacao.get(qid), 'pendente_revisao': False}
        chaves = [_chave(r) for r in respostas]
        linha['todas_diferentes'] = len(respostas) >= 2 and len(set(chaves)) == len(chaves)
        if len(respostas) >= 2 and len(set(chaves)) > 1:
            pergunta = base.get('pergunta') or base.get('enunciado')
            i, bruta, tentativas = escolher(pergunta, respostas, consultar_modelo)
            linha.update(juiz_chamado=True, saida_juiz=bruta, tentativas_juiz=tentativas)
            if i is None:
                linha['observacao'] = 'juiz sem escolha válida; mantida a votação'
            else:
                linha['resposta_juiz'] = respostas[i]
                if _chave(respostas[i]) != _chave(q.get('resposta')):
                    # a rubrica dispensa o juiz da correção; sem rubrica, fica para revisão humana
                    av = avaliar_censo(base, respostas[i], None)
                    linha.update(mudou=True, usc_acertou=av['acertou'],
                                 pendente_revisao=av['acertou'] is None,
                                 criterio_usc=av.get('motivo'), metodo_usc=av.get('metodo_avaliacao'))
        linhas.append(linha)
    return {'arquivo': str(arquivo), 'revisado_humano': revisado, 'linhas': linhas,
            'parametros': dados.get('parametros', {}), 'resumo': resumir(linhas)}


def resumir(linhas):
    n = len(linhas)
    pend = sum(l['pendente_revisao'] for l in linhas)
    acertos_v = sum(l['votacao_acertou'] is True for l in linhas)
    acertos_u = sum(l['usc_acertou'] is True for l in linhas)
    return {'questoes': n, 'todas_diferentes': sum(l['todas_diferentes'] for l in linhas),
            'juiz_chamado': sum(l['juiz_chamado'] for l in linhas),
            'mudaram': sum(l['mudou'] for l in linhas), 'pendentes': pend,
            'acertos_votacao': acertos_v, 'acertos_usc': acertos_u,
            'acuracia_votacao': round(100 * acertos_v / n, 1) if n else None,
            'acuracia_usc': round(100 * acertos_u / n, 1) if n and not pend else None}


def relatorio_md(res):
    r = res['resumo']
    p = res['parametros']
    t = [f"# Teste exploratório: juiz de consenso na SC do Censo\n",
         f"Arquivo: `{Path(res['arquivo']).name}` · temperatura {p.get('temperatura')}, "
         f"{p.get('n_amostras')} amostras, {p.get('maximo_tokens_resposta')} tokens\n",
         f"- Questões: {r['questoes']}; sem nenhuma resposta repetida (votação cai na 1ª geração): {r['todas_diferentes']}; juiz chamado em {r['juiz_chamado']} (respostas divergentes)",
         f"- Escolha do juiz diferente da votação em {r['mudaram']}; pendentes de revisão: {r['pendentes']}",
         f"- Acertos: votação {r['acertos_votacao']} ({r['acuracia_votacao']}%), "
         f"juiz {r['acertos_usc']} ({r['acuracia_usc'] if r['acuracia_usc'] is not None else 'após revisar pendentes'}%)\n",
         '| Questão | Votação | Juiz | Votação acertou | Juiz acertou |', '|---|---|---|---|---|']
    for l in res['linhas']:
        if l['mudou']:
            sim = {True: 'sim', False: 'não', None: 'PENDENTE'}
            t.append(f"| {l['id']} | {str(l['resposta_votacao'])[:50]} | {str(l.get('resposta_juiz'))[:50]} | "
                     f"{sim[l['votacao_acertou']]} | {sim[l['usc_acertou']]} |")
    t.append('\nExploratório: só altera a escolha entre respostas já geradas; não substitui a votação do método.')
    return '\n'.join(t) + '\n'


def principal():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('pasta', nargs='?', default='resultados')
    ap.add_argument('--saida', default=None, help=f'padrão: PASTA/{PASTA_SAIDA}')
    ap.add_argument('--refazer', action='store_true', help='repete execuções que já têm saída')
    ap.add_argument('--simular', action='store_true', help='só lista, sem chamar o modelo')
    args = ap.parse_args()
    arquivos = listar(args.pasta)
    print(f'{len(arquivos)} execução(ões) de SC do Censo encontradas.')
    for a in arquivos:
        print('  -', a.name)
    if args.simular or not arquivos:
        return
    from codigo.utils import carregar_censo, consultar_ollama
    enunciados = {str(q['id']): q for q in carregar_censo()}
    saida = Path(args.saida or Path(args.pasta) / PASTA_SAIDA)
    saida.mkdir(parents=True, exist_ok=True)
    feitas, puladas, erros = 0, 0, []
    for n, a in enumerate(arquivos, 1):
        base = saida / a.stem
        if Path(str(base) + '.json').exists() and not args.refazer:
            puladas += 1
            print(f'[{n}/{len(arquivos)}] {a.name}: já feita, pulada (use --refazer para repetir)')
            continue
        try:
            res = aplicar(a, enunciados, consultar_ollama)
        except Exception as erro:
            erros.append(a.name)
            print(f'[{n}/{len(arquivos)}] {a.name}: ERRO {type(erro).__name__}: {erro}')
            traceback.print_exc()
            continue
        tmp = Path(str(base) + '.json.tmp')
        tmp.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, str(base) + '.json')
        Path(str(base) + '.md').write_text(relatorio_md(res), encoding='utf-8')
        feitas += 1
        print(f"[{n}/{len(arquivos)}] {a.name}: {res['resumo']}")
    print(f'\nResumo: {feitas} feita(s), {puladas} já feita(s), {len(erros)} com erro, '
          f'{len(arquivos) - feitas - puladas - len(erros)} restante(s).')
    for nome in erros:
        print('  erro em', nome)
    print(f'\nSaída em {saida}. Revise as questões PENDENTE nos .md antes de citar números.')


if __name__ == '__main__':
    principal()