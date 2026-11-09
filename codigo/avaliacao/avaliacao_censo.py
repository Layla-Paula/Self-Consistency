"""Avaliacao compartilhada do Censo"""

import re
import json
import unicodedata
from collections import Counter

def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', str(texto).lower())
    return ''.join(c for c in texto if not unicodedata.combining(c))

def _numeros(texto):
    # Captura milhares brasileiros (178.766) e inteiros sem separador (178766).
    tokens = re.findall(r'(?<![\w])\d{1,3}(?:\.\d{3})+(?:,\d+)?|(?<![\w])\d+(?:[.,]\d+)?', str(texto))
    valores = set()
    for token in tokens:
        if re.fullmatch(r'\d{1,3}(?:\.\d{3})+', token):
            valores.add(int(token.replace('.', '')))
        elif token.isdigit():
            valores.add(int(token))
    return valores

# Extracao numerica: separador de milhar brasileiro e decimais com virgula/ponto.
# O texto original nao e modificado; nunca usar comparacao por substring.
from decimal import Decimal, InvalidOperation

_PADRAO_VALOR = re.compile(r"(?<![\w])[-+]?\d{1,3}(?:\.\d{3})+(?:,\d+)?(?![\w])|(?<![\w])[-+]?\d+(?:[.,]\d+)?(?![\w])")

def _valores_decimais(texto):
    valores = []
    for m in _PADRAO_VALOR.finditer(str(texto)):
        token = m.group()
        if re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{3})+(?:,\d+)?", token):
            token = token.replace('.', '').replace(',', '.')
        else:
            token = token.replace(',', '.')
        try:
            valores.append(Decimal(token))
        except InvalidOperation:
            pass
    return valores

def _numero_exato(texto, esperado):
    return Decimal(str(esperado).replace(',', '.')) in _valores_decimais(texto)

def _rotulo_valor(texto, rotulo, esperado):
    # O valor deve estar associado ao rotulo na mesma linha/segmento.
    # Suporta 'Norte: 24,42%' e '24,42% - Norte'.
    t = _normalizar(texto)
    partes = re.split(r'[\n;|]', t)
    for parte in partes:
        if re.search(r'\b' + re.escape(_normalizar(rotulo)) + r'\b', parte) and _numero_exato(parte, esperado):
            return True
    return False

def _avaliacao_deterministica(gabarito, resposta):
    """Só confirma acerto quando há um número único e inequívoco no gabarito.

    Não usa coincidência de números para aprovar perguntas de comparação,
    interpretação, múltiplas categorias ou percentuais.
    """
    numeros = {n for n in _numeros(gabarito) if n >= 1000}
    if len(numeros) != 1:
        return None
    valor = next(iter(numeros))
    # Valores isolados não bastam quando o gabarito exige explicação conceitual.
    palavras = _normalizar(gabarito)
    if any(p in palavras for p in ('segundo o dicionario', 'representa', 'distingue',
                                   'significa', 'indica que', 'percentual', 'media',
                                   'categoria', 'por dependencia', 'por regiao',
                                   'por localizacao', 'compar')):
        return None
    # Garante que a resposta afirma o valor e não apenas o inclui em código de exemplo.
    texto = re.sub(r'```.*?```', '', str(resposta), flags=re.S)
    if valor in _numeros(texto):
        return True, 'Valor principal do gabarito encontrado na resposta em texto.'
    return None

def _extrair_json(texto):
    if not texto:
        return None
    try:
        return json.loads(texto)
    except (ValueError, TypeError):
        trecho = re.search(r'\{[\s\S]*\}', str(texto))
        if trecho:
            try:
                return json.loads(trecho.group())
            except ValueError:
                pass
    return None

def _tem_valor(texto, valor):
    """Reconhece inteiros com ou sem separadores de milhar."""
    return _numero_exato(texto, valor)

# Siglas e nomes de UFs reconhecidos com fronteiras de palavra.
_UFS = {
    'AC':'acre','AL':'alagoas','AP':'amapa','AM':'amazonas',
    'BA':'bahia','CE':'ceara','DF':'distrito federal','ES':'espirito santo',
    'GO':'goias','MA':'maranhao','MT':'mato grosso','MS':'mato grosso do sul',
    'MG':'minas gerais','PA':'para','PB':'paraiba','PR':'parana',
    'PE':'pernambuco','PI':'piaui','RJ':'rio de janeiro',
    'RN':'rio grande do norte','RS':'rio grande do sul','RO':'rondonia',
    'RR':'roraima','SC':'santa catarina','SP':'sao paulo',
    'SE':'sergipe','TO':'tocantins',
}

def _ufs_citadas(resposta):
    texto = _normalizar(resposta)
    # Primeiro retira nomes completos para não confundir 'mato grosso' com MS.
    encontradas = set()
    for uf, nome in sorted(_UFS.items(), key=lambda par: -len(par[1])):
        if uf == 'PA':  # 'para' é também uma preposição comum.
            continue
        padrao = r'(?<![a-z])' + re.escape(nome) + r'(?![a-z])'
        if re.search(padrao, texto):
            encontradas.add(uf)
            texto = re.sub(padrao, ' ', texto)
    for uf in _UFS:
        if uf == 'PA':
            if re.search(r'(?<![A-Za-z])PA(?![A-Za-z])', str(resposta)):
                encontradas.add(uf)
            continue
        if re.search(r'(?<![a-z])' + uf.lower() + r'(?![a-z])', texto):
            encontradas.add(uf)
    return encontradas

