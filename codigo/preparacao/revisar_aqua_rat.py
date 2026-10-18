
import json
import os
import re
import tempfile
from pathlib import Path

from codigo.preparacao import baixar_e_traduzir_aqua_rat_argos as base


NUMEROS = re.compile(r'(?<!\w)\d+(?:[.,]\d+)*(?!\w)')
OPERADORES = re.compile(r'<=|>=|!=|==|≠|≤|≥|=|<|>')
FORMULAS = re.compile(
    r'(?<!\w)(?:[A-Za-z]{1,3}|\d+(?:[.,]\d+)?)'
    r'\s*(?:\^|@|[+*/=<>]|≠|≤|≥)\s*'
    r'(?:[A-Za-z]{1,3}|\d+(?:[.,]\d+)?)'
)
SIMBOLOS = '≠≤≥√∑∫∞±≈∴'
CORROMPIDOS = re.compile(r'â[€€“]|Ã[£©]|\ufffd')
INGLES = re.compile(
    r'\b(?:the answer is|how many|how much|therefore|hence|'
    r'the following|which of the following|eqautions)\b', re.I
)
NEGACAO_EN = re.compile(r"\b(?:not|never|cannot|can't|without)\b", re.I)
NEGACAO_PT = re.compile(r'\b(?:não|nunca|sem|impossível)\b', re.I)

# Uma única expressão reúne os trechos matemáticos que não devem ser traduzidos.
MATEMATICA = re.compile(
    rf'{FORMULAS.pattern}|{NUMEROS.pattern}|{OPERADORES.pattern}|'
    rf'[{re.escape(SIMBOLOS)}]'
)


def proteger_matematica(tradutor, texto, falhas, nivel=0):
    """Traduz só o texto entre números, fórmulas, operadores e símbolos."""
    partes = []
    inicio = 0
    for achado in MATEMATICA.finditer(texto):
        partes.append(traduzir_em_partes(tradutor, texto[inicio:achado.start()], falhas, nivel))
        partes.append(achado.group())
        inicio = achado.end()
    partes.append(traduzir_em_partes(tradutor, texto[inicio:], falhas, nivel))
    return ''.join(partes)


def problemas_traducao(ingles, portugues):
    """Retorna alertas; não afirma que a tradução foi revisada manualmente."""
    alertas = []
    if not isinstance(portugues, str) or not portugues.strip():
        return ['tradução vazia']
    if CORROMPIDOS.search(portugues):
        alertas.append('caracteres corrompidos')
    if INGLES.search(portugues):
        alertas.append('expressões em inglês')
    if '□' in portugues:
        alertas.append('símbolo substituído por quadrado')
    # Verifica perda, não a ordem: um símbolo pode aparecer várias vezes.
    for simbolo in SIMBOLOS:
        if ingles.count(simbolo) > portugues.count(simbolo):
            alertas.append(f'símbolo matemático perdido: {simbolo}')
    for operador in ('<=', '>=', '!=', '==', '≠', '≤', '≥'):
        if ingles.count(operador) > portugues.count(operador):
            alertas.append(f'operador perdido: {operador}')
    numeros_en = NUMEROS.findall(ingles)
    numeros_pt = NUMEROS.findall(portugues)
    # A presença de números extras em explicações pode ser legítima.
    if any(numeros_pt.count(numero) < numeros_en.count(numero) for numero in set(numeros_en)):
        alertas.append('números ausentes ou alterados')
    if NEGACAO_EN.search(ingles) and not NEGACAO_PT.search(portugues):
        alertas.append('possível perda de negação')
    return alertas


def conferir_questao(questao):
    """Verifica os três campos traduzidos contra o original inglês."""
    avisos = []
    campos = [('question_en', 'question_pt', 'enunciado'),
              ('rationale_en', 'rationale_pt', 'raciocínio')]
    for campo_en, campo_pt, nome in campos:
        if not str(questao.get(campo_en) or '').strip():
            continue
        for alerta in problemas_traducao(str(questao.get(campo_en) or ''),
                                        str(questao.get(campo_pt) or '')):
            avisos.append(f'{nome}: {alerta}')
    for letra in LETRAS:
        original = (questao.get('options_en') or {}).get(letra, '')
        traduzido = (questao.get('options_pt') or {}).get(letra, '')
        for alerta in problemas_traducao(str(original), str(traduzido)):
            avisos.append(f'alternativa {letra}: {alerta}')
    return avisos


