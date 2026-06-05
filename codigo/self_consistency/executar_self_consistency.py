from tqdm import tqdm

from codigo.utils import (
    carregar_enem,
    carregar_gsm8k,
    extrair_letra_resposta,
    extrair_resposta_numerica,
    extrair_gabarito_gsm8k,
    comparar_numeros,
    salvar_json
)

from codigo.self_consistency.prompts import (
    prompt_self_consistency_enem,
    prompt_self_consistency_gsm8k
)

from codigo.self_consistency.experimentos import (
    executar_experimento_self_consistency
)


SAIDA_ENEM = "resultados/self_consistency/enem_self_consistency.json"
SAIDA_GSM8K = "resultados/self_consistency/gsm8k_self_consistency.json"

N_AMOSTRAS = 5
TEMPERATURE = 0.7
NUM_PREDICT = 800


def executar_enem(limite=20):
    questoes = carregar_enem()

    if limite:
        questoes = questoes[:limite]

    resultados = []

    for q in tqdm(questoes, desc="Self-Consistency ENEM"):
        prompt = prompt_self_consistency_enem(q)

        resultado_sc = executar_experimento_self_consistency(
            prompt=prompt,
            extrair_resposta=extrair_letra_resposta,
            n_amostras=N_AMOSTRAS,
            temperature=TEMPERATURE,
            num_predict=NUM_PREDICT
        )

        item = {
            "metodo": "self_consistency",
            "dataset": "enem",
            "modelo": "llama3.2",
            "n_amostras": N_AMOSTRAS,
            "temperature": TEMPERATURE,
            "ano": q["ano"],
            "numero": q["numero"],
            "gabarito": q["gabarito"],
            "tem_imagem": q.get("tem_imagem", False),
            **resultado_sc,
            "acertou": resultado_sc["resposta_modelo"] == q["gabarito"]
        }

        resultados.append(item)

        salvar_json(
            SAIDA_ENEM,
            {
                "metodo": "self_consistency",
                "dataset": "enem",
                "modelo": "llama3.2",
                "n_amostras": N_AMOSTRAS,
                "temperature": TEMPERATURE,
                "total": len(resultados),
                "resultados": resultados
            }
        )

    print(f"Salvo: {SAIDA_ENEM}")


def executar_gsm8k(limite=20):
    problemas = carregar_gsm8k()

    if limite:
        problemas = problemas[:limite]

    resultados = []

    for i, p in enumerate(tqdm(problemas, desc="Self-Consistency GSM8K")):
        prompt = prompt_self_consistency_gsm8k(p)

        resultado_sc = executar_experimento_self_consistency(
            prompt=prompt,
            extrair_resposta=extrair_resposta_numerica,
            n_amostras=N_AMOSTRAS,
            temperature=TEMPERATURE,
            num_predict=NUM_PREDICT
        )

        gabarito = extrair_gabarito_gsm8k(p)

        item = {
            "metodo": "self_consistency",
            "dataset": "gsm8k",
            "modelo": "llama3.2",
            "n_amostras": N_AMOSTRAS,
            "temperature": TEMPERATURE,
            "id": p.get("id", i),
            "split": p.get("split", ""),
            "gabarito": gabarito,
            **resultado_sc,
            "acertou": comparar_numeros(
                resultado_sc["resposta_modelo"],
                gabarito
            )
        }

        resultados.append(item)

        salvar_json(
            SAIDA_GSM8K,
            {
                "metodo": "self_consistency",
                "dataset": "gsm8k",
                "modelo": "llama3.2",
                "n_amostras": N_AMOSTRAS,
                "temperature": TEMPERATURE,
                "total": len(resultados),
                "resultados": resultados
            }
        )

    print(f"Salvo: {SAIDA_GSM8K}")


if __name__ == "__main__":
    executar_enem(limite=100)
    executar_gsm8k(limite=100)