def _par_numero(resposta, rotulos, valor):
    # Não basta mencionar o número correto em qualquer ponto do texto.
    linhas = re.split(r'[\n;]', _normalizar(resposta))
    for linha in linhas:
        if any(re.search(r'\b' + re.escape(r) + r'\b', linha) for r in rotulos):
            if _tem_valor(linha, valor):
                return True
    return False

def _contradicao_soma(resposta, valores):
    # Sinaliza a apresentação de uma soma como total da categoria.
    texto = _normalizar(resposta)
    return any(re.search(r'(?<!\d)' + str(v) + r'\s*\+\s*\d', texto)
               for v in valores)

def _valor_do_token(token):
    if re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{3})+(?:,\d+)?", token):
        token = token.replace('.', '').replace(',', '.')
    else:
        token = token.replace(',', '.')
    try:
        return Decimal(token)
    except InvalidOperation:
        return None


def _aceitos(valor, inteiro=False):
    """Valores aceitos para uma média: o decimal oficial e, se inteiro=True,
    também as versões truncada e arredondada (535,7 -> 535 ou 536)."""
    base = Decimal(str(valor))
    if not inteiro:
        return {base}
    return {base, base.to_integral_value(rounding='ROUND_DOWN'),
            base.to_integral_value(rounding='ROUND_HALF_UP')}


def _agrupar_em_trechos(fichas):
    """Divide a lista de fichas em trechos de rótulos e de números que se alternam."""
    trechos = []
    for ficha in fichas:
        if trechos and trechos[-1][0] == ficha[1]:
            trechos[-1][1].append(ficha)
        else:
            trechos.append((ficha[1], [ficha]))
    return [lista for _, lista in trechos]


def _parear_trechos(trechos, saida):
    """Liga cada trecho de números ao trecho de rótulos vizinho.

    Devolve True se houver ambiguidade (por exemplo, dois rótulos para três números)."""
    ambiguo = False
    rotulos_primeiro = trechos[0][0][1] == 'L'
    for i in range(0, len(trechos) - 1, 2):
        par = trechos[i:i + 2]
        if len(par) < 2:
            break
        rotulos, numeros = (par[0], par[1]) if rotulos_primeiro else (par[1], par[0])
        chaves = []
        for ficha in rotulos:
            if not chaves or chaves[-1] != ficha[2]:
                chaves.append(ficha[2])
        valores = [ficha[2] for ficha in numeros]
        if len(chaves) == 1:
            saida[chaves[0]].extend(valores)
        elif len(chaves) == len(valores):
            for chave, valor in zip(chaves, valores):
                saida[chave].append(valor)
        else:
            ambiguo = True
    return ambiguo


def _conferir_pares(resposta, pares):
    """Confere se cada rótulo recebeu o seu valor, sem trocas.

    pares = {chave: (sinônimos, valores_aceitos)}. Funciona com o número depois do
    rótulo ("Urbana: 128.037"), antes dele ("128.037 escolas urbanas"), em tabelas
    (uma linha por rótulo) e com vários números por rótulo.
    Devolve True, False, ou None quando a associação é ambígua (vai para revisão)."""
    texto = _normalizar(resposta)
    padroes = {chave: re.compile(r'\b(?:' + '|'.join(sins) + r')\b') for chave, (sins, _) in pares.items()}
    donos = {chave: [] for chave in pares}
    ambiguo = False
    for segmento in re.split(r'\.\s+|[\n;]', texto):
        fichas = []
        for chave, padrao in padroes.items():
            fichas += [(m.start(), 'L', chave) for m in padrao.finditer(segmento)]
        for m in _PADRAO_VALOR.finditer(segmento):
            valor = _valor_do_token(m.group())
            if valor is not None:
                fichas.append((m.start(), 'N', valor))
        if not any(f[1] == 'L' for f in fichas) or not any(f[1] == 'N' for f in fichas):
            continue
        fichas.sort(key=lambda f: f[0])
        ambiguo |= _parear_trechos(_agrupar_em_trechos(fichas), donos)
    aceitos = {chave: valores for chave, (_, valores) in pares.items()}
    for chave, recebidos in donos.items():
        for valor in recebidos:
            if any(valor in aceitos[outra] and valor not in aceitos[chave]
                   for outra in aceitos if outra != chave):
                return False  # valor de outro rótulo atribuído a este
    if all(any(v in aceitos[chave] for v in donos[chave]) for chave in pares):
        return True
    return None if ambiguo else False


def _tem_contradicao_total(texto, correto):
    """Evita aprovar números concorrentes declarados como total no mesmo enunciado."""
    t = _normalizar(texto)
    # Conflitos explícitos após 'mas', 'porem' ou 'na verdade'.
    for trecho in re.split(r'\b(?:mas|porem|na verdade|entretanto)\b', t)[1:]:
        if re.search(r'\b(?:total|verdadeiro|correto|sao|existem|ha)\b', trecho):
            vals = [v for v in _valores_decimais(trecho) if v >= 1000]
            if re.search(r'\b\d+(?:[.,]\d+)?\s+(?:milhoes|milhao|bilhoes|bilhao)\b', trecho):
                return True
            if any(v != Decimal(correto) for v in vals):
                return True
    return False


