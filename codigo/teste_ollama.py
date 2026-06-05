import json

with open(
    "dados/enem/final/enem_matematica_completo.json",
    encoding="utf-8"
) as f:
    dados = json.load(f)

print(len(dados["questoes"]))

print(dados["questoes"][0].keys())