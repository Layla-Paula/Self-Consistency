"""Revisão humana das respostas pendentes do Censo + estatísticas do TCC.

Uso (na raiz do projeto):
  python -m codigo.revisao_humana pendentes ARQUIVO.json
  python -m codigo.revisao_humana revisar   ARQUIVO.json --revisor layla
  python -m codigo.revisao_humana resumo    ARQUIVO.json
  python -m codigo.revisao_humana kappa     ARQUIVO.json layla prof
  python -m codigo.revisao_humana exportar  ARQUIVO.json --revisor layla
  python -m codigo.revisao_humana revisar-pasta PASTA --revisor layla
  python -m codigo.revisao_humana exportar-pasta PASTA --revisor layla
  Opcional: --questoes dados/censo_escolar/final/censo_escolar_2025.json

O arquivo de resultados NUNCA é alterado. As decisões ficam em
ARQUIVO.revisoes.json (um registro por questão e por revisor).
"""
import hashlib
import json
import math
import re
import sys
from datetime import datetime
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


def carregar_enunciados(caminho="dados/censo_escolar/final/censo_escolar_2025.json"):
    """Lê as perguntas originais sem modificar o dataset nem os resultados."""
    origem = Path(caminho)
    if not origem.exists():
        print(f'AVISO: dataset de perguntas não encontrado: {origem}')
        return {}
    dados = json.loads(origem.read_text(encoding='utf-8'))
    enunciados = {}

    def percorrer(objeto):
        if isinstance(objeto, list):
            for item in objeto:
                percorrer(item)
        elif isinstance(objeto, dict):
            identificador = objeto.get('id') or objeto.get('id_questao')
            pergunta = (objeto.get('pergunta') or objeto.get('enunciado')
                        or objeto.get('questao'))
            if identificador is not None and isinstance(pergunta, str) and pergunta.strip():
                enunciados[str(identificador)] = pergunta.strip()
            for valor in objeto.values():
                if isinstance(valor, (list, dict)):
                    percorrer(valor)

    percorrer(dados)
    return enunciados


def parecer_do_juiz(q):
    """Veredito do juiz (CORRETA/INCORRETA). Nas execuções antigas o campo parecer_llm
    não foi gravado, mas o veredito está no começo do texto de 'motivo'."""
    if q.get('parecer_llm'):
        return q['parecer_llm']
    achado = re.search(r'Parecer do juiz: (CORRETA|INCORRETA)', str(q.get('motivo') or ''))
    return achado.group(1) if achado else None


def pergunta_da_questao(q, enunciados):
    return str(q.get('pergunta') or q.get('enunciado') or enunciados.get(str(q.get('id'))) or '').strip()


def caminho_final(arquivo):
    arquivo = Path(arquivo)
    return arquivo.with_name(arquivo.stem + '.final.json')


def montar_resultado_final(arquivo, revisor, enunciados=None):
    """Junta o JSON original (rubricas) com as decisões humanas do revisor.
    Não altera nenhum arquivo; devolve o dicionário do resultado final."""
    arquivo = Path(arquivo)
    bruto = arquivo.read_bytes()
    dados = json.loads(bruto.decode('utf-8'))
    questoes = _questoes(dados)
    revisoes = carregar_revisoes(arquivo)
    enunciados = enunciados if enunciados is not None else carregar_enunciados()
    ultima = {}
    for r in revisoes:
        if r.get('revisor') == revisor:
            ultima[r['id']] = r
    linhas = []
    for q in questoes:
        if q.get('falha_tecnica'):
            final, origem, criterio = None, 'falha_tecnica', q.get('motivo_falha_tecnica')
        elif isinstance(q.get('acertou'), bool):
            final, origem, criterio = q['acertou'], q.get('metodo_avaliacao') or 'automatico', q.get('motivo')
        elif q['id'] in ultima:
            final, origem = bool(ultima[q['id']]['acertou']), 'revisao_humana'
            criterio = ultima[q['id']].get('criterio')
        else:
            final, origem, criterio = None, 'pendente', q.get('motivo')
        linhas.append({'id': q['id'], 'pergunta': pergunta_da_questao(q, enunciados),
                       'gabarito': q.get('gabarito'), 'resposta': q.get('resposta'),
                       'veredito_final': final, 'origem_veredito': origem, 'criterio': criterio,
                       'parecer_llm': parecer_do_juiz(q), 'falha_tecnica': bool(q.get('falha_tecnica'))})
    validas = [x for x in linhas if not x['falha_tecnica']]
    acertos = sum(x['veredito_final'] is True for x in validas)
    pend = sum(x['veredito_final'] is None for x in validas)
    resumo_final = {'total_questoes': len(linhas), 'falhas_tecnicas': len(linhas) - len(validas),
                    'avaliadas': len(validas), 'acertos': acertos,
                    'erros': sum(x['veredito_final'] is False for x in validas), 'pendentes': pend,
                    'completo': pend == 0,
                    'acuracia': acertos / len(validas) if validas and pend == 0 else None,
                    'ic95_wilson': intervalo_wilson(acertos, len(validas)) if validas and pend == 0 else None,
                    'acertos_sobre_planejadas': acertos / len(linhas) if linhas else None}
    cabecalho = dados if isinstance(dados, dict) else {}
    return {'tipo': 'resultado_final_censo', 'arquivo_origem': arquivo.name,
            'sha256_origem': hashlib.sha256(bruto).hexdigest(),
            'arquivo_revisoes': caminho_revisoes(arquivo).name, 'revisor': revisor,
            'gerado_em': datetime.now().isoformat(timespec='seconds'),
            'tecnica': cabecalho.get('tecnica'), 'dataset': cabecalho.get('dataset'),
            'parametros': cabecalho.get('parametros'), 'resumo': resumo_final, 'resultados': linhas}