# Política (definida pela enunciado de cada questão): quando o enunciado manda SOMAR/CALCULAR,
# a resposta precisa trazer os totais; quando só pergunta "qual é maior", a conclusão basta,
# desde que nenhum número informado contradiga o gabarito.
_RECUSA = re.compile(r'nao (?:foi possivel|e possivel|ha como|consegu)|nao (?:permit|contem|conteve|foi fornecid|foi encontrad|exist)|'
                     r'ausencia d|impossibilit|nao ha (?:dados|registros)|dados consultados nao')


def _numeros_grandes(resposta, minimo=1000):
    """Valores que parecem totais (>= minimo) ou zero; ignora '4 a 5 anos', anos e ordinais."""
    return [v for v in _valores_decimais(resposta) if v == 0 or abs(v) >= minimo]


def _decidir_comparativa(resposta, pares, certa=None, errada=None, percentuais=False,
                         exige_totais=False, basta_conclusao=False):
    """Rubrica para perguntas do tipo 'compare A e B' (totais + conclusão).

    Devolve (acertou, motivo) quando há certeza e None quando é uma meia resposta
    (conclusão sem números, associação ambígua ou conclusão não reconhecida),
    que continua indo para a revisão humana.
      - valores corretos + conclusão correta                     -> certo
      - conclusão errada, números que não batem ou recusa de responder -> errado
      - conclusão certa mas sem números                          -> revisão humana
    """
    t = _normalizar(resposta)
    ok_certa = bool(certa and re.search(certa, t))
    ok_errada = bool(errada and re.search(errada, t))
    if ok_certa and ok_errada:
        return None
    if ok_errada:
        return False, 'Conclusão contrária ao gabarito.'
    esperados = set().union(*(v for _, v in pares.values()))
    valores = _valores_decimais(resposta)
    if percentuais:
        tem_numero = bool(valores)
    else:
        tem_numero = bool(_numeros_grandes(resposta))
    algum_esperado = any(v in esperados for v in valores)
    confere = _conferir_pares(resposta, pares)
    if confere is None:
        # associação ambígua: só decide se NENHUM valor correto aparece na resposta
        if not algum_esperado and tem_numero:
            return False, 'Os valores informados não conferem com o gabarito.'
        return None
    if confere:
        if ok_certa or certa is None:
            return True, 'Valores e conclusão conferem com o gabarito.'
        return None
    if tem_numero:
        return False, 'Os valores informados não conferem com o gabarito.'
    if _RECUSA.search(t):
        return False, 'A resposta não apresenta o resultado solicitado.'
    if basta_conclusao and ok_certa:
        return True, 'O enunciado só pede a conclusão, e ela está correta (sem números contraditórios).'
    if exige_totais:
        return False, 'O enunciado pede os totais e a resposta não os apresenta.'
    return None


