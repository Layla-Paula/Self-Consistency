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
    return valor in _numeros(texto)

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
        # A pergunta exige a quantidade e a lista completa das 27 UFs.
        siglas = ('AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO',
                  'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI',
                  'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO')
        lista_completa = all(re.search(r'(?<![A-Za-z])' + uf + r'(?![A-Za-z])',
                                       resposta, re.I) for uf in siglas)
        return decisao(bool(re.search(r'(?<!\d)27(?!\d)', t)) and lista_completa,
                       'Deve informar 27 e listar todas as 27 siglas das UFs.')
    if numero == 5:
        return decisao(tem(5571) and not ('uf' in t and 'value_counts' in t),
                       'Deve identificar 5.571 municípios distintos; contar UFs não resolve.')
    if numero == 6:
        return decisao('nu_ano_censo' in t and '2025' in t and ('ano' in t or 'referencia' in t),
                       'Variável, significado e ano de referência.')
    if numero == 7:
        afirmacao = re.search(r'\b(sim|existe|existem|ha)\b.{0,75}(escola|qt_mat_bas)', t)
        negativa = bool(re.search(r'\b(nao existe|nao ha|nenhuma escola|zero ocorrencias|0 ocorrencias)\b', t))
        return decisao(negativa and not afirmacao, 'Não há escolas com QT_MAT_BAS igual a zero; afirmação positiva contradiz o gabarito.')
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
        ok = all(x in t for x in ('federal', 'estadual', 'municipal', 'privada')) and all(x in t for x in ('535', '448', '216', '221'))
        return decisao(ok, 'Médias por todas as quatro dependências e identificação da maior.')
    if numero == 13:
        return decisao('municipal' in t and 'estadual' in t and '216' in t and '448' in t and
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
        return decisao('parceria' in t and 'poder publico' in t and ('financiamento' in t or 'convenio' in t),
                       'Interpretação da parceria com o poder público.')
    if numero == 17:
        return decisao(_par_numero(resposta, ('urbana', 'urbanas'), 128037) and _par_numero(resposta, ('rural', 'rurais'), 50729) and not _contradicao_soma(resposta, (128037, 50729)), 'Exige os dois totais por localização, sem apresentar somas contraditórias como totais.')
    if numero == 18:
        return decisao(_par_numero(resposta, ('urbana', 'urbanas'), 40871166) and _par_numero(resposta, ('rural', 'rurais'), 5147214) and not re.search(r'\b(iguais|mesmo total|mesma quantidade)\b', t), 'Totais corretos de matrículas urbanas e rurais, sem afirmar igualdade.')
    if numero == 19:
        return decisao('319' in t and '101' in t and 'urbana' in t and 'rural' in t and '270' not in t,
                       'Médias urbana e rural corretas, sem valor urbano contraditório.')
    if numero == 20:
        return decisao(all(x in t for x in ('24,42', '21,34', '5,90', '5,77', '3,30')) and 'norte' in t,
                       'Percentuais das cinco regiões e identificação da maior.')
    # As questões 22 e 23 pedem QUAIS UFs, não os valores por UF.
    # Não exigir os números evita falsos negativos de respostas corretas.
    if numero in (22, 23):
        esperadas = ({'SP', 'MG', 'BA', 'RJ', 'PR'} if numero == 22 else
                     {'RR', 'AP', 'AC', 'RO', 'TO'})
        citadas = _ufs_citadas(resposta)
        return decisao(citadas == esperadas,
                       'Comparação exata do conjunto das cinco UFs; ordem e valores não exigidos.')
    # Questões com resultado numérico inequívoco, além das 01–23.
    if numero == 24:
        return decisao(tem(2512355) and ('sao paulo' in t or re.search(r'\bsp\b', t)),
                       'Município São Paulo/SP e total 2.512.355.')
    if numero == 31:
        return decisao(tem(2490145) and ('78,1' in t or '78.1' in t),
                       'Total técnico e percentual sobre Educação Profissional.')
    if numero == 33:
        return decisao(tem(2252069) and ('4,89' in t or '4.89' in t),
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
        return decisao(tem(10143262) and ('22,04' in t or '22.04' in t),
                       'Total em tempo integral e percentual.')
    if numero == 47:
        return decisao(tem(2458159) and ('5,34' in t or '5.34' in t),
                       'Total Educação Especial e percentual.')
    if numero == 49:
        return decisao(all(tem(x) for x in (9078809, 1431234, 7647575)) and 'municipal' in t,
                       'Totais de transporte escolar e predomínio municipal.')
    return None

def avaliar_censo(questao, resposta, consultar_ollama=None):
    """Avalia automaticamente em acerto/erro; sem revisão manual."""
    gabarito = str(questao.get('resposta_esperada') or questao.get('gabarito') or '').strip()
    enunciado = str(questao.get('pergunta') or questao.get('enunciado') or '').strip()
    resposta = str(resposta or '').strip()
    if not resposta:
        return {'acertou': False, 'motivo': 'Modelo não forneceu resposta.',
                'revisao_necessaria': False, 'metodo_avaliacao': 'resposta_vazia'}
    if not gabarito:
        return {'acertou': None, 'motivo': 'Gabarito ausente; não foi possível confirmar acerto.',
                'revisao_necessaria': False, 'metodo_avaliacao': 'gabarito_ausente'}

    # Primeiro aplica critérios verificáveis para as questões cobertas por rubricas.
    resultado = _criterios_censo(questao, resposta)
    # Rubricas objetivas prevalecem sobre o avaliador LLM.
    # Um erro objetivo não pode ser transformado em acerto pelo juiz semântico.
    if resultado is not None:
        return resultado

    # Para as demais questões (e rubricas negativas), usa avaliação semântica.
    if consultar_ollama is None:
        return {'acertou': None, 'motivo': 'Sem avaliador para confirmar a resposta.',
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
    return {'acertou': None, 'motivo': ultimo_motivo,
            'revisao_necessaria': False,
            'metodo_avaliacao': 'avaliador_inconclusivo',
            'tentativas_avaliador': 3}

