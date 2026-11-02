import requests

URL_OLLAMA = "http://localhost:11434/api/generate"
MODELO_OLLAMA = "llama3.2:3b"

try:
    resposta = requests.post(
        URL_OLLAMA,
        json={
            "model": MODELO_OLLAMA,
            "prompt": "Responda apenas o resultado de 25 * 17",
            "stream": False
        },
        timeout=120
    )

    print(f"Status HTTP: {resposta.status_code}")

    resposta.raise_for_status()

    dados = resposta.json()
    print(f"Resposta do modelo: {dados['response']}")

except requests.exceptions.RequestException as erro:
    print(f"Erro na comunicação com o Ollama: {erro}")

    if "resposta" in locals():
        print(f"Detalhes: {resposta.text}")

except KeyError:
    print("O Ollama não retornou o campo 'response'.")
    print(resposta.text)