def _criterios_censo(questao, resposta):
    """Rubricas objetivas para as questões 01–20, com base nos gabaritos.

    Não utiliza a resposta esperada como resposta do modelo. O ID apenas
    seleciona os critérios; o texto produzido precisa satisfazê-los.
    As demais questões continuam na avaliação semântica automática.
    """
    identificador = str(questao.get('id', ''))
    try:
        numero = int(identificador.rsplit('_', 1)[-1])
    except ValueError:
        return None
    t = _normalizar(resposta)
    tem = lambda x: _tem_valor(resposta, x)
    def decisao(ok, explicacao):
        return {'acertou': bool(ok), 'motivo': explicacao,
                'revisao_necessaria': False, 'metodo_avaliacao': 'rubrica_objetiva_censo'}
    def _decisao_pares(resposta, pares, explicacao, extra=True):
        # Associação ambígua entre rótulos e números: sem decisão automática (vai para revisão).
        resultado = _conferir_pares(resposta, pares)
        if resultado is None:
            return None
        return decisao(resultado and extra, explicacao)

    if numero == 1:
        return decisao(tem(178766) and not re.search(r'(?<!\d)0\s+escolas\b', t), 'Total correto de escolas, sem afirmação contraditória.')
    if numero == 2:
        return decisao(tem(46018380) and not _tem_contradicao_total(resposta, 46018380), 'Verificação do total de matrículas, não apenas do código proposto.')
    if numero == 3:
        return decisao(('atividade complementar' in t and ('aee' in t or 'atendimento educacional especializado' in t)),
                       'Devem ser identificados os dois tipos de turma excluídos.')
    if numero == 4:
        # A questão 04 exige contagem e identificação das 27 UFs.
        # Aceita siglas ou nomes completos, sem confundir PA com a preposição "para".
        ufs = {
            'AC': 'acre', 'AL': 'alagoas', 'AP': 'amapa', 'AM': 'amazonas',
            'BA': 'bahia', 'CE': 'ceara', 'DF': 'distrito federal',
            'ES': 'espirito santo', 'GO': 'goias', 'MA': 'maranhao',
            'MT': 'mato grosso', 'MS': 'mato grosso do sul',
            'MG': 'minas gerais', 'PA': 'para', 'PB': 'paraiba',
            'PR': 'parana', 'PE': 'pernambuco', 'PI': 'piaui',
            'RJ': 'rio de janeiro', 'RN': 'rio grande do norte',
            'RS': 'rio grande do sul', 'RO': 'rondonia',
            'RR': 'roraima', 'SC': 'santa catarina',
            'SP': 'sao paulo', 'SE': 'sergipe', 'TO': 'tocantins',
        }
        # Procura nomes completos do maior para o menor para evitar
        # que "Mato Grosso" seja confundido com "Mato Grosso do Sul".
        texto_nomes = t
        identificadas = set()
        for uf, nome in sorted(ufs.items(), key=lambda item: -len(item[1])):
            if uf == 'PA':
                # "para" isolado pode ser apenas uma preposição.
                continue
            padrao_nome = r'(?<![a-z])' + re.escape(nome) + r'(?![a-z])'
            if re.search(padrao_nome, texto_nomes):
                identificadas.add(uf)
                texto_nomes = re.sub(padrao_nome, ' ', texto_nomes)
        # Siglas são verificadas no texto original com letras maiúsculas.
        # Isso impede que palavras comuns sejam tomadas como siglas.
        for uf in ufs:
            if re.search(r'(?<![A-Za-z])' + uf + r'(?![A-Za-z])', str(resposta)):
                identificadas.add(uf)
        quantidade = bool(re.search(r'(?<!\d)27(?!\d)', t))
        completa = len(identificadas) == 27
        return decisao(quantidade and completa,
                       'Deve informar 27 UFs e identificar todas as 26 unidades estaduais e o Distrito Federal.')
    if numero == 5:
        return decisao(tem(5571) and not ('uf' in t and 'value_counts' in t),
                       'Deve identificar 5.571 municípios distintos; contar UFs não resolve.')
    if numero == 6:
        return decisao('nu_ano_censo' in t and '2025' in t and ('ano' in t or 'referencia' in t),
                       'Variável, significado e ano de referência.')
    if numero == 7:
        negativa = bool(re.search(r'\b(nao\s+(?:existe|existem|ha)|nenhuma escola|zero ocorrencias|0 ocorrencias)\b', t))
        afirmacao = bool(re.search(r'(?<!nao )\b(?:existe|existem|ha)\s+(?:alguma|uma|escola|escolas)', t)) and not negativa
        return decisao(negativa and not afirmacao and not re.search(r'\b(?:mas|porem|entretanto)\s+(?:ha|existem|existe)\b', t), 'Não há escolas com QT_MAT_BAS igual a zero.')
    if numero == 8:
        correta = ('co_rede' in t and 'tp_dependencia' in t and
                   ('publica' in t and 'privada' in t) and
                   ('federal' in t and 'estadual' in t and 'municipal' in t))
        bloco = re.search(r'co_rede.{0,180}(?:tp_dependencia|ja a variavel)', t, flags=re.S)
        erro_rede = bool(bloco and all(x in bloco.group() for x in ('federal', 'estadual', 'municipal', 'privada')))
        return decisao(correta and not erro_rede and ('duas' in t or '2 categoria' in t or 'publica e privada' in t),
                       'CO_REDE agrupa pública/privada; TP_DEPENDENCIA possui quatro categorias.')
    if numero == 9:
        return _decisao_pares(resposta, {
            'publica': (('publica', 'publicas'), {Decimal(137020)}),
            'privada': (('privada', 'privadas'), {Decimal(41746)})},
            'Contagens das redes pública e privada.')
    if numero == 10:
        conclusao_errada = re.search(r'\b(?:estadual|federal|privada)\s+(?:concentra|tem|possui)\s+(?:o\s+)?maior', t)
        return _decisao_pares(resposta, {
            'federal': (('federal', 'federais'), {Decimal(383526)}),
            'estadual': (('estadual', 'estaduais'), {Decimal(13330302)}),
            'municipal': (('municipal', 'municipais'), {Decimal(23059168)}),
            'privada': (('privada', 'privadas'), {Decimal(9245384)})},
            'Quatro totais de matrículas por dependência e predominância municipal.',
            extra=not conclusao_errada)
    if numero == 11:
        return decisao('federal' in t and tem(716) and tem(383526),
                       'Menor dependência é federal, com 716 escolas e 383.526 matrículas.')
    if numero == 12:
        return _decisao_pares(resposta, {
            'federal': (('federal', 'federais'), _aceitos('535.7', True)),
            'estadual': (('estadual', 'estaduais'), _aceitos('448.3', True)),
            'municipal': (('municipal', 'municipais'), _aceitos('216.4', True)),
            'privada': (('privada', 'privadas'), _aceitos('221.5', True))},
            'Médias por todas as quatro dependências e identificação da maior.')
    if numero == 13:
        return _decisao_pares(resposta, {
            'municipal': (('municipal', 'municipais'), _aceitos('216.4', True)),
            'estadual': (('estadual', 'estaduais'), _aceitos('448.3', True))},
            'Comparação efetiva entre as médias municipal e estadual.',
            extra=('metade' in t or 'dobro' in t or 'menor' in t))
    if numero == 14:
        return decisao('tp_categoria_escola_privada' in t and all(x in t for x in
                       ('particular', 'comunitaria', 'confessional', 'filantropica')),
                       'Variável e as quatro categorias privadas.')
    if numero == 15:
        return _decisao_pares(resposta, {
            'particular': (('particular', 'particulares'), {Decimal(7085034)}),
            'filantropica': (('filantropica', 'filantropicas'), {Decimal(1711268)})},
            'Matrículas particular e filantrópica e comparação conclusiva entre ambas.',
            extra=(('maior' in t or 'mais matriculas' in t or 'superior' in t or 'concentra' in t)
                   and not re.search(r'filantropica\s+(?:concentra|tem|possui)\s+(?:o\s+)?(?:maior|mais)', t)))
    if numero == 16:
        return decisao('parceria' in t and ('poder publico' in t or 'administracao publica' in t) and ('financiamento' in t or 'convenio' in t or 'itinerario' in t),
                       'Interpretação da parceria com o poder público.')
    if numero == 17:
        return _decisao_pares(resposta, {
            'urbana': (('urbana', 'urbanas', 'urbano', 'urbanos'), {Decimal(128037)}),
            'rural': (('rural', 'rurais'), {Decimal(50729)})},
            'Exige os dois totais por localização, sem apresentar somas contraditórias como totais.',
            extra=not _contradicao_soma(resposta, (128037, 50729)))
    if numero == 18:
        return _decisao_pares(resposta, {
            'urbana': (('urbana', 'urbanas', 'urbano', 'urbanos'), {Decimal(40871166)}),
            'rural': (('rural', 'rurais'), {Decimal(5147214)})},
            'Totais corretos de matrículas urbanas e rurais, sem afirmar igualdade.',
            extra=not re.search(r'\b(iguais|mesmo total|mesma quantidade)\b', t))
    if numero == 19:
        return _decisao_pares(resposta, {
            'urbana': (('urbana', 'urbanas', 'urbano', 'urbanos'), _aceitos('319.2', True)),
            'rural': (('rural', 'rurais'), _aceitos('101.5', True))},
            'Médias urbana e rural corretas, sem valor urbano contraditório.',
            extra=(not tem(270) and not re.search(r'\b(?:e tambem|mas tambem)\s*\d', t)))
    if numero == 20:
        regioes = {'norte': '24.42', 'nordeste': '21.34', 'centro-oeste': '5.90', 'sul': '5.77', 'sudeste': '3.30'}
        ok = all(_rotulo_valor(resposta, regiao, valor) for regiao, valor in regioes.items())
        # Se a resposta agrupar varias regioes na mesma linha, a associacao
        # nao e inequivoca; encaminhar ao avaliador semantico.
        if any(sum(bool(re.search(r'\b'+re.escape(r)+r'\b', linha)) for r in regioes) > 1 for linha in _normalizar(resposta).splitlines()):
            return None
        return decisao(ok and 'norte' in t, 'Percentuais exatos associados às cinco regiões.')
    # As questões 22 e 23 pedem QUAIS UFs, não os valores por UF.
    # Não exigir os números evita falsos negativos de respostas corretas.
    if numero in (22, 23):
        esperadas = ({'SP', 'MG', 'BA', 'RJ', 'PR'} if numero == 22 else
                     {'RR', 'AP', 'AC', 'RO', 'TO'})
        citadas = _ufs_citadas(resposta)
        return decisao(citadas == esperadas,
                       'Comparação exata do conjunto das cinco UFs; ordem e valores não exigidos.')
    # Casos em que o juiz semântico aceitou contradições verificáveis.
    if numero == 28:
        # A pergunta exige a comparação; inverter a direção é erro inequívoco.
        invertida = bool(re.search(r'anos iniciais.{0,100}(?:menor(?:es)?|menos|inferior(?:es)?)\s+(?:que|do que|aos?)', t, re.S))
        invertida |= bool(re.search(r'anos finais.{0,100}(?:maior(?:es)?|mais|superior(?:es)?)\s+(?:que|do que|aos?)', t, re.S))
        invertida |= bool(re.search(r'anos iniciais.{0,65}(?:menos|menor(?:es)?|inferior(?:es)?).{0,65}anos finais', t, re.S))
        if invertida:
            return decisao(False, 'Contradição: Anos Iniciais têm MAIS matrículas que Anos Finais.')
        # Para as demais: diferença ou os dois totais corretos + tendência = acerto;
        # números errados = erro; só a tendência (sem números) continua com o revisor.
        tem_interpretacao = bool(re.search(r'evasao|retencao|distorcao|fluxo|reducao|queda|diminu|abandono', t))
        if tem(3221721) and tem_interpretacao:
            return decisao(True, 'Diferença correta (3.221.721) e interpretação do fluxo escolar.')
        if not tem(3221721):
            # diferença errada (ex.: 3.217.721) mesmo com os dois totais corretos
            if any(3000000 <= v <= 3500000 for v in _valores_decimais(resposta)):
                return decisao(False, 'A diferença informada não é 3.221.721.')
            if _numeros_grandes(resposta) and not (tem(14514244) and tem(11292523)):
                return decisao(False, 'Os totais ou a diferença informados não conferem com o gabarito.')
            if _RECUSA.search(t):
                return decisao(False, 'A resposta não apresenta a diferença solicitada.')
        return None
    if numero == 41:
        # A associacao das faixas etarias as etapas pode aparecer em periodos
        # diferentes; janelas de caracteres cruzam afirmacoes corretas.
        # Deixar a avaliacao semantica decidir sem falso negativo automatico.
        # (Agora: totais exatos + etapas; meia resposta continua indo ao revisor.)
        r = _decidir_comparativa(resposta, {
            'faixa6': (('6 a 10 anos', '6 a 10'), {Decimal(14111254)}),
            'faixa11': (('11 a 14 anos', '11 a 14'), {Decimal(11194106)})},
            certa=r'anos iniciais.{0,120}(?:6 a 10|6-10)|(?:6 a 10|6-10).{0,120}anos iniciais')
        return decisao(*r) if r else None
    if numero == 43:
        # Não aceitar separadores numéricos malformados como se fossem totais corretos.
        if re.search(r'(?<!\d)496\.8651(?!\d)', t):
            return decisao(False, 'Total de 4 a 5 anos foi escrito incorretamente: 496.8651.')
        r = _decidir_comparativa(resposta, {
            'creche': (('0 a 3 anos', '0 a 3'), {Decimal(3874541)}),
            'pre': (('4 a 5 anos', '4 a 5'), {Decimal(4968651)})},
            certa=r'(?:4 a 5|4 e 5)[^.;\n\d]{0,60}(?:maior|mais|concentra|superior)|(?:maior|mais)[^.;\n\d]{0,60}(?:4 a 5|4 e 5)',
            errada=r'(?:0 a 3)[^.;\n\d]{0,60}(?:tem|apresenta|possui|e a)[^.;\n\d]{0,20}(?:maior|mais)')
        return decisao(*r) if r else None
    if numero == 44:
        # A pergunta também solicita quantidades por turno; só a predominância não basta.
        if not all(tem(n) for n in (42131013, 3240654, 646713)):
            return decisao(False, 'Faltam os totais de Diurno, Noturno e EAD solicitados na questão.')
        return decisao(True, 'Três totais corretos e Diurno como predominante.') if (
            re.search(r'diurno.{0,100}(?:maioria|concentra|predomina|maior)|(?:maioria|concentra|predomina|maior).{0,100}diurno', t)
            and not re.search(r'(?:noturno|ead).{0,40}(?:concentra|maioria|predomina)', t)) else None
    if numero == 25:
        r = _decidir_comparativa(resposta, {
            'indigena': (('terra indigena', 'indigena', 'indigenas'), {Decimal(280634)}),
            'quilombola': (('comunidade quilombola', 'quilombola', 'quilombolas'), {Decimal(288673)})},
            certa=r'quilombola[^.;\n\d]{0,80}(?:mais|maior|concentra|superior)',
            errada=r'indigena[^.;\n\d]{0,80}(?:concentra|tem|apresenta|possui)\s+(?:o\s+)?(?:maior|mais)',
            exige_totais=True)
        return decisao(*r) if r else None
    if numero == 26:
        r = _decidir_comparativa(resposta, {
            'infantil': (('educacao infantil', 'infantil'), {Decimal(9286182)}),
            'fundamental': (('ensino fundamental', 'fundamental'), {Decimal(25806767)}),
            'medio': (('ensino medio', 'medio'), {Decimal(7370879)}),
            'profissional': (('educacao profissional', 'profissional'), {Decimal(3187976)}),
            'eja': (('eja',), {Decimal(2252069)})},
            certa=r'fundamental[^.;\n\d]{0,80}(?:maior|mais|concentra)|(?:maior|mais|concentra)[^.;\n\d]{0,80}fundamental',
            errada=r'(?:infantil|medio|profissional|eja)[^.;\n\d]{0,60}(?:concentra|tem|possui)\s+(?:o\s+)?(?:maior|mais)|(?:maior|mais)[^.]{0,60}\b(?:e|sao)\s+(?:a|o)?\s*(?:educacao infantil|ensino medio|educacao profissional|eja)\b',
            exige_totais=True)
        return decisao(*r) if r else None
    if numero == 27:
        r = _decidir_comparativa(resposta, {
            'creche': (('creche',), {Decimal(4182646)}),
            'pre': (('pre-escola', 'pre escola', 'preescola'), {Decimal(5103536)})},
            certa=r'pre-?\s?escola[^.;\n\d]{0,80}(?:mais|maior)',
            errada=r'creche[^.;\n\d]{0,60}(?:tem|possui|apresenta|e a etapa)[^.;\n\d]{0,30}(?:mais|maior)')
        return decisao(*r) if r else None
    if numero == 29:
        # O enunciado exige a tabela de TODOS os nove anos e a conclusão.
        valores = (2890337, 2874392, 2850775, 2984869, 2913871,
                   2919014, 2870115, 2840218, 2663176)
        linhas = [linha for linha in resposta.splitlines()
                  if re.search(r'\b(?:[1-9])\s*[ºo°]?\s*ano\b', _normalizar(linha))]
        # Cada ano deve aparecer com seu valor na mesma linha; outras
        # representações são ambíguas e seguem para a revisão semântica.
        encontrados = {}
        for linha in linhas:
            m = re.search(r'\b([1-9])\s*[ºo°]?\s*ano\b', _normalizar(linha))
            if m:
                ano = int(m.group(1))
                if not _valores_decimais(linha):
                    continue  # frase de conclusão ("O 4º ano é o maior") não é linha da tabela
                encontrados[ano] = encontrados.get(ano, False) or _numero_exato(linha, valores[ano - 1])
                if not encontrados[ano]:
                    return decisao(False, f'Valor incorreto para o {ano}º ano.')
        if len(encontrados) == 9 and all(encontrados.values()):
            if re.search(r'(?:4|quarto)\s*[ºo°]?\s*ano', t) and tem(2984869):
                return decisao(True, 'Tabela dos nove anos com totais corretos e 4º ano predominante.')
        if re.search(r'\b(?:20(?:19|25)|460183780)\b', t) and not linhas:
            return decisao(False, 'Confundiu ano letivo com ano/série escolar.')
        if not _valores_decimais(resposta) or _RECUSA.search(t):
            return decisao(False, 'O enunciado pede a tabela de matrículas por ano; a resposta não a apresenta.')
        return None
    if numero == 32:
        r = _decidir_comparativa(resposta, {
            'concomitante': (('concomitante',), {Decimal(348446)}),
            'subsequente': (('subsequente',), {Decimal(832032)})})
        if r is None or not r[0]:
            return decisao(*r) if r else None
        # Não basta apresentar os números: o enunciado pede a diferença
        # conceitual entre as duas formas de oferta.
        simultaneo = bool(re.search(r'simultane|ao mesmo tempo|durante o ensino medio|junto (?:ao|com) o ensino medio', t))
        posterior = bool(re.search(r'apos|depois|posterior|conclu(?:sao|ido) do ensino medio', t))
        if simultaneo and posterior:
            return decisao(True, 'Totais e diferença conceitual corretos.')
        return None
    if numero == 34:
        r = _decidir_comparativa(resposta, {
            'fundamental': (('eja fundamental', 'fundamental'), {Decimal(1406442)}),
            'medio': (('eja medio', 'medio'), {Decimal(845627)})},
            certa=r'fundamental[^.;\n\d]{0,80}(?:mais|maior|concentra)|(?:mais|maior|concentra)[^.;\n\d]{0,80}fundamental',
            errada=r'medio[^.;\n\d]{0,60}(?:concentra|tem|possui)\s+(?:o\s+)?(?:mais|maior)',
            basta_conclusao=True)
        return decisao(*r) if r else None
    if numero == 37:
        r = _decidir_comparativa(resposta, {
            'feminino': (('feminin[oa]s?', 'mulheres', 'meninas'), _aceitos('49.4')),
            'masculino': (('masculin[oa]s?', 'homens', 'meninos'), _aceitos('50.6'))},
            percentuais=True,
            exige_totais=True)
        return decisao(*r) if r else None
    if numero == 38:
        soma = _numero_exato(resposta, 23149061)
        percentual = (_numero_exato(resposta, '58.25') or
                      _numero_exato(resposta, '58.3'))
        if soma and percentual:
            return decisao(True, 'Soma de 23.149.061 e percentual de 58,25% corretos.')
        # Respostas que apresentam um percentual explicitamente incompatível
        # ou um número isolado errado são erros objetivos.
        valores = _valores_decimais(resposta)
        if re.fullmatch(r'\s*\d+(?:[.,]\d+)?\s*%?\s*', resposta) and not percentual:
            return decisao(False, 'Percentual informado é diferente de 58,25%.')
        if re.search(r'\d[\d.,]*\s*%', resposta) and not percentual:
            return decisao(False, 'Percentual informado é diferente de 58,25%.')
        if percentual and not soma:
            return decisao(False, 'Informou o percentual, mas omitiu a soma exigida.')
        return None
    if numero == 45:
        r = _decidir_comparativa(resposta, {
            'matutino': (('matutino',), {Decimal(24171117)}),
            'vespertino': (('vespertino',), {Decimal(17959896)})},
            certa=r'matutino[^.;\n\d]{0,80}(?:mais|maior|numeroso|concentra)',
            errada=r'vespertino[^.;\n\d]{0,80}(?:e\s+)?(?:mais|maior|numeroso)',
            basta_conclusao=True)
        return decisao(*r) if r else None
    if numero == 48:
        r = _decidir_comparativa(resposta, {
            'comuns': (('classes comuns', 'classe comum', 'comuns'), {Decimal(2298005)}),
            'exclusivas': (('classes exclusivas', 'classe exclusiva', 'exclusivas'), {Decimal(160154)})},
            certa=r'comuns[^.;\n\d]{0,80}(?:predomin|maior|mais|maioria)|(?:predomin|maioria)[^.;\n\d]{0,60}comuns',
            errada=r'exclusivas[^.;\n\d]{0,80}(?:predomin|maioria)')
        if r is None or not r[0]:
            return decisao(*r) if r else None
        if re.search(r'inclus(?:ao|iva|ivo)|turmas regulares|ensino regular', t):
            return decisao(True, 'Totais, predomínio e relação com a inclusão escolar.')
        return None
    if numero == 50:
        # Duas dimensões diferentes: residência do aluno e localização da escola.
        # Uma conclusão isolada ("sim, é possível") não resolve a pergunta.
        numeros = (38397441, 7618155, 40871166, 5147214)
        presentes = [_numero_exato(resposta, n) for n in numeros]
        if not any(presentes):
            if _RECUSA.search(t) or len(_valores_decimais(resposta)) == 0:
                return decisao(False, 'Não apresentou as somas nem a comparação pedidas.')
            return None
        if not all(presentes):
            return None
        tem_residencia = bool(re.search(r'residenc|morad|residem|resident', t))
        tem_escola = bool(re.search(r'localizac|escolas? (?:urban|rura)|tp_localizacao', t))
        tem_justificativa = bool(re.search(r'transporte escolar|deslocam|deslocamento|estudam em escolas urbanas|matriculad[oa]s? em escolas urbanas', t))
        if tem_residencia and tem_escola and tem_justificativa:
            return None  # associação de 4 números e justificativa exige conferência semântica
        return None
    # Questões com resultado numérico inequívoco, além das 01–23.
    if numero == 24:
        return decisao(tem(2512355) and ('sao paulo' in t or re.search(r'\bsp\b', t)),
                       'Município São Paulo/SP e total 2.512.355.')
    if numero == 31:
        return decisao(tem(2490145) and _numero_exato(resposta, '78.1'),
                       'Total técnico e percentual sobre Educação Profissional.')
    if numero == 33:
        return decisao(tem(2252069) and _numero_exato(resposta, '4.89'),
                       'Total EJA e percentual correto.')
    if numero == 35:
        return decisao(tem(3637), 'Total nacional de matrículas em classes bilíngues de surdos.')
    if numero == 40:
        return decisao(tem(6275577) and ('nao declarad' in t),
                       'Total de não declaradas e identificação da categoria.')
    if numero == 42:
        return decisao(tem(3974803) and ('eja' in t or 'profissional' in t),
                       'Total de 18+ e modalidade associada.')
    if numero == 46:
        return decisao(tem(10143262) and _numero_exato(resposta, '22.04'),
                       'Total em tempo integral e percentual.')
    if numero == 47:
        return decisao(tem(2458159) and _numero_exato(resposta, '5.34'),
                       'Total Educação Especial e percentual.')
    if numero == 49:
        return decisao(all(tem(x) for x in (9078809, 1431234, 7647575)) and 'municipal' in t,
                       'Totais de transporte escolar e predomínio municipal.')
    return None

