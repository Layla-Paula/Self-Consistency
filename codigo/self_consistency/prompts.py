
#importa os prompts da técnica CoT, pois a self_consistency parte dela
from codigo.chain_of_thought.prompts import (
    prompt_cot_enem,
    prompt_cot_gsm8k,
)



# SELF-CONSISTENCY - ENEM

#recebe uma questão do enem
def prompt_self_consistency_enem(
    questao
):

    return prompt_cot_enem(
        questao
    )



# SELF-CONSISTENCY - GSM8K


def prompt_self_consistency_gsm8k(
    problema
):

    return prompt_cot_gsm8k(
        problema
    )