FALHAS = Path('dados/aqua_rat/traducoes/falhas_traducao.jsonl')
REVISAO = Path('dados/aqua_rat/revisao/questoes_revisao_true.json')
LETRAS = 'ABCDE'


def salvar_json_seguro(caminho, objeto):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=caminho.parent,
                                         prefix='.aqua_', suffix='.tmp', delete=False) as f:
            tmp = Path(f.name)
            json.dump(objeto, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, caminho)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def traduzir_em_partes(tradutor, trecho, sem_traducao, nivel=0):
    """Tenta traduzir; se vier vazio/erro, divide recursivamente em palavras."""
    if not trecho.strip() or not re.search(r'[A-Za-z]', trecho):
        return trecho
    prefixo = trecho[:len(trecho) - len(trecho.lstrip())]
    sufixo = trecho[len(trecho.rstrip()):]
    miolo = trecho.strip()
    try:
        resultado = tradutor.translate(miolo)
        if isinstance(resultado, str) and resultado.strip():
            return prefixo + resultado.strip() + sufixo
    except Exception:
        pass
    if nivel < 12:
        palavras = re.findall(r'\S+\s*', miolo)
        if len(palavras) > 1:
            meio = len(palavras) // 2
            return (prefixo
                    + proteger_matematica(tradutor, ''.join(palavras[:meio]), sem_traducao, nivel + 1)
                    + proteger_matematica(tradutor, ''.join(palavras[meio:]), sem_traducao, nivel + 1)
                    + sufixo)
    sem_traducao.append(miolo)
    return trecho


def traducao_preenchida(q):
    if not isinstance(q, dict):
        return False
    if not isinstance(q.get('question_pt'), str) or not q['question_pt'].strip():
        return False
    op = q.get('options_pt')
    if not isinstance(op, dict) or any(not isinstance(op.get(l), str) or not op[l].strip() for l in LETRAS):
        return False
    if str(q.get('rationale_en') or '').strip() and not str(q.get('rationale_pt') or '').strip():
        return False
    return True


def carregar_falhas():
    falhas = {}
    if not FALHAS.exists():
        return falhas
    with FALHAS.open(encoding='utf-8') as f:
        for n, linha in enumerate(f, 1):
            if not linha.strip():
                continue
            item = json.loads(linha)
            if not isinstance(item, dict) or not isinstance(item.get('id'), str):
                raise ValueError(f'Falha inválida na linha {n} de {FALHAS}')
            falhas[item['id']] = item
    return falhas


def carregar_progresso():
    """Lê o JSONL sem alterar seu conteúdo e verifica IDs duplicados."""
    registros = {}
    with base.ARQUIVO_TRADUCOES_EM_ANDAMENTO.open(encoding='utf-8') as f:
        for n, linha in enumerate(f, 1):
            if not linha.strip():
                continue
            q = json.loads(linha)
            id_ = q['id']
            if id_ in registros:
                raise ValueError(f'ID duplicado no progresso: {id_}, linha {n}')
            registros[id_] = q
    return registros


