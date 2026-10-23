
"""Teste rápido da conexão Ollama, sem avaliar datasets nem alterar resultados."""

from codigo.utils import consultar_ollama, MODELO_OLLAMA, SEMENTE_OLLAMA


def main():
    print(f"Modelo: {MODELO_OLLAMA} | seed: {SEMENTE_OLLAMA}")

    resultado = consultar_ollama(
        "Responda apenas: OK",
        temperature=0.0,
        num_predict=32,
        retornar_metricas=True
    )

    print("Resposta:", resultado.get("resposta"))
    print("Erro:", resultado.get("erro_detalhado"))
    print("Tokens:", resultado.get("prompt_eval_count"), resultado.get("eval_count"))

    if resultado.get("resposta") is None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
