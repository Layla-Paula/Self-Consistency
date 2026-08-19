import os
import re
import json
import time
import requests



# CONFIGURAÇÃO

MODELO_OLLAMA = "llama3.2"
URL_OLLAMA = "http://localhost:11434/api/generate"

DATASET_ENEM = "dados/enem/final/enem_matematica_completo.json"
DATASET_GSM8K = "dados/gsm8k/final/gsm8k_ptbr.json"


# DATASETS

def carregar_enem():
    with open(
        DATASET_ENEM,
        "r",
        encoding="utf-8"
    ) as f:
        dados = json.load(f)

    return dados["questoes"]


def carregar_gsm8k():
    with open(
        DATASET_GSM8K,
        "r",
        encoding="utf-8"
    ) as f:
        dados = json.load(f)

    return dados["problemas"]



# FORMATAÇÃO

def formatar_alternativas(alternativas): # Recebe as alternativas e transforma essas alternativas em texto formatado com o valor associado das alternativa
    linhas = []

    for letra in ["A", "B", "C", "D", "E"]:

        valor = alternativas.get(
            letra,
            ""
        )

        if valor:
            linhas.append(
                f"{letra}) {valor}"
            )

    return "\n".join(linhas)


def montar_questao_enem(questao): # Monta o texto que será enviado ao modelo.

    return f"""
Questão {questao["numero"]} - ENEM {questao["ano"]}

{questao["enunciado"]}

Alternativas:
{formatar_alternativas(questao["alternativas"])}
""".strip()


def montar_questao_gsm8k(problema):

    return (
        problema.get("question_pt")
        or problema.get("problema")
        or problema.get("question")
        or ""
    )



# RESPOSTAS

def extrair_letra_resposta(texto):

    if not texto:
        return ""

    texto = texto.upper().strip()
        # \s*      = zero ou mais espaços
        # [:\-]?   = ":" ou "-", opcionais
        # ([A-E])  = captura uma letra entre A e E
    padroes = [
        r"RESPOSTA FINAL\s*[:\-]?\s*([A-E])",
        r"ALTERNATIVA CORRETA\s*[:\-]?\s*([A-E])",
        r"ALTERNATIVA\s*[:\-]?\s*([A-E])",
        r"RESPOSTA\s*[:\-]?\s*([A-E])",
        r"\b([A-E])\b"
    ]

    for padrao in padroes:

        m = re.search(
            padrao,
            texto
        )

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

        m = re.search(
            padrao,
            texto,
            re.I
        )

        if m:
            return (
                m.group(1)
                .replace(",", ".")
            )

    numeros = re.findall(
        r"[\-]?\d+(?:[,.]\d+)?",
        texto
    )

    if numeros:
        return (
            numeros[-1]
            .replace(",", ".")
        )

    return ""


def extrair_gabarito_gsm8k(problema):

    resposta = (
        problema.get("resposta")
        or problema.get("answer_pt")
        or problema.get("answer")
        or ""
    )

    m = re.search(
        r"####\s*([\-]?\d+(?:[,.]\d+)?)",
        resposta
    )

    if m:
        return (
            m.group(1)
            .replace(",", ".")
        )

    m = re.search(
        r"([\-]?\d+(?:[,.]\d+)?)$",
        resposta.strip()
    )

    if m:
        return (
            m.group(1)
            .replace(",", ".")
        )

    return ""


def comparar_numeros(a, b):

    try:

        valor_a = float(
            str(a).replace(",", ".")
        )

        valor_b = float(
            str(b).replace(",", ".")
        )

        return valor_a == valor_b

    except Exception:

        return (
            str(a).strip()
            ==
            str(b).strip()
        )



# OLLAMA

# Função responsável por enviar um prompt ao Ollama e receber a resposta produzida pelo modelo.
def consultar_ollama(
    prompt,
    temperature=0.0, #  Controla a aleatoriedade das respostas.
    num_predict=512 # Número máximo de tokens que o modelo poderá gerar
):

    payload = {
        "model": MODELO_OLLAMA,
        "prompt": prompt,
        "stream": False,  # False significa que a resposta será retornada inteira, e não enviada aos poucos em streaming
        "options": {
            "temperature": temperature,
            "num_predict": num_predict
        }
    }

    # Permite realizar até três tentativas de comunicação com o Ollama

    for tentativa in range(1, 4):

        try:

            resposta = requests.post(
                URL_OLLAMA,
                json=payload,
                timeout=300   # 300 segundos = 5 minutos.
            )

            resposta.raise_for_status()

            dados = resposta.json()

            return dados.get(
                "response",
                ""
            )

        except Exception as e:

            print()
            print(
                f"Erro no Ollama "
                f"(tentativa {tentativa}/3): {e}"
            )

            if tentativa < 3:

                print(
                    "Tentando novamente..."
                )

                time.sleep(5)

    print(
        "Falha após 3 tentativas."
    )

    return None



# ARQUIVOS


def salvar_json(
    caminho,
    dados
):

    diretorio = os.path.dirname(
        caminho
    )

    if diretorio:

        os.makedirs( # Cria a pasta caso ela ainda não exista.
            diretorio,
            exist_ok=True
        )

    with open(
        caminho,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            dados,
            f,
            ensure_ascii=False,
            indent=2
        )