def atualizar_progresso(substituicoes, acrescimos):
    """Reescreve atomicamente o progresso somente se houver recuperação."""
    if not substituicoes and not acrescimos:
        return
    destino = base.ARQUIVO_TRADUCOES_EM_ANDAMENTO
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=destino.parent,
                                         prefix='.aqua_progresso_', suffix='.tmp', delete=False) as saida:
            tmp = Path(saida.name)
            with destino.open(encoding='utf-8') as entrada:
                for linha in entrada:
                    if not linha.strip():
                        continue
                    q = json.loads(linha)
                    novo = substituicoes.get(q['id'])
                    saida.write(json.dumps(novo if novo is not None else q, ensure_ascii=False) + '\n')
            for q in acrescimos:
                saida.write(json.dumps(q, ensure_ascii=False) + '\n')
            saida.flush()
            os.fsync(saida.fileno())
        os.replace(tmp, destino)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def recuperar_traducao(q, tradutor):
    trechos_falhos = []
    funcao_original = base.traduzir_parte_sem_matematica
    try:
        base.traduzir_parte_sem_matematica = (
            lambda modelo, texto: proteger_matematica(modelo, texto, trechos_falhos)
        )
        resultado = base.traduzir_questao(q, tradutor)
    finally:
        base.traduzir_parte_sem_matematica = funcao_original
    if trechos_falhos:
        raise ValueError(f'{len(trechos_falhos)} trecho(s) não traduzido(s): {trechos_falhos[:2]!r}')
    if not traducao_preenchida(resultado):
        raise ValueError('Enunciado, alternativas ou raciocínio com tradução vazia')
    avisos = conferir_questao(resultado)
    if avisos:
        resultado['revisao_necessaria'] = True
        print(f"Avisos em {resultado.get('id')}: {', '.join(avisos[:4])}")
    return {k: resultado[k] for k in base.ORDEM_CAMPOS}