def exportar(arquivo, revisor, saida=None, arquivo_questoes="dados/censo_escolar/final/censo_escolar_2025.json"):
    final = montar_resultado_final(arquivo, revisor, carregar_enunciados(arquivo_questoes))
    destino = Path(saida) if saida else caminho_final(arquivo)
    if destino.resolve() == Path(arquivo).resolve():
        raise ValueError('O arquivo final não pode sobrescrever o original.')
    destino.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding='utf-8')
    return destino, final


def contar_pendentes_arquivo(arquivo, revisor):
    """Retorna o total de questões que precisam de revisão e quantas já foram revisadas."""
    dados = json.loads(Path(arquivo).read_text(encoding='utf-8'))
    fila_total = pendentes(_questoes(dados))
    ja = veredito_revisor(carregar_revisoes(arquivo), revisor)
    feitas = sum(q['id'] in ja for q in fila_total)
    return len(fila_total), feitas


def revisar(arquivo, revisor, arquivo_questoes="dados/censo_escolar/final/censo_escolar_2025.json",
            progresso_pasta=None):
    dados = json.loads(Path(arquivo).read_text(encoding='utf-8'))
    questoes = _questoes(dados)
    revisoes = carregar_revisoes(arquivo)
    ja = veredito_revisor(revisoes, revisor)
    enunciados = carregar_enunciados(arquivo_questoes)
    todas = pendentes(questoes)
    fila = [q for q in todas if q['id'] not in ja]
    total = len(todas)
    feitas = total - len(fila)
    print(f'Execução: {total} para revisar | {feitas} revisadas | {len(fila)} faltando.')
    print('Digite "s" para sair a qualquer momento.')
    for q in fila:
        faltam = total - feitas
        print('\n' + '=' * 70)
        print(f'PROGRESSO DA EXECUÇÃO: {feitas}/{total} revisadas | {faltam} faltando (inclui a atual)')
        if progresso_pasta is not None:
            total_pasta, feitas_pasta = progresso_pasta
            print(f'PROGRESSO DA PASTA: {feitas_pasta}/{total_pasta} revisadas | '
                  f'{total_pasta - feitas_pasta} faltando (inclui a atual)')
        print('QUESTÃO:', q['id'])
        print('\nENUNCIADO ORIGINAL:\n', enunciados.get(str(q['id']), '[Não encontrado no dataset original]'))
        print('\nGABARITO:\n', q.get('gabarito'))
        print('\nRESPOSTA DO MODELO:\n', q.get('resposta'))
        print('\nPARECER DO JUIZ (só triagem, não decide):', parecer_do_juiz(q) or 'sem parecer', '-', q.get('motivo'))
        r = _pedir('\nA resposta está correta? [c]orreta / [e]rrada / [s]air: ', ('c', 'e', 's'))
        if r == 's':
            exportar(arquivo, revisor, arquivo_questoes=arquivo_questoes)
            return False
        criterio = input('Critério usado (1 linha, ex.: "tem os dois totais e a conclusão"): ').strip()
        revisoes.append({'id': q['id'], 'revisor': revisor, 'acertou': r == 'c', 'criterio': criterio})
        caminho_revisoes(arquivo).write_text(json.dumps(revisoes, ensure_ascii=False, indent=2),
                                              encoding='utf-8')
        feitas += 1
        if progresso_pasta is not None:
            progresso_pasta[1] += 1
        print(f'✔ Salvo | Execução: {feitas}/{total} | Faltam: {total - feitas}')
        if progresso_pasta is not None:
            print(f'  Pasta: {progresso_pasta[1]}/{progresso_pasta[0]} | '
                  f'Faltam: {progresso_pasta[0] - progresso_pasta[1]}')
    print('\nSalvo em', caminho_revisoes(arquivo))
    destino, final = exportar(arquivo, revisor, arquivo_questoes=arquivo_questoes)
    print(f'JSON final atualizado: {destino} | pendentes: {final["resumo"]["pendentes"]}')
    return True


