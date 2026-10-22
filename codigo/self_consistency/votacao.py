
"""Votação por frequência e seleção semântica cega ao gabarito para o Censo."""

from collections import Counter
import json
import re
import unicodedata


# ============================================================
# 1. VOTAÇÃO MAJORITÁRIA — GSM8K E AQUA-RAT
# ============================================================

def voto_majoritario(respostas):
    """Escolhe a resposta mais frequente entre as respostas válidas."""

    validas = [
        str(r).strip()
        for r in respostas
        if r is not None and str(r).strip()
    ]

    if not validas:
        return {
            "vencedora": "",
            "votos": 0,
            "distribuicao": {},
            "houve_empate": False,
            "total_respostas_validas": 0,
            "metodo_votacao": "frequencia_simples",
        }

    contagem = Counter(validas)
    maior = max(contagem.values())

    vencedoras = [
        resposta
        for resposta, votos in contagem.items()
        if votos == maior
    ]

    return {
        "vencedora": vencedoras[0] if len(vencedoras) == 1 else "",
        "votos": maior,
        "distribuicao": dict(contagem),
        "houve_empate": len(vencedoras) > 1,
        "total_respostas_validas": len(validas),
        "metodo_votacao": "frequencia_simples",
    }


# ============================================================
# 2. NORMALIZAÇÃO DE RESPOSTAS DO CENSO
# ============================================================

