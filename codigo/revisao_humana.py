"""Revisão humana das respostas pendentes do Censo + estatísticas do TCC.

Uso (na raiz do projeto):
  python -m codigo.revisao_humana pendentes ARQUIVO.json
  python -m codigo.revisao_humana revisar   ARQUIVO.json --revisor layla
  python -m codigo.revisao_humana resumo    ARQUIVO.json
  python -m codigo.revisao_humana kappa     ARQUIVO.json layla prof

O arquivo de resultados NUNCA é alterado. As decisões ficam em
ARQUIVO.revisoes.json (um registro por questão e por revisor).
"""
import json
import math
import sys
from pathlib import Path


# ---------------- estatística (só biblioteca padrão) ----------------

def intervalo_wilson(acertos, total, z=1.96):
    """Intervalo de confiança de 95% para uma proporção (Wilson)."""
    if total <= 0:
        return (0.0, 0.0)
    p = acertos / total
    d = 1 + z * z / total
    centro = (p + z * z / (2 * total)) / d
    meia = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / d
    return (max(0.0, centro - meia), min(1.0, centro + meia))


def mcnemar_exato(b, c):
    """Teste de McNemar exato (bicaudal). b = só A acertou; c = só B acertou."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    cauda = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * cauda)


def comparar_pareado(acertos_a, acertos_b):
    """acertos_a/b: dicts id -> bool, sobre as MESMAS questões."""
    ids = sorted(set(acertos_a) & set(acertos_b))
    b = sum(1 for i in ids if acertos_a[i] and not acertos_b[i])
    c = sum(1 for i in ids if acertos_b[i] and not acertos_a[i])
    return {'n': len(ids), 'so_a': b, 'so_b': c, 'p_mcnemar': mcnemar_exato(b, c)}


def kappa_cohen(a, b):
    """Concordância entre dois revisores. a, b: dicts id -> bool."""
    ids = sorted(set(a) & set(b))
    n = len(ids)
    if n == 0:
        return {'n': 0, 'kappa': None, 'concordancia': None}
    obs = sum(a[i] == b[i] for i in ids) / n
    pa, pb = sum(a[i] for i in ids) / n, sum(b[i] for i in ids) / n
    esp = pa * pb + (1 - pa) * (1 - pb)
    kappa = None if esp == 1 else (obs - esp) / (1 - esp)
    return {'n': n, 'kappa': kappa, 'concordancia': obs}


# ---------------- leitura e resumo ----------------

def _questoes(dados):
    return dados['resultados'] if isinstance(dados, dict) else dados


def caminho_revisoes(arquivo):
    arquivo = Path(arquivo)
    return arquivo.with_name(arquivo.stem + '.revisoes.json')


def carregar_revisoes(arquivo):
    c = caminho_revisoes(arquivo)
    return json.loads(c.read_text(encoding='utf-8')) if c.exists() else []


def pendentes(questoes):
    return [q for q in questoes if q.get('acertou') is None
            and q.get('tipo_resultado') == 'avaliacao_pendente'
            or (q.get('acertou') is None and q.get('revisao_necessaria'))]


def veredito_revisor(revisoes, revisor):
    """id -> bool, última decisão de cada questão para esse revisor."""
    saida = {}
    for r in revisoes:
        if r['revisor'] == revisor:
            saida[r['id']] = bool(r['acertou'])
    return saida


def acertos_finais(questoes, revisoes, revisor):
    """id -> bool, ou None onde ainda falta decisão."""
    humano = veredito_revisor(revisoes, revisor)
    saida = {}
    for q in questoes:
        if isinstance(q.get('acertou'), bool):
            saida[q['id']] = q['acertou']
        else:
            saida[q['id']] = humano.get(q['id'])
    return saida


def resumo(questoes, revisoes=(), revisor=None):
    certos = sum(q.get('acertou') is True for q in questoes)
    errados = sum(q.get('acertou') is False for q in questoes)
    pend = [q for q in questoes if q.get('acertou') is None]
    n = len(questoes)
    out = {'total': n, 'certos_automaticos': certos, 'errados_automaticos': errados,
           'pendentes': len(pend),
           'minimo': certos / n if n else 0.0, 'maximo': (certos + len(pend)) / n if n else 0.0}
    if revisor:
        finais = acertos_finais(questoes, revisoes, revisor)
        decididos = {i: v for i, v in finais.items() if v is not None}
        faltam = n - len(decididos)
        out['faltam_revisar'] = faltam
        if faltam == 0 and n:
            ac = sum(decididos.values())
            out['acuracia_final'] = ac / n
            out['ic95'] = intervalo_wilson(ac, n)
    return out


# ---------------- linha de comando ----------------

def _pedir(msg, validos):
    while True:
        r = input(msg).strip().lower()
        if r in validos:
            return r
        print(f'  Digite uma destas opções: {", ".join(validos)}')


def revisar(arquivo, revisor):
    dados = json.loads(Path(arquivo).read_text(encoding='utf-8'))
    questoes = _questoes(dados)
    revisoes = carregar_revisoes(arquivo)
    ja = veredito_revisor(revisoes, revisor)
    fila = [q for q in pendentes(questoes) if q['id'] not in ja]
    print(f'{len(fila)} questão(ões) para revisar. Digite "s" para sair a qualquer momento.')
    for q in fila:
        print('\n' + '=' * 70)
        print('QUESTÃO:', q['id'])
        print('\nGABARITO:\n', q.get('gabarito'))
        print('\nRESPOSTA DO MODELO:\n', q.get('resposta'))
        print('\nPARECER DO JUIZ (só triagem, não decide):', q.get('parecer_llm'), '-', q.get('motivo'))
        r = _pedir('\nA resposta está correta? [c]orreta / [e]rrada / [s]air: ', ('c', 'e', 's'))
        if r == 's':
            break
        criterio = input('Critério usado (1 linha, ex.: "tem os dois totais e a conclusão"): ').strip()
        revisoes.append({'id': q['id'], 'revisor': revisor, 'acertou': r == 'c', 'criterio': criterio})
        caminho_revisoes(arquivo).write_text(json.dumps(revisoes, ensure_ascii=False, indent=2),
                                              encoding='utf-8')
    print('\nSalvo em', caminho_revisoes(arquivo))


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 2:
        print(__doc__)
        return 1
    cmd, arquivo = a[0], a[1]
    dados = json.loads(Path(arquivo).read_text(encoding='utf-8'))
    questoes = _questoes(dados)
    revisoes = carregar_revisoes(arquivo)
    if cmd == 'pendentes':
        for q in pendentes(questoes):
            print(q['id'], '| juiz:', q.get('parecer_llm'))
    elif cmd == 'revisar':
        revisor = a[a.index('--revisor') + 1] if '--revisor' in a else 'revisor1'
        revisar(arquivo, revisor)
    elif cmd == 'resumo':
        revisor = a[a.index('--revisor') + 1] if '--revisor' in a else None
        print(json.dumps(resumo(questoes, revisoes, revisor), ensure_ascii=False, indent=2))
    elif cmd == 'kappa':
        r1, r2 = a[2], a[3]
        print(json.dumps(kappa_cohen(veredito_revisor(revisoes, r1), veredito_revisor(revisoes, r2)),
                         indent=2))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
