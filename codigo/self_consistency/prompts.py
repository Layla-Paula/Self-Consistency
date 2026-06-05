from codigo.chain_of_thought.prompts import (
    prompt_cot_enem,
    prompt_cot_gsm8k
)


def prompt_self_consistency_enem(questao):
    return prompt_cot_enem(questao)


def prompt_self_consistency_gsm8k(problema):
    return prompt_cot_gsm8k(problema)