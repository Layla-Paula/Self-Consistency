"""Avaliacao compartilhada do Censo"""

import re
import json
import unicodedata

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
        return decisao(tem(178766), 'Verificação do total de escolas.')
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
        return decisao(tem(137020) and tem(41746), 'Contagens das redes pública e privada.')
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
        return decisao(tem(128037) and tem(50729), 'Contagens de escolas urbanas e rurais.')
    if numero == 18:
        return decisao(tem(40871166) and tem(5147214), 'Totais de matrículas urbanas e rurais.')
    if numero == 19:
        return decisao('319' in t and '101' in t and 'urbana' in t and 'rural' in t and '270' not in t,
                       'Médias urbana e rural corretas, sem valor urbano contraditório.')
    if numero == 20:
        return decisao(all(x in t for x in ('24,42', '21,34', '5,90', '5,77', '3,30')) and 'norte' in t,
                       'Percentuais das cinco regiões e identificação da maior.')
    # Questões que pedem listas de UFs: compara cada sigla com seu valor, sem exigir ordem.
    # Não avalia explicações adicionais, apenas os cinco resultados solicitados.
    if numero in (22, 23):
        esperados = ({'SP': 9600318, 'MG': 4220829, 'BA': 3345058,
                      'RJ': 3319771, 'PR': 2438428} if numero == 22 else
                     {'RR': 186395, 'AP': 212026, 'AC': 242727,
                      'RO': 376264, 'TO': 380768})
        nomes = {'SP': 'sao paulo', 'MG': 'minas gerais', 'BA': 'bahia',
                 'RJ': 'rio de janeiro', 'PR': 'parana', 'RR': 'roraima',
                 'AP': 'amapa', 'AC': 'acre', 'RO': 'rondonia', 'TO': 'tocantins'}
        # Exige que cada valor esteja associado à UF correspondente.
        linhas = re.split(r'\n|;', resposta)
        def par_presente(sigla, valor):
            for linha in linhas:
                uf = (re.search(r'(?<![A-Za-z])' + sigla + r'(?![A-Za-z])', linha, re.I)
                      or nomes[sigla] in _normalizar(linha))
                if uf and _tem_valor(linha, valor):
                    return True
            return False
        ok = all(par_presente(sigla, valor) for sigla, valor in esperados.items())
        return decisao(ok, 'Conferência dos cinco pares UF e total de matrículas, independentemente da ordem.')
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
    # Se a rubrica rejeitar, consulte o avaliador semântico para evitar
    # falsos negativos causados por formatação, sinônimos ou ordem da resposta.
    # Rubricas exatas e verificaveis nao podem ser anuladas por um juiz LLM.
    # Evita falso positivo como "zero escolas" para o total 178766.
    id_num = str(questao.get('id', '')).rsplit('_', 1)[-1]
    if resultado is not None and (resultado['acertou'] or id_num in ('01', '02', '17', '18', '22', '23')):
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
{{"veredito":"CORRETA","justificativa":"motivo específico"}}

QUESTÃO: {enunciado}
GABARITO: {gabarito}
RESPOSTA: {resposta}"""
    # Até três julgamentos quando o avaliador responde JSON inválido.
    # Cada chamada também tem os retries de conexão definidos em utils.py.
    ultimo_motivo = 'Avaliador inconclusivo.'
    for tentativa_avaliador in range(1, 4):
        try:
            info_avaliador = consultar_ollama(
                prompt, temperature=0, num_predict=220, retornar_metricas=True,
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