def arquivos_da_pasta(pasta):
    """Busca recursiva somente JSONs originais de execuções concluídas do Censo."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise NotADirectoryError(f'Pasta não encontrada: {pasta}')
    ignorar = ('.progresso.json', '.revisoes.json', '.final.json',
               '.auditado.json')
    encontrados = []
    for arquivo in sorted(pasta.rglob('*.json')):
        if arquivo.name.endswith(ignorar):
            continue
        try:
            dados = json.loads(arquivo.read_text(encoding='utf-8'))
        except (OSError, ValueError, UnicodeError):
            print('AVISO: JSON inválido ignorado:', arquivo)
            continue
        if (isinstance(dados, dict) and dados.get('dataset') == 'censo'
                and dados.get('status') == 'concluido'
                and isinstance(dados.get('resultados'), list)):
            encontrados.append(arquivo)
    return encontrados


def revisar_pasta(pasta, revisor, arquivo_questoes):
    arquivos = arquivos_da_pasta(pasta)
    print(f'{len(arquivos)} execução(ões) concluída(s) encontrada(s).')
    contagens = [contar_pendentes_arquivo(arquivo, revisor) for arquivo in arquivos]
    progresso = [sum(total for total, _ in contagens),
                sum(feitas for _, feitas in contagens)]
    print(f'PROGRESSO DA PASTA: {progresso[0]} questões para revisão | '
          f'{progresso[1]} revisadas | {progresso[0] - progresso[1]} faltando.')
    for numero, (arquivo, (total, feitas)) in enumerate(zip(arquivos, contagens), 1):
        print(f'\n[{numero}/{len(arquivos)}] {arquivo} | '
              f'{feitas}/{total} revisadas | {total - feitas} pendente(s)')
        if feitas == total:
            destino, final = exportar(arquivo, revisor, arquivo_questoes=arquivo_questoes)
            print(f'JSON final: {destino} | pendentes: {final["resumo"]["pendentes"]}')
            continue
        if not revisar(arquivo, revisor, arquivo_questoes, progresso):
            # Mesmo uma revisão parcial gera snapshot sem declarar acurácia final.
            destino, final = exportar(arquivo, revisor, arquivo_questoes=arquivo_questoes)
            print(f'JSON parcial: {destino} | pendentes: {final["resumo"]["pendentes"]}')
            print('Revisão da pasta interrompida; decisões anteriores preservadas.')
            return
    print(f'Revisão da pasta concluída: {progresso[1]}/{progresso[0]} revisadas.')


def exportar_pasta(pasta, revisor, arquivo_questoes):
    arquivos = arquivos_da_pasta(pasta)
    print(f'{len(arquivos)} execução(ões) concluída(s) encontrada(s).')
    for arquivo in arquivos:
        destino, final = exportar(arquivo, revisor, arquivo_questoes=arquivo_questoes)
        print(f'{destino} | pendentes: {final["resumo"]["pendentes"]} '
              f'| falhas técnicas: {final["resumo"]["falhas_tecnicas"]}')


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 2:
        print(__doc__)
        return 1
    cmd, arquivo = a[0], a[1]
    if cmd in ('revisar-pasta', 'exportar-pasta'):
        revisor = a[a.index('--revisor') + 1] if '--revisor' in a else 'revisor1'
        caminho_questoes = (a[a.index('--questoes') + 1] if '--questoes' in a
                           else 'dados/censo_escolar/final/censo_escolar_2025.json')
        if cmd == 'revisar-pasta':
            revisar_pasta(arquivo, revisor, caminho_questoes)
        else:
            exportar_pasta(arquivo, revisor, caminho_questoes)
        return 0
    dados = json.loads(Path(arquivo).read_text(encoding='utf-8'))
    questoes = _questoes(dados)
    revisoes = carregar_revisoes(arquivo)
    if cmd == 'pendentes':
        for q in pendentes(questoes):
            print(q['id'], '| juiz:', parecer_do_juiz(q))
    elif cmd == 'revisar':
        revisor = a[a.index('--revisor') + 1] if '--revisor' in a else 'revisor1'
        caminho_questoes = (a[a.index('--questoes') + 1] if '--questoes' in a
                           else 'dados/censo_escolar/final/censo_escolar_2025.json')
        revisar(arquivo, revisor, caminho_questoes)
    elif cmd == 'resumo':
        revisor = a[a.index('--revisor') + 1] if '--revisor' in a else None
        print(json.dumps(resumo(questoes, revisoes, revisor), ensure_ascii=False, indent=2))
    elif cmd == 'exportar':
        if '--revisor' not in a:
            print('Informe o revisor: exportar ARQUIVO.json --revisor layla')
            return 1
        saida = a[a.index('--saida') + 1] if '--saida' in a else None
        caminho_questoes = (a[a.index('--questoes') + 1] if '--questoes' in a
                           else 'dados/censo_escolar/final/censo_escolar_2025.json')
        destino, final = exportar(arquivo, a[a.index('--revisor') + 1], saida, caminho_questoes)
        print(json.dumps(final['resumo'], ensure_ascii=False, indent=2))
        if not final['resumo']['completo']:
            print(f"ATENÇÃO: faltam {final['resumo']['pendentes']} questão(ões) para revisar.")
        print('Salvo em:', destino)
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