def avaliar_censo(questao, resposta, consultar_ollama=None):
    """Avalia com rubricas e juiz; indecisão requer revisão, não falha de geração."""
    gabarito = str(questao.get('resposta_esperada') or questao.get('gabarito') or '').strip()
    enunciado = str(questao.get('pergunta') or questao.get('enunciado') or '').strip()
    resposta = str(resposta or '').strip()
    if resposta.startswith(('{', '[')) or re.search(r'(?im)^\s*(?:FERRAMENTA|ASSISTENTE|DICIONARIO)\s*:|```sql', resposta):
        return {'acertou': False, 'motivo': 'Saída bruta de ferramenta não constitui resposta final.',
                'revisao_necessaria': False, 'metodo_avaliacao': 'formato_invalido_censo'}
    if not resposta:
        return {'acertou': False, 'motivo': 'Modelo não forneceu resposta.',
                'revisao_necessaria': False, 'metodo_avaliacao': 'resposta_vazia'}
    if not gabarito:
        return {'acertou': False, 'motivo': 'Gabarito ausente; avaliação conservadora como erro.',
                'revisao_necessaria': False, 'metodo_avaliacao': 'gabarito_ausente'}

    # Primeiro aplica critérios verificáveis para as questões cobertas por rubricas.
    resultado = _criterios_censo(questao, resposta)
    # Rubricas objetivas prevalecem sobre o avaliador LLM.
    # Um erro objetivo não pode ser transformado em acerto pelo juiz semântico.
    if resultado is not None:
        return resultado

    # Para as demais questões (e rubricas negativas), usa avaliação semântica.
    if consultar_ollama is None:
        return {'acertou': None, 'motivo': 'Sem avaliador: revisão humana necessária.',
                'revisao_necessaria': True, 'metodo_avaliacao': 'avaliador_indisponivel'}
    prompt = f"""Você corrige respostas do Censo Escolar. Julgue APENAS a resposta dada,
comparando-a com a questão e o gabarito. Não avalie a intenção nem a qualidade
aparente do código: se o valor pedido não foi efetivamente respondido, está errado.
Avalie TODOS os requisitos expressos no enunciado: valores, tabelas, comparações
e explicações quando solicitadas. Não exija cálculo ou tabela quando não pedidos.
Valores numéricos afirmados como resultados devem estar corretos, mesmo se opcionais.
Listas podem vir em qualquer ordem, exceto quando a pergunta exigir uma ordem.
Resultado objetivamente ausente ou incorreto é INCORRETA. Se houver ambiguidade
semântica genuína, use INCERTO e encaminhe para revisão humana.
Responda com JSON válido, sem markdown, neste formato:
{{"veredito":"CORRETA","justificativa":"motivo breve"}}

QUESTÃO: {enunciado}
GABARITO: {gabarito}
RESPOSTA: {resposta}"""
    # Até três julgamentos quando o avaliador responde JSON inválido.
    # Cada chamada também tem os retries de conexão definidos em utils.py.
    ultimo_motivo = 'Avaliador inconclusivo.'
    for tentativa_avaliador in range(1, 4):
        try:
            info_avaliador = consultar_ollama(
                prompt, temperature=0, num_predict=120, retornar_metricas=True,
            )
            if not isinstance(info_avaliador, dict):
                info_avaliador = {'resposta': None, 'tentativas': 3,
                                  'erro_detalhado': 'Avaliador sem metadados.'}
            julgamento = _extrair_json(info_avaliador.get('resposta'))
        except Exception as erro:
            julgamento = None
            ultimo_motivo = f'Falha no avaliador: {erro}'
        else:
            ultimo_motivo = (info_avaliador.get('erro_detalhado')
                             or 'O avaliador não retornou JSON válido.')
        if isinstance(julgamento, dict):
            veredito = str(julgamento.get('veredito', '')).upper().strip()
            justificativa = str(julgamento.get('justificativa', '')).strip()
            if veredito in ('CORRETA', 'INCORRETA') and justificativa:
                return {'acertou': None, 'motivo': f'Parecer do juiz: {veredito}. {justificativa}',
                        'revisao_necessaria': True,
                        'metodo_avaliacao': 'llm_triagem_revisao_humana',
                        'parecer_llm': veredito,
                        'tentativas_avaliador': tentativa_avaliador}
            ultimo_motivo = justificativa or 'Veredito inconclusivo.'
    return {'acertou': None, 'motivo': ultimo_motivo + ' Revisão humana necessária.',
            'revisao_necessaria': True,
            'metodo_avaliacao': 'avaliador_inconclusivo',
            'tentativas_avaliador': 3}

