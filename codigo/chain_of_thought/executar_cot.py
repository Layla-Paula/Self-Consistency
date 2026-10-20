"""Execução Chain-of-Thought: GSM8K, AQuA-RAT e Censo Escolar.

"""
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path

from tqdm import tqdm
import re
import unicodedata
from codigo.utils import (
    carregar_gsm8k, carregar_aqua_rat, carregar_censo, consultar_ollama,
    extrair_gabarito_gsm8k, extrair_gabarito_aqua_rat,
    extrair_gabarito_censo, extrair_resposta_numerica,
    extrair_letra_resposta, comparar_numeros,
    montar_questao_gsm8k, montar_questao_aqua_rat,
)
from codigo.chain_of_thought.prompts import (
    prompt_cot_gsm8k, prompt_cot_aqua_rat, prompt_cot_censo,
)

try:
    import psutil
except ImportError:
    psutil = None

MODELO = "llama3.2"
TEMPERATURE = 0.0
NUM_PREDICT = 800
N_EXEMPLOS = {"gsm8k": 10, "aqua_rat": 10, "censo": 5}
SALVAR_CADA = 10
PASTA_BASE = Path("resultados/chain_of_thought")

# Faixas temáticas das 50 questões do Censo (posições no JSON).
# A seleção é automática, determinística e alterna entre os seis blocos.
BLOCOS_CENSO = [(1, 8), (9, 16), (17, 25), (26, 35), (36, 43), (44, 50)]

# Avaliação do Censo incorporada: este arquivo não depende de revisao_censo.py.
def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', str(texto).lower())
    return ''.join(c for c in texto if not unicodedata.combining(c))

