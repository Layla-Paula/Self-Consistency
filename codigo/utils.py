import os
import re
import json
import time
import requests

# =====================================================
# CONFIGURAÇÃO
# =====================================================

MODELO_OLLAMA = "llama3.2"
URL_OLLAMA = "http://localhost:11434/api/generate"

DATASET_ENEM = "dados/enem/final/enem_matematica_completo.json"
DATASET_GSM8K = "dados/gsm8k/final/gsm8k_ptbr.json"


# =====================================================
# DATASETS
# =====================================================

def carregar_enem():
    with open(DATASET_ENEM, "r", encoding="utf-8") as f:
        dados = json.load(f)

    return dados["questoes"]


def carregar_gsm8k():
    with open(DATASET_GSM8K, "r", encoding="utf-8") as f:
        dados = json.load(f)

    return dados["problemas"]


# =====================================================
# FORMATAÇÃO
# =====================================================

def formatar_alternativas(alternativas):
    linhas = []

    for letra in ["A", "B", "C", "D", "E"]:
        valor = alternativas.get(letra, "")

        if valor:
            linhas.append(f"{letra}) {valor}")

    return "\n".join(linhas)


def montar_questao_enem(questao):
    return f"""
Questão {questao["numero"]} - ENEM {questao["ano"]}

{questao["enunciado"]}

Alternativas:
{formatar_alternativas(questao["alternativas"])}
""".strip()


def montar_questao_gsm8k(problema):
    return problema["question_pt"]


# =====================================================
# RESPOSTAS
# =====================================================

def extrair_letra_resposta(texto):
    if not texto:
        return ""

    texto = texto.upper().strip()

    padroes = [
        r"RESPOSTA FINAL\s*[:\-]?\s*([A-E])",
        r"ALTERNATIVA CORRETA\s*[:\-]?\s*([A-E])",
        r"ALTERNATIVA\s*[:\-]?\s*([A-E])",
        r"RESPOSTA\s*[:\-]?\s*([A-E])",
        r"\b([A-E])\b"
    ]

    for padrao in padroes:
        m = re.search(padrao, texto)

        if m:
            return m.group(1)

    return ""


def extrair_resposta_numerica(texto):
    if not texto:
        return ""

    texto = texto.strip()

    padroes = [
        r"RESPOSTA FINAL\s*[:\-]?\s*([\-]?\d+(?:[,.]\d+)?)",
        r"RESPOSTA\s*[:\-]?\s*([\-]?\d+(?:[,.]\d+)?)",
        r"####\s*([\-]?\d+(?:[,.]\d+)?)"
    ]

    for padrao in padroes:
        m = re.search(padrao, texto, re.I)

        if m:
            return m.group(1).replace(",", ".")

    numeros = re.findall(r"[\-]?\d+(?:[,.]\d+)?", texto)

    if numeros:
        return numeros[-1].replace(",", ".")

    return ""


def extrair_gabarito_gsm8k(answer_pt):
    m = re.search(r"####\s*([\-]?\d+(?:[,.]\d+)?)", answer_pt)

    if m:
        return m.group(1).replace(",", ".")

    return ""


# =====================================================
# OLLAMA
# =====================================================

def consultar_ollama(prompt, temperature=0.0, num_predict=512):
    payload = {
        "model": MODELO_OLLAMA,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict
        }
    }

    for tentativa in range(3):
        try:
            resposta = requests.post(
                URL_OLLAMA,
                json=payload,
                timeout=300
            )

            resposta.raise_for_status()

            return resposta.json().get("response", "")

        except Exception as e:
            print(f"Erro no Ollama: {e}")
            print("Tentando novamente...")
            time.sleep(5)

    return ""


# =====================================================
# ARQUIVOS
# =====================================================

def salvar_json(caminho, dados):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(
            dados,
            f,
            ensure_ascii=False,
            indent=2
        )

def montar_questao_gsm8k(problema):
    return problema.get("question_pt") or problema.get("problema") or ""


def extrair_gabarito_gsm8k(problema):
    resposta = (
        problema.get("resposta")
        or problema.get("answer_pt")
        or problema.get("answer")
        or ""
    )

    m = re.search(r"####\s*([\-]?\d+(?:[,.]\d+)?)", resposta)

    if m:
        return m.group(1).replace(",", ".")

    m = re.search(r"([\-]?\d+(?:[,.]\d+)?)$", resposta.strip())

    if m:
        return m.group(1).replace(",", ".")

    return ""


def comparar_numeros(a, b):
    try:
        return float(str(a).replace(",", ".")) == float(str(b).replace(",", "."))
    except Exception:
        return str(a).strip() == str(b).strip()