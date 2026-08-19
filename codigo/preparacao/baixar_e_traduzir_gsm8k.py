"""
GSM8K -> Português
Autor: Layla Paula

Baixa o dataset GSM8K
Salva versão original
Traduz para PT-BR
Salva progresso automaticamente
Gera JSON final
"""

from datasets import load_dataset
from deep_translator import GoogleTranslator

import json
import os
import time
from datetime import datetime


# PASTAS

PASTA_BASE = "dados/gsm8k"

ARQ_ORIGINAL = os.path.join(
    PASTA_BASE,
    "gsm8k_original.json"
)

ARQ_PROGRESSO = os.path.join(
    PASTA_BASE,
    "progresso_traducao.json"
)

ARQ_FINAL = os.path.join(
    PASTA_BASE,
    "gsm8k_ptbr.json"
)


# CRIAR PASTA


os.makedirs(PASTA_BASE, exist_ok=True)


# BAIXAR DATASET


def baixar_gsm8k():

    print("Baixando GSM8K...")

    dataset = load_dataset(
        "openai/gsm8k",
        "main"
    )

    dados = []

    for i, item in enumerate(dataset["train"]):

        dados.append({
            "id": f"train_{i}",
            "split": "train",
            "question": item["question"],
            "answer": item["answer"]
        })

    for i, item in enumerate(dataset["test"]):

        dados.append({
            "id": f"test_{i}",
            "split": "test",
            "question": item["question"],
            "answer": item["answer"]
        })

    print(f"Total: {len(dados)}")

    return dados


# SALVAR ORIGINAL


def salvar_original(dados):

    with open(
        ARQ_ORIGINAL,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            dados,
            f,
            ensure_ascii=False,
            indent=2
        )


# CARREGAR PROGRESSO


def carregar_progresso():

    if os.path.exists(ARQ_PROGRESSO):

        with open(
            ARQ_PROGRESSO,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    return []


# SALVAR PROGRESSO


def salvar_progresso(lista):

    with open(
        ARQ_PROGRESSO,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            lista,
            f,
            ensure_ascii=False,
            indent=2
        )


# TRADUTOR


translator = GoogleTranslator(
    source="en",
    target="pt"
)

def traduzir(texto):

    try:

        return translator.translate(texto)

    except Exception as e:

        print(f"Erro tradução: {e}")

        return texto


# TRADUÇÃO


def traduzir_dataset(dados):

    traduzidos = carregar_progresso()

    ids_existentes = {
        item["id"]
        for item in traduzidos
    }

    total = len(dados)

    print(
        f"Já traduzidos: {len(ids_existentes)}"
    )

    for indice, item in enumerate(dados):

        if item["id"] in ids_existentes:
            continue

        print(
            f"[{indice+1}/{total}] {item['id']}"
        )

        pergunta_pt = traduzir(
            item["question"]
        )

        resposta_pt = traduzir(
            item["answer"]
        )

        registro = {

            "id": item["id"],

            "split": item["split"],

            "question_en":
                item["question"],

            "question_pt":
                pergunta_pt,

            "answer_en":
                item["answer"],

            "answer_pt":
                resposta_pt
        }

        traduzidos.append(
            registro
        )

        if len(traduzidos) % 25 == 0:

            salvar_progresso(
                traduzidos
            )

            print(
                f"Salvos: {len(traduzidos)}"
            )

        time.sleep(0.2)

    salvar_progresso(
        traduzidos
    )

    return traduzidos


# JSON FINAL


def gerar_json_final(traduzidos):

    resultado = {

        "dataset_info": {

            "nome":
                "GSM8K PT-BR",

            "data_criacao":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "total":
                len(traduzidos)
        },

        "problemas":
            traduzidos
    }

    with open(
        ARQ_FINAL,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            resultado,
            f,
            ensure_ascii=False,
            indent=2
        )


# MAIN


def main():

    print("=" * 60)
    print("GSM8K PT-BR")
    print("=" * 60)

    if os.path.exists(ARQ_ORIGINAL):

        print(
            "Usando dataset já baixado..."
        )

        with open(
            ARQ_ORIGINAL,
            "r",
            encoding="utf-8"
        ) as f:

            dados = json.load(f)

    else:

        dados = baixar_gsm8k()

        salvar_original(
            dados
        )

    traduzidos = traduzir_dataset(
        dados
    )

    gerar_json_final(
        traduzidos
    )

    print("\nConcluído!")
    print(
        f"Total traduzido: {len(traduzidos)}"
    )

if __name__ == "__main__":
    main()