def _canonico(texto):
    """Normaliza maiúsculas, acentos e espaços."""

    texto = unicodedata.normalize(
        "NFKD",
        str(texto).casefold()
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    return " ".join(texto.split()).strip(" .;")


def _numero_unico(texto):
    """Normaliza respostas compostas somente por um número."""

    from codigo.utils import normalizar_numero

    texto = str(texto).strip()

    if not re.fullmatch(r"-?\d[\d., ]*%?", texto):
        return None

    percentual = texto.endswith("%")

    try:
        valor = normalizar_numero(
            texto.rstrip("%").strip()
        )

        if not abs(valor) < float("inf"):
            return None

        prefixo = "percentual:" if percentual else "numero:"

        return prefixo + format(valor, ".12g")

    except (ValueError, TypeError, OverflowError):
        return None


# ============================================================
# 3. EXTRAÇÃO E VALIDAÇÃO DO ÍNDICE
# ============================================================

def _json_objeto(texto):
    """Lê um objeto JSON válido, inclusive dentro de bloco Markdown."""

    texto = str(texto or "").strip()

    try:
        return json.loads(texto)

    except (ValueError, TypeError):
        pass

    encontrado = re.search(
        r"\{[\s\S]*?\}",
        texto
    )

    if encontrado:
        try:
            return json.loads(encontrado.group())

        except ValueError:
            pass

    return None


def _extrair_indice(texto):
    """Aceita JSON válido ou um índice isolado.

    Não aceita JSON incompleto, mesmo que contenha um índice.
    """

    texto = str(texto or "").strip()

    objeto = _json_objeto(texto)

    if isinstance(objeto, dict):
        indice = objeto.get("indice")

        if type(indice) is int:
            return indice

        if (
            isinstance(indice, str)
            and re.fullmatch(r"\d+", indice.strip())
        ):
            return int(indice.strip())

        return None

    # Aceita somente o número isolado, sem texto adicional.
    if re.fullmatch(r"\d+", texto):
        return int(texto)

    return None


# ============================================================
# 4. SELEÇÃO SEMÂNTICA — CENSO ESCOLAR
# ============================================================

def voto_censo_semantico(
    pergunta,
    respostas,
    consultar_ollama
):
    """Seleciona a resposta mais consistente sem consultar o gabarito.

    Primeiro verifica equivalência determinística.
    Quando não há maioria clara, consulta o seletor semântico.
    """

    validas = [
        (indice + 1, str(resposta).strip())
        for indice, resposta in enumerate(respostas)
        if resposta is not None and str(resposta).strip()
    ]

    # Nenhuma resposta válida.
    if not validas:
        resultado = voto_majoritario(respostas)
        resultado["metodo_votacao"] = "censo_sem_resposta"
        return resultado

    # Normaliza respostas para identificar equivalências simples.
    chaves = [
        _numero_unico(resposta)
        or "texto:" + _canonico(resposta)
        for _, resposta in validas
    ]

    contagem = Counter(chaves)
    maximo = max(contagem.values())

    # Há maioria absoluta: não precisa consultar o LLM.
    if maximo > len(validas) / 2:
        chave = next(
            chave
            for chave, votos in contagem.items()
            if votos == maximo
        )

        posicao = chaves.index(chave)

        return {
            "vencedora": validas[posicao][1],
            "votos": maximo,
            "distribuicao": dict(contagem),
            "houve_empate": False,
            "total_respostas_validas": len(validas),
            "metodo_votacao": "censo_equivalencia_deterministica",
            "indice_selecionado": validas[posicao][0],
            "tentativas_seletor": 0,
        }

    if consultar_ollama is None:
        raise RuntimeError(
            "Seletor semântico do Censo indisponível."
        )

    # Mantém os índices originais das cinco amostras.
    indices_validos = {
        indice
        for indice, _ in validas
    }

    opcoes = "\n".join(
        f"{indice}. {resposta}"
        for indice, resposta in validas
    )

    # CORREÇÃO PRINCIPAL:
    # O seletor não deve gerar justificativas longas.
    prompt = (
        "Você deve selecionar a resposta mais consistente "
        "entre as candidatas para a MESMA pergunta.\n"
        "Compare significados, números, categorias e listas.\n"
        "Respostas semanticamente equivalentes podem "
        "estar escritas de maneiras diferentes.\n"
        "NÃO consulte o gabarito: ele não foi fornecido.\n"
        "NÃO resolva novamente a questão.\n"
        "NÃO invente uma nova resposta.\n"
        "Escolha somente um índice existente nas candidatas.\n"
        "Se não houver consenso semântico claro, escolha 0.\n"
        "Responda SOMENTE com um JSON curto.\n"
        "NÃO escreva justificativas ou explicações.\n"
        'Formato obrigatório: {"indice": 1}\n\n'
        f"PERGUNTA:\n{pergunta}\n\n"
        f"CANDIDATAS:\n{opcoes}"
    )

    ultimo_erro = "Seletor não retornou uma escolha válida."
    ultima_resposta = ""

    # Até três tentativas de seleção.
    for tentativa in range(1, 4):

        info = consultar_ollama(
            prompt,
            temperature=0,
            num_predict=160,
            retornar_metricas=True,
        )

        if not isinstance(info, dict):
            ultimo_erro = "Consulta não retornou metadados."
            continue

        texto = info.get("resposta")

        if texto is None:
            ultimo_erro = (
                info.get("erro_detalhado")
                or "Falha técnica do seletor."
            )
            continue

        ultima_resposta = str(texto)

        indice = _extrair_indice(texto)

        # O seletor declarou ausência de consenso.
        if indice == 0:
            return {
                "vencedora": "",
                "votos": 0,
                "distribuicao": dict(contagem),
                "houve_empate": True,
                "total_respostas_validas": len(validas),
                "metodo_votacao": "censo_semantica_sem_consenso",
                "tentativas_seletor": tentativa,
            }

        # O índice corresponde a uma candidata existente.
        if indice in indices_validos:

            resposta = next(
                resposta
                for i, resposta in validas
                if i == indice
            )

            return {
                "vencedora": resposta,
                "votos": None,
                "distribuicao": dict(contagem),
                "houve_empate": False,
                "total_respostas_validas": len(validas),
                "metodo_votacao": "censo_selecao_semantica_llm",
                "indice_selecionado": indice,
                "tentativas_seletor": tentativa,
                "justificativa_seletor": "",
            }

        ultimo_erro = (
            "JSON inválido ou índice fora das candidatas."
        )

    # Não inventa um vencedor quando o seletor falha.
    raise RuntimeError(
        "Falha técnica no seletor semântico do Censo: "
        f"{ultimo_erro} "
        f"Resposta recebida: {ultima_resposta[:200]!r}"
    )