def executar_revisao():
    for caminho in (base.ARQUIVO_ORIGINAL, base.ARQUIVO_TRADUCOES_EM_ANDAMENTO, base.ARQUIVO_FINAL):
        if not caminho.is_file():
            raise FileNotFoundError(caminho)

    falhas = carregar_falhas()
    progresso = carregar_progresso()
    originais = {}
    for q in base.percorrer_questoes_originais():
        id_ = q['id']
        if id_ in originais:
            raise ValueError(f'ID duplicado no original: {id_}')
        originais[id_] = q
    with base.ARQUIVO_FINAL.open(encoding='utf-8') as f:
        dados = json.load(f)
    if not isinstance(dados, dict) or not isinstance(dados.get('problemas'), list):
        raise ValueError('JSON final inválido: falta a lista problemas')
    final = {}
    for q in dados['problemas']:
        id_ = q['id']
        if id_ in final:
            raise ValueError(f'ID duplicado no JSON final: {id_}')
        final[id_] = q
    for nome, ids in (('progresso', set(progresso)), ('final', set(final)), ('falhas', set(falhas))):
        desconhecidos = ids - set(originais)
        if desconhecidos:
            raise ValueError(f'IDs desconhecidos em {nome}: {sorted(desconhecidos)[:5]}')

    # Registros existentes válidos não são retraduzidos, mesmo que estejam no histórico.
    # Registros ausentes do final são primeiro recuperados do progresso.
    recuperados_progresso = 0
    for id_, q in progresso.items():
        if id_ not in final and traducao_preenchida(q):
            final[id_] = q
            dados['problemas'].append(q)
            recuperados_progresso += 1

    # Só aciona Argos para IDs realmente ausentes/inválidos ou falhas ainda não resolvidas.
    alvos = [id_ for id_ in originais if
             id_ not in progresso or id_ not in final or
             (id_ in falhas and (not traducao_preenchida(progresso.get(id_)) or
                                not traducao_preenchida(final.get(id_))))]
    print(f'Original: {len(originais)} | Progresso: {len(progresso)} | '
          f'Final: {len(final)} | Histórico de falhas: {len(falhas)} | '
          f'Necessitam tradução: {len(alvos)}')
    if recuperados_progresso:
        print(f'Restauradas do progresso para o final: {recuperados_progresso}')

    substituicoes = {}
    acrescimos = []
    erros = {}
    tradutor = None
    for id_ in alvos:
        # Nunca substituir uma tradução existente válida por uma tradução automática.
        if id_ in final and traducao_preenchida(final[id_]) and id_ in progresso and traducao_preenchida(progresso[id_]):
            continue
        try:
            if tradutor is None:
                tradutor = base.carregar_tradutor_argos()
            novo = recuperar_traducao(originais[id_], tradutor)
            if id_ in progresso:
                # Atualiza apenas o registro que tinha campos inválidos.
                if not traducao_preenchida(progresso[id_]):
                    substituicoes[id_] = novo
            else:
                acrescimos.append(novo)
            if id_ in final:
                # Não sobrescrever registros válidos do final.
                if not traducao_preenchida(final[id_]):
                    pos = next(i for i, item in enumerate(dados['problemas']) if item['id'] == id_)
                    dados['problemas'][pos] = novo
                    final[id_] = novo
            else:
                dados['problemas'].append(novo)
                final[id_] = novo
            print(f'Recuperada: {id_}')
        except Exception as exc:
            erros[id_] = f'{type(exc).__name__}: {exc}'
            print(f'Falha persistente: {id_}: {exc}')

    # Sinaliza traduções suspeitas existentes sem substituí-las nem afirmar revisão.
    marcadas = 0
    for questao in dados['problemas']:
        if questao.get('revisao_necessaria') is False:
            continue  # Preserva revisões já confirmadas.
        if conferir_questao(questao) and questao.get('revisao_necessaria') is not True:
            questao['revisao_necessaria'] = True
            marcadas += 1
    if marcadas:
        print(f'Questões sinalizadas para revisão: {marcadas}')

    # Grava progresso antes do final; se houver interrupção, a próxima execução
    # recupera os registros do progresso sem repetir a tradução.
    atualizar_progresso(substituicoes, acrescimos)
    atualizou_final = bool(recuperados_progresso or substituicoes or acrescimos or marcadas)
    info = dados.setdefault('dataset_info', {})
    total_true = sum(q.get('revisao_necessaria') is True for q in dados['problemas'])
    total_atual = len(dados['problemas'])
    novos_metadados = {
        'registros_traduzidos': total_atual,
        'registros_pendentes': len(originais) - total_atual,
        'traducao_concluida': total_atual == len(originais),
        'questoes_com_revisao_necessaria': total_true,
    }
    if any(info.get(k) != v for k, v in novos_metadados.items()):
        info.update(novos_metadados)
        atualizou_final = True
    if atualizou_final:
        salvar_json_seguro(base.ARQUIVO_FINAL, dados)
        print('JSON final atualizado (recuperações e/ou contagens).')

    # Só apaga o histórico quando todos os seus IDs estão válidos em ambos os arquivos.
    pendentes = {}
    for id_ in set(originais) - set(final):
        pendentes[id_] = {'id': id_, 'erro': erros.get(id_, 'Ausente do JSON final')}
    for id_ in set(originais) - (set(progresso) | {q['id'] for q in acrescimos}):
        pendentes[id_] = {'id': id_, 'erro': erros.get(id_, 'Ausente do progresso')}
    for id_ in falhas:
        registro_progresso = substituicoes.get(id_, progresso.get(id_))
        if id_ not in final or not traducao_preenchida(final[id_]) or not traducao_preenchida(registro_progresso):
            pendentes[id_] = {'id': id_, 'erro': erros.get(id_, 'Tradução incompleta ou ausente')}
    for id_, erro in erros.items():
        pendentes[id_] = {'id': id_, 'erro': erro}

    if pendentes:
        FALHAS.parent.mkdir(parents=True, exist_ok=True)
        # Histórico da tradução, não relatório de revisão.
        tmp = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=FALHAS.parent,
                                             prefix='.falhas_', suffix='.tmp', delete=False) as f:
                tmp = Path(f.name)
                for item in pendentes.values():
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, FALHAS)
        finally:
            if tmp is not None and tmp.exists():
                tmp.unlink()
        print(f'Falhas ainda pendentes: {len(pendentes)} ({FALHAS})')
    elif FALHAS.exists():
        FALHAS.unlink()
        print(f'Histórico de falhas excluído: {FALHAS}')
    else:
        print('Nenhuma falha de tradução pendente.')

    selecionadas = [q for q in dados['problemas'] if q.get('revisao_necessaria') is True]
    salvar_json_seguro(REVISAO, {'total_questoes': len(selecionadas), 'problemas': selecionadas})
    print(f'Questões true exportadas: {len(selecionadas)} -> {REVISAO}')
    print('Questões false preservadas; questões true não foram retraduzidas para revisão.')


if __name__ == '__main__':
    executar_revisao()