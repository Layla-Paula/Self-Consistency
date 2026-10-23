
"""Votação por frequência e seleção semântica cega ao gabarito para o Censo."""

from collections import Counter
import json
import re
import unicodedata


# ============================================================
# 1. VOTAÇÃO MAJORITÁRIA — GSM8K E AQUA-RAT
# ============================================================

def voto_majoritario(respostas, normalizar_voto=None):
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
            "metodo_votacao": "frequencia_primeira_geracao",
        }

    chaves = []
    for resposta in validas:
        if normalizar_voto is None:
            chave = resposta
        else:
            try:
                chave = str(normalizar_voto(resposta)).strip()
            except (ValueError, TypeError, OverflowError):
                chave = resposta
        chaves.append(chave)
    contagem = Counter(chaves)
    maior = max(contagem.values())
    vencedoras = [chave for chave, votos in contagem.items() if votos == maior]
    # Empate: primeira geracao entre as chaves lideres.
    vencedora = next(chave for chave in chaves if chave in vencedoras)
    return {
        "vencedora": vencedora,
        "votos": maior,
        "distribuicao": dict(contagem),
        "houve_empate": len(vencedoras) > 1,
        "total_respostas_validas": len(validas),
        "metodo_votacao": "frequencia_primeira_geracao",
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

    try:
        valor = normalizar_numero(
            texto.rstrip("%").strip()
        )

        if not abs(valor) < float("inf"):
            return None

        # Percentual e numero sem unidade NAO sao automaticamente equivalentes.
        prefixo = "percentual:" if texto.endswith("%") else "numero:"
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
    Depois escolhe a resposta de maior frequência; empate usa a primeira geração.
    O parâmetro consultar_ollama é mantido para compatibilidade, mas não é usado.
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

    # A pluralidade vence mesmo sem maioria absoluta (por exemplo, 2-1-1-1).
    # Empates na maior frequência: primeira amostra gerada entre as empatadas.
    lideres = {chave for chave, votos in contagem.items() if votos == maximo}
    posicao = next(i for i, chave in enumerate(chaves) if chave in lideres)
    empate = len(lideres) > 1
    return {
        "vencedora": validas[posicao][1],
        "votos": maximo,
        "distribuicao": dict(contagem),
        "houve_empate": empate,
        "total_respostas_validas": len(validas),
        "metodo_votacao": (
            "censo_empate_primeira_geracao" if empate
            else "censo_pluralidade_deterministica"
        ),
        "indice_selecionado": validas[posicao][0],
        "tentativas_seletor": 0,
    }


def normalizar_voto_gsm8k(texto):
    """Chave compartilhada por execução e auditoria; 1.000 = 1000."""
    from codigo.utils import normalizar_numero
    valor = normalizar_numero(texto)
    if not abs(valor) < float('inf'):
        raise ValueError('Número não finito.')
    return str(int(valor)) if valor.is_integer() else format(valor, '.12g')
