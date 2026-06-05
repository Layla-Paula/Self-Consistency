import requests

r = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3.2",
        "prompt": "Responda apenas o resultado de 25 * 17",
        "stream": False
    },
    timeout=120
)

print(r.status_code)
print(r.json()["response"])