def _numeros(texto):
    # Captura milhares brasileiros (178.766) e inteiros sem separador (178766).
    tokens = re.findall(r'(?\<![\w])\d{1,3}(?:\\.\d{3})+(?:,\d+)?|(?\<![\w])\d+(?:[.,]\d+)?', str(texto))
    valores = set()
    for token in tokens:
        if re.fullmatch(r'\d{1,3}(?:\\.\d{3})+', token):
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
        lista_completa = all(re.search(r'(?\<![A-Za-z])' + uf + r'(?![A-Za-z])',
                                       resposta, re.I) for uf in siglas)
        return decisao(bool(re.search(r'(?\<!\d)27(?!\d)', t)) and lista_completa,
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
                uf = (re.search(r'(?\<![A-Za-z])' + sigla + r'(?![A-Za-z])', linha, re.I)
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
        return {'acertou': False, 'motivo': 'Gabarito ausente; não foi possível confirmar acerto.',
                'revisao_necessaria': False, 'metodo_avaliacao': 'gabarito_ausente'}

    # Primeiro aplica critérios verificáveis para as questões cobertas por rubricas.
    resultado = _criterios_censo(questao, resposta)
    # Se a rubrica rejeitar, consulte o avaliador semântico para evitar
    # falsos negativos causados por formatação, sinônimos ou ordem da resposta.
    if resultado is not None and resultado["acertou"]:
        return resultado

    # Para as demais questões (e rubricas negativas), usa avaliação semântica.
    if consultar_ollama is None:
        return {'acertou': False, 'motivo': 'Sem avaliador para confirmar a resposta.',
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
    try:
        texto = consultar_ollama(prompt, temperature=0, num_predict=220)
        julgamento = _extrair_json(texto)
    except Exception as erro:
        julgamento = None
        detalhe = f'Falha no avaliador: {erro}'
    else:
        detalhe = 'O avaliador não retornou JSON válido.'
    if not isinstance(julgamento, dict):
        return {'acertou': None, 'motivo': detalhe, 'revisao_necessaria': False,
                'metodo_avaliacao': 'avaliador_inconclusivo'}
    veredito = str(julgamento.get('veredito', '')).upper().strip()
    justificativa = str(julgamento.get('justificativa', '')).strip()
    if veredito not in ('CORRETA', 'INCORRETA') or not justificativa:
        return {'acertou': None, 'motivo': justificativa or 'Veredito inconclusivo.',
                'revisao_necessaria': False, 'metodo_avaliacao': 'avaliador_inconclusivo'}
    return {'acertou': veredito == 'CORRETA', 'motivo': justificativa,
            'revisao_necessaria': False, 'metodo_avaliacao': 'llm_como_avaliador'}

def ordem_exemplos_censo(registros):
    """Intercala questões de todos os blocos, sem sorteio e sem repetir posições.

    Em cada bloco, prioriza questões próximas ao centro; com mais exemplos,
    preserva todos os exemplos já selecionados com uma quantidade menor.
    """
    blocos = []
    for inicio, fim in BLOCOS_CENSO:
        posicoes = [i for i in range(inicio - 1, min(fim, len(registros)))]
        centro = (inicio + fim - 2) / 2
        posicoes.sort(key=lambda i: (abs(i - centro), i))
        blocos.append(posicoes)

    ordem = []
    for rodada in range(max(map(len, blocos), default=0)):
        for bloco in blocos:
            if rodada < len(bloco):
                ordem.append(bloco[rodada])

    # Se a lista crescer além das 50 questões originais, não omitir novas posições.
    ordem.extend(range(min(50, len(registros)), len(registros)))
    return ordem

def agora():
    return datetime.now().isoformat(timespec="seconds")

def salvar(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)

def selecionar_exemplos(dataset, registros, quantidade):
    if not isinstance(quantidade, int) or isinstance(quantidade, bool) or quantidade < 1:
        raise ValueError("A quantidade de exemplos deve ser um inteiro positivo.")

    if dataset == "censo":
        if quantidade >= len(registros):
            raise ValueError("O Censo precisa ter questões fora das demonstrações.")
        ordem = ordem_exemplos_censo(registros)
        exemplos = [registros[i] for i in ordem[:quantidade]]
        if len(exemplos) != quantidade:
            raise ValueError("Não há exemplos suficientes no Censo.")
        if any(not str(e.get("resposta_esperada") or "").strip() for e in exemplos):
            raise ValueError("Há demonstração do Censo sem resposta_esperada.")
        return exemplos

    exemplos = []
    vistos = set()
    for questao in registros:
        if questao.get("split") != "train":
            continue
        identificador = str(questao.get("id", ""))
        if not identificador or identificador in vistos:
            continue
        try:
            if dataset == "gsm8k":
                montar_questao_gsm8k(questao)
                if not extrair_gabarito_gsm8k(questao):
                    continue
                if not str(questao.get("answer_pt") or questao.get("answer_en") or questao.get("answer") or "").strip():
                    continue
            else:
                montar_questao_aqua_rat(questao)
                extrair_gabarito_aqua_rat(questao)
                if not str(questao.get("rationale_pt") or "").strip():
                    continue
                if questao.get("revisao_necessaria") is True:
                    continue
        except (ValueError, KeyError, TypeError):
            continue
        exemplos.append(questao)
        vistos.add(identificador)
        if len(exemplos) == quantidade:
            break
    if len(exemplos) != quantidade:
        raise ValueError(f"Foram encontrados apenas {len(exemplos)} exemplos válidos.")
    return exemplos

def metricas(resultados, tempo_total, quantidade, dataset):
    """Falhas técnicas não participam da acurácia nem das médias de desempenho."""
    avaliadas = [
        r for r in resultados
        if not r.get("falha_tecnica", False) and isinstance(r.get("acertou"), bool)
    ]
    falhas = [r for r in resultados if r.get("falha_tecnica", False)]
    tempos = [r["tempo_segundos"] for r in avaliadas if isinstance(r.get("tempo_segundos"), (int, float))]
    def acuracia(itens):
        return round(100 * sum(r["acertou"] for r in itens) / len(itens), 2) if itens else None
    def media(chave):
        valores = [r[chave] for r in avaliadas if isinstance(r.get(chave), (int, float))]
        return round(statistics.mean(valores), 2) if valores else None
    def resumo(itens):
        return {
            "questoes": len(itens),
            "acertos": sum(r["acertou"] for r in itens),
            "erros": sum(not r["acertou"] for r in itens),
            "acuracia_percentual": acuracia(itens),
        }
    por_split = {}
    if dataset != "censo":
        for split in ("train", "validation", "test"):
            itens = [r for r in avaliadas if r.get("split") == split]
            if itens:
                por_split[split] = resumo(itens)
    return {
        "exemplos_utilizados": quantidade,
        "questoes_executadas": len(resultados),
        "questoes_avaliadas": len(avaliadas),
        "falhas_tecnicas": len(falhas),
        "questoes_descartadas_por_falha_tecnica": len(falhas),
        "detalhes_falhas_tecnicas": [
            {"id": r["id"], "motivo": r.get("motivo"), "tentativas": r.get("tentativas_consulta")}
            for r in falhas
        ],
        "acertos": sum(r["acertou"] for r in avaliadas),
        "erros": sum(not r["acertou"] for r in avaliadas),
        "acuracia_percentual": acuracia(avaliadas),
        "acuracia_por_split": por_split,
        "respostas_sem_extracao": sum(not r.get("resposta_valida", False) for r in avaliadas),
        "revisoes_necessarias": sum(bool(r.get("revisao_necessaria", False)) for r in avaliadas),
        "tempo_total_segundos": round(tempo_total, 2),
        "tempo_medio_segundos": round(statistics.mean(tempos), 2) if tempos else None,
        "tokens_entrada": sum(r.get("tokens_entrada") or 0 for r in avaliadas),
        "tokens_saida": sum(r.get("tokens_saida") or 0 for r in avaliadas),
        "cpu_media_percentual": media("cpu_percentual"),
        "ram_media_percentual": media("ram_percentual"),
    }

def recursos():
    if psutil is None:
        return {"cpu_percentual": None, "ram_percentual": None}
    return {
        "cpu_percentual": psutil.cpu_percent(interval=None),
        "ram_percentual": psutil.virtual_memory().percent,
    }

def identificador_novo(dataset, limite, quantidade):
    pasta = PASTA_BASE / dataset
    pasta.mkdir(parents=True, exist_ok=True)
    data = datetime.now().strftime("%Y%m%d")
    prefixo = f"chain_of_thought_{dataset}_{data}_q{'todos' if limite is None else limite}_ex{quantidade}_run"
    indice = 1
    while any((pasta / f"{prefixo}{indice:02d}{sufixo}").exists()
              for sufixo in (".json", ".progresso.json")):
        indice += 1
    return f"{prefixo}{indice:02d}"

def tempo_legivel(segundos):
    horas, resto = divmod(round(segundos), 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{horas}h {minutos}min {segundos}s" if horas else f"{minutos}min {segundos}s"

def mostrar_resumo(dataset, dados, caminho):
    m = dados["metricas"]
    acuracia = m["acuracia_percentual"]
    print(f"\n{dataset.upper()} | Chain-of-Thought")
    print(f"Questões executadas: {m['questoes_executadas']}")
    print(f"Questões avaliadas: {m['questoes_avaliadas']}")
    print(f"Exemplos utilizados: {m['exemplos_utilizados']}")
    print(f"Acertos: {m['acertos']}")
    print(f"Erros: {m['erros']}")
    print(f"Falhas técnicas: {m['falhas_tecnicas']}")
    print(f"Acurácia: {acuracia:.2f}%" if acuracia is not None else "Acurácia: indisponível")
    print(f"Tempo de execução: {tempo_legivel(m['tempo_total_segundos'])}")
    print(f"Resultados salvos em: {caminho}")

def executar_dataset(dataset, limite=None, n_exemplos=None, retomar=None):
    carregadores = {
        "gsm8k": carregar_gsm8k,
        "aqua_rat": carregar_aqua_rat,
        "censo": carregar_censo,
    }
    if dataset not in carregadores:
        raise ValueError(f"Dataset desconhecido: {dataset}")
    if limite is not None and (not isinstance(limite, int) or isinstance(limite, bool) or limite < 1):
        raise ValueError("O limite deve ser None ou inteiro positivo.")

    quantidade = N_EXEMPLOS[dataset] if n_exemplos is None else n_exemplos
    registros = carregadores[dataset](split=None)
    ids = [str(q.get("id", "")) for q in registros]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Há IDs ausentes ou duplicados no dataset.")

    exemplos = selecionar_exemplos(dataset, registros, quantidade)
    ids_exemplos = {str(e["id"]) for e in exemplos}

    # Exclui automaticamente as questões utilizadas como exemplos, pelos IDs.
    # Preserva a ordem original e aplica o limite somente após a exclusão.
    questoes_disponiveis = [
        questao for questao in registros
        if str(questao["id"]) not in ids_exemplos
    ]
    questoes = (questoes_disponiveis[:limite]
               if limite is not None else questoes_disponiveis)
    if not questoes:
        raise ValueError("Nenhuma questão disponível para avaliação após excluir os exemplos.")

    sessao = None
    contextos_exemplos = None
    if dataset == "censo":
        try:
            from codigo.consulta_censo import SessaoCenso, verificar_consultas
        except ImportError as erro:
            raise ImportError(
                "O Censo exige SessaoCenso e verificar_consultas em codigo/consulta_censo.py."
            ) from erro
        verificar_consultas(exemplos + questoes)
        sessao = SessaoCenso()
        contextos_exemplos = {str(e["id"]): sessao.consultar(e) for e in exemplos}
        raciocinios_exemplos = {}
        for exemplo in exemplos:
            raciocinio = str(exemplo.get("raciocinio") or "").strip()
            if not raciocinio:
                raise ValueError(
                    f"Censo {exemplo['id']} sem raciocínio. Execute baixar_preparar_censo.py "
                    "para gerar o JSON com as demonstrações CoT."
                )
            raciocinios_exemplos[str(exemplo["id"])] = raciocinio

    pasta = PASTA_BASE / dataset
    pasta.mkdir(parents=True, exist_ok=True)
    nome = (Path(retomar).name.removesuffix(".progresso.json") if retomar
            else identificador_novo(dataset, limite, quantidade))
    caminho = pasta / f"{nome}.json"
    progresso = pasta / f"{nome}.progresso.json"
    parametros = {
        "modelo": MODELO,
        "temperatura": TEMPERATURE,
        "limite": limite,
        "maximo_tokens_resposta": NUM_PREDICT,
        "quantidade_exemplos": quantidade,
        "ids_exemplos": [str(e["id"]) for e in exemplos],
        "ids_questoes": [str(q["id"]) for q in questoes],
        "criterio_avaliacao": "todos_splits_sem_demonstracoes",
        "tipo_demonstracao": "questao_raciocinio_resposta",
        "origem_raciocinios_censo": "json_preparado" if dataset == "censo" else None,
    }
    if retomar:
        with progresso.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        if dados["parametros"] != parametros:
            raise ValueError("Os parâmetros atuais diferem do checkpoint.")
        resultados = dados["resultados"]
    else:
        resultados = []
        dados = {
            "id_execucao": nome,
            "tecnica": "chain_of_thought",
            "dataset": dataset,
            "data_inicio": agora(),
            "parametros": parametros,
            "resultados": resultados,
            "status": "em_andamento",
        }

    concluidos = {str(r["id"]) for r in resultados}
    if len(concluidos) != len(resultados):
        raise ValueError("Checkpoint contém questões duplicadas.")
    pendentes = [q for q in questoes if str(q["id"]) not in concluidos]
    tempo_anterior = dados.get("tempo_acumulado_segundos", 0.0)
    inicio = time.perf_counter()
    print(f"\n{dataset.upper()} | {len(questoes)} questões | {quantidade} exemplos")

    def checkpoint():
        total = tempo_anterior + time.perf_counter() - inicio
        dados["tempo_acumulado_segundos"] = total
        dados["metricas_parciais"] = metricas(resultados, total, quantidade, dataset)
        salvar(progresso, dados)

    try:
        for questao in tqdm(pendentes, desc=f"Chain-of-Thought {dataset}"):
            demonstracao = str(questao["id"]) in ids_exemplos
            if dataset == "gsm8k":
                exemplos_prompt = [e for e in exemplos if str(e["id"]) != str(questao["id"])]
                if not exemplos_prompt:
                    raise ValueError("É necessário ter outra demonstração para avaliar esta questão.")
                prompt = prompt_cot_gsm8k(questao, exemplos_prompt)
                gabarito = extrair_gabarito_gsm8k(questao)
            elif dataset == "aqua_rat":
                exemplos_prompt = [e for e in exemplos if str(e["id"]) != str(questao["id"])]
                if not exemplos_prompt:
                    raise ValueError("É necessário ter outra demonstração para avaliar esta questão.")
                prompt = prompt_cot_aqua_rat(questao, exemplos_prompt)
                gabarito = extrair_gabarito_aqua_rat(questao)
            else:
                contexto = sessao.consultar(questao)
                # Segurança: não permite que a questão avaliada seja demonstração.
                exemplos_prompt = [e for e in exemplos if str(e["id"]) != str(questao["id"])]
                if not exemplos_prompt:
                    raise ValueError("Censo precisa de pelo menos dois exemplos para executar demonstrações.")
                prompt = prompt_cot_censo(questao, contexto, exemplos_prompt, contextos_exemplos, raciocinios_exemplos)
                gabarito = extrair_gabarito_censo(questao)

            inicio_questao = time.perf_counter()
            info = consultar_ollama(
                prompt, temperature=TEMPERATURE,
                num_predict=NUM_PREDICT, retornar_metricas=True,
            )
            duracao = round(time.perf_counter() - inicio_questao, 3)
            if not isinstance(info, dict):
                info = {"resposta": None}
            texto = info.get("resposta")
            erro_consulta = texto is None

            if erro_consulta:
                # consultar_ollama já fez as três tentativas. Registra e segue.
                detalhe = info.get("erro_detalhado") or info.get("erro") or (
                    "Falha do Ollama após 3 tentativas (ver erro no terminal)"
                )
                resultados.append({
                    "id": str(questao["id"]), "split": questao.get("split"),
                    "usada_como_exemplo": False, "avaliacao_independente": False,
                    "gabarito": gabarito, "resposta": None, "texto_modelo": None,
                    "resposta_valida": False, "falha_tecnica": True,
                    "acertou": None, "motivo": detalhe,
                    "tentativas_consulta": info.get("tentativas", 3),
                    "revisao_necessaria": False, "metodo_avaliacao": "falha_tecnica",
                    "tempo_segundos": duracao, "tokens_entrada": None,
                    "tokens_saida": None, **recursos(),
                })
                print(f"\n[FALHA TÉCNICA] {dataset}/{questao['id']}: {detalhe}. "
                      "Fora da acurácia; avançando.")
                checkpoint()
                continue

            if dataset == "gsm8k":
                resposta = extrair_resposta_numerica(texto)
                valida = bool(resposta)
                acertou = comparar_numeros(resposta, gabarito) if valida else False
            elif dataset == "aqua_rat":
                resposta = extrair_letra_resposta(texto)
                valida = bool(resposta)
                acertou = resposta == gabarito if valida else False
            else:
                resposta = str(texto).strip() if texto is not None else ""
                valida = bool(resposta)
                # Avalia automaticamente com o gabarito, sem usá-lo no prompt da questão.
                # Respostas inconclusivas ou sem resultado identificável são erros.
                avaliacao_censo = avaliar_censo(questao, resposta, consultar_ollama)
                acertou = avaliacao_censo["acertou"]
                if acertou is None:
                    resultados.append({
                        "id": str(questao["id"]), "split": questao.get("split"),
                        "usada_como_exemplo": False, "avaliacao_independente": False,
                        "gabarito": gabarito, "resposta": resposta,
                        "texto_modelo": texto, "resposta_valida": valida,
                        "falha_tecnica": True, "acertou": None,
                        "motivo": "Avaliador inconclusivo: " + avaliacao_censo["motivo"],
                        "tentativas_consulta": 3, "revisao_necessaria": False,
                        "metodo_avaliacao": "falha_tecnica_avaliador",
                        "tempo_segundos": duracao,
                        "tokens_entrada": info.get("prompt_eval_count"),
                        "tokens_saida": info.get("eval_count"), **recursos(),
                    })
                    checkpoint()
                    continue

            # Falha HTTP/timeout não é erro matemático; resposta sem letra/número é erro.
            if erro_consulta:
                acertou = None

            independente = not demonstracao  # Todos os splits são avaliados, exceto demonstrações.
            revisao = False  # Avaliação binária: não há fila de revisão.
            if erro_consulta:
                motivo = "Falha na consulta ao modelo"
            elif not valida:
                motivo = "Resposta não identificada"
            elif acertou is False:
                motivo = "Resposta incorreta"
            elif acertou is None:
                motivo = "Avaliação inconclusiva"
            else:
                motivo = None

            if dataset == "censo" and not erro_consulta:
                motivo = avaliacao_censo["motivo"]

            resultados.append({
                "id": str(questao["id"]),
                "split": questao.get("split"),
                "usada_como_exemplo": demonstracao,
                "avaliacao_independente": independente,
                "gabarito": gabarito,
                "resposta": resposta,
                "texto_modelo": texto,
                "resposta_valida": valida,
                "falha_tecnica": erro_consulta,
                "acertou": acertou,
                "motivo": motivo,
                "revisao_necessaria": revisao,
                "metodo_avaliacao": ("falha_tecnica" if erro_consulta else avaliacao_censo["metodo_avaliacao"] if dataset == "censo" else "comparacao_exata"),
                "tempo_segundos": duracao,
                "tokens_entrada": info.get("prompt_eval_count"),
                "tokens_saida": info.get("eval_count"),
                **recursos(),
            })
            if len(resultados) % SALVAR_CADA == 0:
                checkpoint()
    except BaseException:
        checkpoint()
        raise

    dados["data_fim"] = agora()
    dados["status"] = "concluido"
    dados["tempo_acumulado_segundos"] = tempo_anterior + time.perf_counter() - inicio
    dados["metricas"] = metricas(resultados, dados["tempo_acumulado_segundos"], quantidade, dataset)
    dados.pop("metricas_parciais", None)
    salvar(caminho, dados)
    if progresso.exists():
        progresso.unlink()
    mostrar_resumo(dataset, dados, caminho)
    return dados

def executar_gsm8k(limite=None, n_exemplos=None, retomar=None):
    return executar_dataset("gsm8k", limite, n_exemplos, retomar)

def executar_aqua_rat(limite=None, n_exemplos=None, retomar=None):
    return executar_dataset("aqua_rat", limite, n_exemplos, retomar)

def executar_censo(limite=None, n_exemplos=None, retomar=None):
    return executar_dataset("censo", limite, n_exemplos, retomar)

if __name__ == "__main__":
    executar_gsm8k(limite=500)
    executar_aqua_rat(limite=500)
    executar_censo(limite=20)

    # executar_gsm8k()
    # executar_aqua_rat()
    # executar_censo()
