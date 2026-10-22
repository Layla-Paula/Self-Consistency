"""Utilitários compartilhados """

import json
import math
import re
import time
from pathlib import Path

import requests

MODELO_OLLAMA = "llama3.2"
URL_OLLAMA = "http://localhost:11434/api/generate"
DATASET_GSM8K = Path("dados/gsm8k/final/gsm8k_ptbr.json")
DATASET_AQUA_RAT = Path("dados/aqua_rat/final/aqua_rat_ptbr_argos.json")
DATASET_CENSO = Path("dados/censo_escolar/final/censo_escolar_2025.json")


def carregar_json(caminho):
    with open(caminho, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar_json(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def carregar_registros(caminho):
    dados = carregar_json(caminho)
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict):
        for chave in ("problemas", "questoes", "questions"):
            if isinstance(dados.get(chave), list):
                return dados[chave]
    raise ValueError(f"Estrutura de questões não reconhecida: {caminho}")


def filtrar_split(registros, split=None):
    if split is None:
        return registros
    return [item for item in registros if item.get("split") == split]


def carregar_gsm8k(split=None):
    return filtrar_split(carregar_registros(DATASET_GSM8K), split)


def carregar_aqua_rat(split=None):
    return filtrar_split(carregar_registros(DATASET_AQUA_RAT), split)


def carregar_censo(split=None):
    registros = carregar_registros(DATASET_CENSO)
    if split is not None:
        raise ValueError("O Censo Escolar não possui splits definidos no JSON atual.")
    return registros


def formatar_alternativas(alternativas):
    """Aceita dict A-E ou lista de cinco textos, com ou sem prefixo A)."""
    if isinstance(alternativas, list):
        if len(alternativas) != 5:
            raise ValueError("AQuA-RAT precisa de exatamente cinco alternativas.")
        convertidas = {}
        for letra, texto in zip("ABCDE", alternativas):
            texto = str(texto).strip()
            prefixo = re.match(r"^\s*([A-E])\s*[).:\-]\s*(.+)$", texto, re.I | re.S)
            if prefixo:
                letra_encontrada = prefixo.group(1).upper()
                if letra_encontrada != letra:
                    raise ValueError(
                        f"Alternativa fora de ordem: esperado {letra}, "
                        f"recebido {letra_encontrada}."
                    )
                texto = prefixo.group(2).strip()
            convertidas[letra] = texto
        alternativas = convertidas
    if not isinstance(alternativas, dict):
        raise ValueError("Alternativas devem ser uma lista ou dicionário.")
    alternativas = {str(chave).upper(): valor for chave, valor in alternativas.items()}
    linhas = []
    for letra in "ABCDE":
        valor = alternativas.get(letra)
        if valor is None or not str(valor).strip():
            raise ValueError(f"Alternativa {letra} ausente.")
        linhas.append(f"{letra}) {str(valor).strip()}")
    return "\n".join(linhas)


def montar_questao_gsm8k(problema):
    enunciado = str(
        problema.get("question_pt")
        or problema.get("problema")
        or problema.get("question")
        or ""
    ).strip()
    if not enunciado:
        raise ValueError("GSM8K sem enunciado.")
    return enunciado


def montar_questao_aqua_rat(problema):
    enunciado = str(
        problema.get("question_pt")
        or problema.get("pergunta")
        or problema.get("question")
        or ""
    ).strip()
    alternativas = (
        problema.get("options_pt")
        or problema.get("alternativas")
        or problema.get("options")
    )
    if not enunciado or alternativas is None:
        raise ValueError("AQuA-RAT sem enunciado ou alternativas.")
    return f"{enunciado}\n\nAlternativas:\n{formatar_alternativas(alternativas)}"


def montar_questao_censo(questao, contexto=None):
    """Recebe contexto calculado externamente; nunca utiliza resposta_esperada."""
    enunciado = str(questao.get("pergunta") or questao.get("enunciado") or "").strip()
    if not enunciado:
        raise ValueError("Censo Escolar sem pergunta.")
    if contexto is None:
        contexto = questao.get("contexto")
    contexto = str(contexto or "").strip()
    if not contexto:
        raise ValueError(
            f"Questão {questao.get('id', '?')} sem contexto dos microdados. "
            "Prepare a consulta antes de executar."
        )
    return f"Dados do Censo Escolar 2025:\n{contexto}\n\nPergunta:\n{enunciado}"


def extrair_letra_resposta(texto):
    """Extrai decisão explícita A-E, inclusive 'Resposta: B' do Few-shot.

    Não extrai letras apenas por aparecerem na lista de alternativas.
    Quando há várias declarações explícitas, usa a última.
    """
    if not texto:
        return ""
    texto = str(texto).strip()
    padrao = re.compile(
        r"(?:\b(?:resposta\s+final|resposta\s+correta|resposta|alternativa\s+correta|"
        r"alternativa\s+escolhida|op[cç][aã]o\s+correta|"
        r"(?:a\s+)?[uú]nica\s+(?:alternativa|op[cç][aã]o)(?:\s+que\s+[eé]\s+igual)?|"
        r"(?:a\s+)?(?:resposta|alternativa|op[cç][aã]o)\s+(?:[eé]|seria)|"
        r"escolho|marco|assinalo|opto\s+pela|ans(?:wer)?)\b)"
        r"\s*(?:(?:correta|[eé]|seria)\s*)?(?:[:=]|->|[-–])?\s*"
        r"\**\(?([A-E])\)?(?=$|[\s).,:;!\-–*])", re.I
    )
    achados = list(padrao.finditer(texto))
    if achados:
        return achados[-1].group(1).upper()
    ultima = next((linha.strip() for linha in reversed(texto.splitlines()) if linha.strip()), "")
    isolada = re.fullmatch(r"(?:\*\*)?\(?([A-E])\)?[.)]?(?:\*\*)?", ultima, re.I)
    return isolada.group(1).upper() if isolada else ""


NUMERO = r"-?(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"


def normalizar_numero(texto):
    valor = str(texto).strip().replace(" ", "")
    if "," in valor and "." in valor:
        valor = (
            valor.replace(".", "").replace(",", ".")
            if valor.rfind(",") > valor.rfind(".")
            else valor.replace(",", "")
        )
    elif "," in valor:
        valor = valor.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", valor):
        valor = valor.replace(".", "")
    return float(valor)


def extrair_resposta_numerica(texto):
    """Recupera números finais declarados, inclusive 'Resposta: 72' do Few-shot.

    Não usa números soltos de cálculos intermediários como resposta final.
    """
    if not texto:
        return ""
    texto = str(texto).strip()
    marcadores = list(re.finditer(r"(?:\bresposta\s+final\b|\bresposta\b|####)\s*[:=\-]?\s*", texto, re.I))
    if not marcadores:
        linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
        if not linhas:
            return ""
        ultima = " ".join(linhas[-2:])
        conclusao = re.search(
            rf"(?:portanto|assim|logo|resultado|total|pagou|ganhou|sobrou|restam|precisa de)"
            rf"[^\n]*?({NUMERO})\s*(?:\w+)?[.!]?\s*$", ultima, re.I)
        if not conclusao or re.search(r"[a-zA-Z]\s*[/+*^]\s*\d", ultima):
            return ""
        return conclusao.group(1)
    trecho = (texto[marcadores[-1].end():].splitlines() or [""])[0].strip()
    trecho = re.sub(r"^(?:R\$|US\$|\$)\s*", "", trecho, flags=re.I)
    numero = re.match(rf"({NUMERO})(?![\w/])", trecho)
    if not numero:
        return ""
    resto = trecho[numero.end():].lstrip()
    if re.match(r"[+*/^=]|-(?=\s*\d)|[xX]\s*(?:/|\d)", resto):
        return ""
    return numero.group(1)

def extrair_gabarito_gsm8k(problema):
    resposta = str(
        problema.get("resposta")
        or problema.get("answer_en")
        or problema.get("answer")
        or problema.get("answer_pt")
        or ""
    )
    encontrado = re.search(rf"####\s*({NUMERO})", resposta)
    if encontrado:
        return encontrado.group(1)
    encontrado = re.search(rf"({NUMERO})\s*$", resposta)
    return encontrado.group(1) if encontrado else ""


def extrair_gabarito_aqua_rat(problema):
    letra = str(problema.get("correct") or problema.get("gabarito") or "").upper().strip()
    if len(letra) != 1 or letra not in "ABCDE":
        raise ValueError(f"Gabarito AQuA-RAT inválido: {letra!r}")
    return letra


def extrair_gabarito_censo(questao):
    return questao.get("resposta_esperada") or questao.get("gabarito") or questao.get("resposta") or ""


def comparar_numeros(a, b):
    try:
        valor_a, valor_b = normalizar_numero(a), normalizar_numero(b)
        return (
            math.isfinite(valor_a)
            and math.isfinite(valor_b)
            and math.isclose(valor_a, valor_b, rel_tol=0, abs_tol=1e-9)
        )
    except (ValueError, TypeError, OverflowError):
        return False


def consultar_ollama(
    prompt,
    temperature=0.0,
    num_predict=512,
    retornar_metricas=False,
    num_ctx=8192,
    top_k=40,
    top_p=0.9,
):
    """Consulta o Ollama até 3 vezes; falhas retornam metadados, não acerto/erro.

    Mantém retornar_metricas como quarto argumento para compatibilidade com
    chamadas posicionais antigas. O chamador decide como registrar a falha.
    """
    payload = {
        "model": MODELO_OLLAMA,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
            "top_k": top_k,
            "top_p": top_p,
        },
    }

    ultimo_erro = None
    inicio_total = time.perf_counter()

    for tentativa in range(1, 4):
        try:
            resposta = requests.post(URL_OLLAMA, json=payload, timeout=300)
            resposta.raise_for_status()
            dados = resposta.json()
            if not isinstance(dados, dict):
                raise ValueError("O Ollama retornou um JSON que não é um objeto.")

            texto = dados.get("response", "")
            if texto is None or not isinstance(texto, str):
                raise ValueError("O Ollama retornou um campo 'response' inválido.")

            duracao = time.perf_counter() - inicio_total
            if retornar_metricas:
                return {
                    "resposta": texto,
                    "tempo_total_segundos": duracao,
                    "total_duration_ns": dados.get("total_duration"),
                    "prompt_eval_count": dados.get("prompt_eval_count"),
                    "prompt_eval_duration_ns": dados.get("prompt_eval_duration"),
                    "eval_count": dados.get("eval_count"),
                    "eval_duration_ns": dados.get("eval_duration"),
                    "done_reason": dados.get("done_reason"),
                    "done": dados.get("done"),
                    "tentativas": tentativa,
                    "erro_detalhado": None,
                }
            return texto

        except (requests.RequestException, ValueError) as erro:
            ultimo_erro = f"{type(erro).__name__}: {erro}"
            if isinstance(erro, requests.HTTPError) and erro.response is not None:
                detalhe_servidor = erro.response.text.strip()[:1000]
                if detalhe_servidor:
                    ultimo_erro += f" | Resposta do Ollama: {detalhe_servidor}"

            print(f"Erro no Ollama (tentativa {tentativa}/3): {ultimo_erro}")
            if tentativa < 3:
                time.sleep(5)

    print("Falha técnica após 3 tentativas. A execução pode avançar para a próxima questão.")
    if retornar_metricas:
        return {
            "resposta": None,
            "tempo_total_segundos": time.perf_counter() - inicio_total,
            "total_duration_ns": None,
            "prompt_eval_count": None,
            "prompt_eval_duration_ns": None,
            "eval_count": None,
            "eval_duration_ns": None,
            "done_reason": None,
            "done": None,
            "tentativas": 3,
            "erro_detalhado": ultimo_erro,
        }
    return None
