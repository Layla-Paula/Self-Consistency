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

_PADRAO_VALOR = re.compile(r"(?<![\w])[-+]?\d{1,3}(?:\.\d{3})+(?:,\d+)?(?![\w.,])|(?<![\w])[-+]?\d+(?:[.,]\d+)?(?![\w.,])")

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

    if numero == 1:
        return decisao(tem(178766) and not re.search(r'(?<!\d)0\s+escolas\b', t), 'Total correto de escolas, sem afirmação contraditória.')
    if numero == 2:
        return decisao(tem(46018380), 'Verificação do total de matrículas, não apenas do código proposto.')
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
        return decisao(negativa and not afirmacao, 'Não há escolas com QT_MAT_BAS igual a zero.')
    if numero == 8:
        correta = ('co_rede' in t and 'tp_dependencia' in t and
                   ('publica' in t and 'privada' in t) and
                   ('federal' in t and 'estadual' in t and 'municipal' in t))
        bloco = re.search(r'co_rede.{0,180}(?:tp_dependencia|ja a variavel)', t, flags=re.S)
        erro_rede = bool(bloco and all(x in bloco.group() for x in ('federal', 'estadual', 'municipal', 'privada')))
        return decisao(correta and not erro_rede and ('duas' in t or '2 categoria' in t or 'publica e privada' in t),
                       'CO_REDE agrupa pública/privada; TP_DEPENDENCIA possui quatro categorias.')
    if numero == 9:
        return decisao(tem(137020) and tem(41746) and 'publica' in t and 'privada' in t, 'Contagens das redes pública e privada.')
    if numero == 10:
        return decisao(all(tem(v) for v in (383526, 13330302, 23059168, 9245384)) and 'municipal' in t,
                       'Quatro totais de matrículas por dependência e predominância municipal.')
    if numero == 11:
        return decisao('federal' in t and tem(716) and tem(383526),
                       'Menor dependência é federal, com 716 escolas e 383.526 matrículas.')
    if numero == 12:
        ok = all(x in t for x in ('federal', 'estadual', 'municipal', 'privada')) and all(tem(x) for x in (535, 448, 216, 221))
        return decisao(ok, 'Médias por todas as quatro dependências e identificação da maior.')
    if numero == 13:
        return decisao('municipal' in t and 'estadual' in t and tem(216) and tem(448) and
                       ('metade' in t or 'dobro' in t or 'menor' in t),
                       'Comparação efetiva entre as médias municipal e estadual.')
    if numero == 14:
        return decisao('tp_categoria_escola_privada' in t and all(x in t for x in
                       ('particular', 'comunitaria', 'confessional', 'filantropica')),
                       'Variável e as quatro categorias privadas.')
    if numero == 15:
        return decisao(tem(7085034) and tem(1711268) and 'particular' in t and 'filantropica' in t and
                       ('maior' in t or 'mais matriculas' in t or 'superior' in t or 'concentra' in t),
                       'Matrículas particular e filantrópica e comparação conclusiva entre ambas.')
    if numero == 16:
        return decisao('parceria' in t and ('poder publico' in t or 'administracao publica' in t) and ('financiamento' in t or 'convenio' in t or 'itinerario' in t),
                       'Interpretação da parceria com o poder público.')
    if numero == 17:
        return decisao(_par_numero(resposta, ('urbana', 'urbanas'), 128037) and _par_numero(resposta, ('rural', 'rurais'), 50729) and not _contradicao_soma(resposta, (128037, 50729)), 'Exige os dois totais por localização, sem apresentar somas contraditórias como totais.')
    if numero == 18:
        return decisao(_par_numero(resposta, ('urbana', 'urbanas'), 40871166) and _par_numero(resposta, ('rural', 'rurais'), 5147214) and not re.search(r'\b(iguais|mesmo total|mesma quantidade)\b', t), 'Totais corretos de matrículas urbanas e rurais, sem afirmar igualdade.')
    if numero == 19:
        return decisao(tem(319) and tem(101) and 'urbana' in t and 'rural' in t and not tem(270),
                       'Médias urbana e rural corretas, sem valor urbano contraditório.')
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
        # Para as demais respostas, exigir validação semântica, pois podem citar só a tendência.
        return None
    if numero == 41:
        # A associacao das faixas etarias as etapas pode aparecer em periodos
        # diferentes; janelas de caracteres cruzam afirmacoes corretas.
        # Deixar a avaliacao semantica decidir sem falso negativo automatico.
        return None
    if numero == 43:
        # Não aceitar separadores numéricos malformados como se fossem totais corretos.
        if re.search(r'(?<!\d)496\.8651(?!\d)', t):
            return decisao(False, 'Total de 4 a 5 anos foi escrito incorretamente: 496.8651.')
        return None
    if numero == 44:
        # A pergunta também solicita quantidades por turno; só a predominância não basta.
        if not all(tem(n) for n in (42131013, 3240654, 646713)):
            return decisao(False, 'Faltam os totais de Diurno, Noturno e EAD solicitados na questão.')
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
        return {'acertou': False, 'motivo': 'Sem avaliador: resposta não confirmada, contada como erro.',
                'revisao_necessaria': False, 'metodo_avaliacao': 'avaliador_indisponivel'}
    prompt = f"""Você corrige respostas do Censo Escolar. Julgue APENAS a resposta dada,
comparando-a com a questão e o gabarito. Não avalie a intenção nem a qualidade
aparente do código: se o valor pedido não foi efetivamente respondido, está errado.
Avalie o RESULTADO solicitado, não a explicação ou o procedimento.
Se o resultado solicitado estiver correto, marque CORRETA mesmo com explicação ruim.
Listas podem vir em qualquer ordem, exceto quando a pergunta exigir uma ordem.
Resultado ausente, ambíguo ou incorreto é INCORRETA. Nunca use INCERTO.
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
                return {'acertou': veredito == 'CORRETA', 'motivo': justificativa,
                        'revisao_necessaria': False,
                        'metodo_avaliacao': 'llm_como_avaliador',
                        'tentativas_avaliador': tentativa_avaliador}
            ultimo_motivo = justificativa or 'Veredito inconclusivo.'
    return {'acertou': False, 'motivo': ultimo_motivo + ' Contada como erro por ausência de confirmação.',
            'revisao_necessaria': False,
            'metodo_avaliacao': 'avaliador_inconclusivo',
            'tentativas_avaliador': 3}


# ============================================================
# REAVALIAÇÃO OFFLINE - SELF-CONSISTENCY NO CENSO
# ============================================================
# Refaz a votação e a avaliação a partir das amostras JÁ SALVAS no JSON.
# Não gera texto novo do modelo: só usa o juiz (Ollama) nas questões sem rubrica.
# Nunca altera o arquivo original: grava ao lado, com final ".reavaliado.json".

def reavaliar_self_consistency_censo(caminho, usar_juiz=True, registros_censo=None):
    from pathlib import Path
    from codigo.self_consistency.votacao import voto_censo_semantico

    caminho = Path(caminho)
    original = json.loads(caminho.read_text(encoding='utf-8'))
    if original.get('tecnica') != 'self_consistency' or original.get('dataset') != 'censo':
        raise ValueError('O arquivo precisa ser de self_consistency no censo.')

    consultar = None
    if usar_juiz:
        from codigo.utils import consultar_ollama as consultar
    if registros_censo is None:
        from codigo.utils import carregar_censo
        registros_censo = carregar_censo()
    perguntas = {str(q.get('id')): q for q in registros_censo}

    dados = json.loads(json.dumps(original))  # cópia profunda
    resultados = dados['resultados']
    alteracoes = []

    for r in resultados:
        if r.get('falha_tecnica'):
            continue
        antes = {'resposta': r.get('resposta'), 'acertou': r.get('acertou')}
        respostas = []
        for a in r.get('amostras', []):
            # O agente já devolve só o texto depois de "Resposta final:".
            texto = '' if a.get('falha_tecnica') else str(a.get('resposta_completa') or '').strip()
            a['resposta_extraida'] = texto
            a['resposta_valida'] = bool(texto)
            a['sem_extracao'] = (not texto) and (not a.get('falha_tecnica'))
            respostas.append(texto)

        questao = dict(perguntas.get(str(r['id']), {}))
        questao.setdefault('id', r['id'])
        questao['resposta_esperada'] = r.get('gabarito') or questao.get('resposta_esperada', '')
        pergunta = str(questao.get('pergunta') or questao.get('enunciado') or '')

        votacao = voto_censo_semantico(pergunta, respostas, None)
        r.update(
            respostas_extraidas=respostas,
            distribuicao_votos=votacao['distribuicao'],
            resposta_modelo=votacao['vencedora'],
            resposta=votacao['vencedora'],
            resposta_valida=bool(votacao['vencedora']),
            votos_resposta_modelo=votacao['votos'],
            houve_empate=votacao['houve_empate'],
            total_respostas_validas=votacao['total_respostas_validas'],
            metodo_votacao=votacao.get('metodo_votacao'),
            amostras_sem_extracao=sum(a['sem_extracao'] for a in r.get('amostras', [])),
        )

        if not votacao['vencedora']:
            r.update(acertou=False, motivo='Nenhuma resposta final válida nas amostras.',
                     metodo_avaliacao='votacao_sem_vencedor', revisao_necessaria=False,
                     tipo_resultado='sem_vencedor')
        else:
            av = avaliar_censo(questao, votacao['vencedora'], consultar)
            pendente = av.get('metodo_avaliacao') == 'avaliador_indisponivel'
            r.update(acertou=None if pendente else bool(av['acertou']),
                     motivo=av.get('motivo'), metodo_avaliacao=av.get('metodo_avaliacao'),
                     revisao_necessaria=bool(av.get('revisao_necessaria')) or pendente,
                     tipo_resultado=('pendente' if pendente else
                                     'acerto' if av['acertou'] else 'vencedora_incorreta'))
        if antes != {'resposta': r.get('resposta'), 'acertou': r.get('acertou')}:
            alteracoes.append({'id': r['id'], 'antes': antes,
                               'depois': {'resposta': r.get('resposta'), 'acertou': r.get('acertou')}})

    avaliadas = [r for r in resultados if not r.get('falha_tecnica') and isinstance(r.get('acertou'), bool)]
    pendentes = [r for r in resultados if not r.get('falha_tecnica') and r.get('acertou') is None]
    acertos = sum(r['acertou'] for r in avaliadas)
    amostras = [a for r in resultados for a in r.get('amostras', [])]
    m = dados['metricas']
    dados['metricas_originais'] = original.get('metricas', {})
    m.update(
        questoes_avaliadas=len(avaliadas), acertos=acertos, erros=len(avaliadas) - acertos,
        avaliacoes_pendentes=len(pendentes),
        acuracia_percentual=round(100 * acertos / len(avaliadas), 2) if avaliadas else None,
        amostras_sem_extracao=sum(a.get('sem_extracao', False) for a in amostras),
        questoes_sem_vencedor=sum(not r.get('resposta_modelo') for r in avaliadas),
        questoes_maioria_incorreta=sum(bool(r.get('resposta_modelo')) and not r['acertou'] for r in avaliadas),
        questoes_empate=sum(bool(r.get('houve_empate')) for r in avaliadas),
        ids_questoes_sem_vencedor=[r['id'] for r in avaliadas if not r.get('resposta_modelo')],
        ids_questoes_maioria_incorreta=[r['id'] for r in avaliadas
                                        if r.get('resposta_modelo') and not r['acertou']],
        revisoes_necessarias=sum(bool(r.get('revisao_necessaria')) for r in resultados),
    )
    dados['reavaliacao'] = {
        'tipo': 'offline_a_partir_das_amostras_salvas',
        'motivo': 'Correção do extrator de resposta final do Censo no Self-Consistency.',
        'usou_juiz_llm': bool(usar_juiz),
        'arquivo_origem': str(caminho),
        'questoes_alteradas': len(alteracoes),
    }
    destino = caminho.with_name(caminho.stem + '.reavaliado.json')
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"{caminho.name}: {acertos}/{len(avaliadas)} = {m['acuracia_percentual']}% "
          f"| pendentes: {len(pendentes)} | sem vencedora: {m['questoes_sem_vencedor']}")
    print(f'Salvo em: {destino}')
    return destino


if __name__ == '__main__':
    import sys
    argumentos = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(argumentos) != 1:
        raise SystemExit('Uso: python -m codigo.avaliacao.avaliacao_censo ARQUIVO.json [--sem-juiz]')
    reavaliar_self_consistency_censo(argumentos[0], usar_juiz='--sem-juiz' not in sys.argv)