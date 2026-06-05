import json


ARQ_FEWSHOT_ENEM = (
    "resultados/few_shot/enem_few_shot.json"
)

ARQ_FEWSHOT_GSM8K = (
    "resultados/few_shot/gsm8k_few_shot.json"
)

ARQ_COT_ENEM = (
    "resultados/chain_of_thought/enem_cot.json"
)

ARQ_COT_GSM8K = (
    "resultados/chain_of_thought/gsm8k_cot.json"
)

ARQ_SC_ENEM = (
    "resultados/self_consistency/enem_self_consistency.json"
)

ARQ_SC_GSM8K = (
    "resultados/self_consistency/gsm8k_self_consistency.json"
)


def carregar(path):

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)["resultados"]


def calcular(nome, resultados):

    total = len(resultados)

    acertos = sum(
        1
        for r in resultados
        if r["acertou"]
    )

    erros = total - acertos

    precisao = (
        acertos / total * 100
        if total > 0 else 0
    )

    print()
    print("=" * 60)
    print(nome)
    print("=" * 60)

    print(f"Total     : {total}")
    print(f"Acertos   : {acertos}")
    print(f"Erros     : {erros}")
    print(f"Precisão  : {precisao:.2f}%")

    return precisao


def main():

    fs_enem = carregar(
        ARQ_FEWSHOT_ENEM
    )

    fs_gsm8k = carregar(
        ARQ_FEWSHOT_GSM8K
    )

    cot_enem = carregar(
        ARQ_COT_ENEM
    )

    cot_gsm8k = carregar(
        ARQ_COT_GSM8K
    )

    sc_enem = carregar(
        ARQ_SC_ENEM
    )

    sc_gsm8k = carregar(
        ARQ_SC_GSM8K
    )

    p_fs_enem = calcular(
        "Few-Shot ENEM",
        fs_enem
    )

    p_cot_enem = calcular(
        "Chain-of-Thought ENEM",
        cot_enem
    )

    p_sc_enem = calcular(
        "Self-Consistency ENEM",
        sc_enem
    )

    p_fs_gsm8k = calcular(
        "Few-Shot GSM8K",
        fs_gsm8k
    )

    p_cot_gsm8k = calcular(
        "Chain-of-Thought GSM8K",
        cot_gsm8k
    )

    p_sc_gsm8k = calcular(
        "Self-Consistency GSM8K",
        sc_gsm8k
    )

    print()
    print("=" * 60)
    print("COMPARAÇÃO DAS TÉCNICAS")
    print("=" * 60)

    print()
    print("ENEM")

    print(
        f"Few-Shot          : {p_fs_enem:.2f}%"
    )

    print(
        f"Chain-of-Thought  : {p_cot_enem:.2f}%"
    )

    print(
        f"Self-Consistency  : {p_sc_enem:.2f}%"
    )

    print()
    print("GSM8K")

    print(
        f"Few-Shot          : {p_fs_gsm8k:.2f}%"
    )

    print(
        f"Chain-of-Thought  : {p_cot_gsm8k:.2f}%"
    )

    print(
        f"Self-Consistency  : {p_sc_gsm8k:.2f}%"
    )

    print()
    print("=" * 60)
    print("GANHOS RELATIVOS")
    print("=" * 60)

    print()

    print(
        f"CoT vs Few-Shot (ENEM): "
        f"{p_cot_enem - p_fs_enem:+.2f} p.p."
    )

    print(
        f"SC vs CoT (ENEM): "
        f"{p_sc_enem - p_cot_enem:+.2f} p.p."
    )

    print()

    print(
        f"CoT vs Few-Shot (GSM8K): "
        f"{p_cot_gsm8k - p_fs_gsm8k:+.2f} p.p."
    )

    print(
        f"SC vs CoT (GSM8K): "
        f"{p_sc_gsm8k - p_cot_gsm8k:+.2f} p.p."
    )


if __name__ == "__main__":
    main()