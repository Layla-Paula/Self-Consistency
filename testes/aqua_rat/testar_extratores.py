from codigo.utils import extrair_letra_resposta, extrair_resposta_numerica

def testar():
    casos_aqua = {
        "A resposta correta é D) $45": "D",
        "A única opção que é igual é C) 12.": "C",
        "Resposta final: B": "B",
        "Alternativa correta: E": "E",
        "Resposta final: Nenhum valor": "",
        "A) 12\nB) 20\nC) 30": "",
    }
    casos_gsm = {
        "Resposta final: 72": "72",
        "Resposta final: 3x/4": "",
        "Resposta final: 12/5": "",
        "48 + 24 = 72": "",
        "Resposta final: 1.234,50": "1.234,50",
    }
    for texto, esperado in casos_aqua.items():
        obtido = extrair_letra_resposta(texto)
        assert obtido == esperado, (texto, esperado, obtido)
    for texto, esperado in casos_gsm.items():
        obtido = extrair_resposta_numerica(texto)
        assert obtido == esperado, (texto, esperado, obtido)
    print("Todos os testes passaram.")

if __name__ == "__main__":
    testar()
