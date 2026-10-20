"""Self-Consistency reutiliza os prompts CoT, inclusive no Censo Escolar."""
from codigo.chain_of_thought.prompts import (
    prompt_cot_gsm8k, prompt_cot_aqua_rat, prompt_cot_censo,
)


def prompt_self_consistency_gsm8k(problema, exemplos):
    return prompt_cot_gsm8k(problema, exemplos)


def prompt_self_consistency_aqua_rat(problema, exemplos):
    return prompt_cot_aqua_rat(problema, exemplos)


def prompt_self_consistency_censo(
    questao, contexto, exemplos, contextos_exemplos, raciocinios_exemplos,
):
    return prompt_cot_censo(
        questao, contexto, exemplos, contextos_exemplos, raciocinios_exemplos,
    )
