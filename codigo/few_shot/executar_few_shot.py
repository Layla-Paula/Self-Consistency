from tqdm import tqdm

from codigo.utils import (
    carregar_enem,
    carregar_gsm8k,
    consultar_ollama,
    extrair_letra_resposta,
    extrair_resposta_numerica,
    extrair_gabarito_gsm8k,
    comparar_numeros,
    salvar_json
)

from codigo.few_shot.prompts import (
    prompt_few_shot_enem,
    prompt_few_shot_gsm8k
)


SAIDA_ENEM = "resultados/few_shot/enem_few_shot.json"
SAIDA_GSM8K = "resultados/few_shot/gsm8k_few_shot.json"


def executar_enem(limite=None):
    questoes = carregar_enem()

    if limite:
        questoes = questoes[:limite]

    resultados = []

    for q in tqdm(questoes, desc="Few-Shot ENEM"):
        prompt = prompt_few_shot_enem(q)

        resposta_completa = consultar_ollama(
            prompt=prompt,
            temperature=0.0,
            num_predict=200
        )

        resposta_modelo = extrair_letra_resposta(resposta_completa)

        item = {
            "metodo": "few_shot",
            "dataset": "enem",
            "modelo": "llama3.2",
            "ano": q["ano"],
            "numero": q["numero"],
            "gabarito": q["gabarito"],
            "resposta_modelo": resposta_modelo,
            "acertou": resposta_modelo == q["gabarito"],
            "tem_imagem": q.get("tem_imagem", False),
            "resposta_completa": resposta_completa
        }

        resultados.append(item)

        salvar_json(
            SAIDA_ENEM,
            {
                "metodo": "few_shot",
                "dataset": "enem",
                "modelo": "llama3.2",
                "total": len(resultados),
                "resultados": resultados
            }
        )

    print(f"Salvo: {SAIDA_ENEM}")


def executar_gsm8k(limite=None):
    problemas = carregar_gsm8k()

    if limite:
        problemas = problemas[:limite]

    resultados = []

    for i, p in enumerate(tqdm(problemas, desc="Few-Shot GSM8K")):
        prompt = prompt_few_shot_gsm8k(p)

        resposta_completa = consultar_ollama(
            prompt=prompt,
            temperature=0.0,
            num_predict=200
        )

        resposta_modelo = extrair_resposta_numerica(resposta_completa)
        gabarito = extrair_gabarito_gsm8k(p)

        item = {
            "metodo": "few_shot",
            "dataset": "gsm8k",
            "modelo": "llama3.2",
            "id": p.get("id", i),
            "split": p.get("split", ""),
            "gabarito": gabarito,
            "resposta_modelo": resposta_modelo,
            "acertou": comparar_numeros(resposta_modelo, gabarito),
            "resposta_completa": resposta_completa
        }

        resultados.append(item)

        salvar_json(
            SAIDA_GSM8K,
            {
                "metodo": "few_shot",
                "dataset": "gsm8k",
                "modelo": "llama3.2",
                "total": len(resultados),
                "resultados": resultados
            }
        )

    print(f"Salvo: {SAIDA_GSM8K}")


if __name__ == "__main__":
    executar_enem(limite=100)
    executar_gsm8k(limite=100)