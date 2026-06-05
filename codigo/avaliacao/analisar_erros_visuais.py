import os
import json
import csv

ARQ_ENEM = "resultados/few_shot/enem_few_shot.json"

SAIDA_JSON = "resultados/metricas/analise_erros_visuais_enem.json"
SAIDA_CSV = "resultados/metricas/analise_erros_visuais_enem.csv"


def carregar_resultados():
    with open(ARQ_ENEM, "r", encoding="utf-8") as f:
        return json.load(f)["resultados"]


def main():
    resultados = carregar_resultados()

    total = len(resultados)
    erros = [r for r in resultados if not r["acertou"]]
    erros_com_imagem = [r for r in erros if r.get("tem_imagem")]
    erros_sem_imagem = [r for r in erros if not r.get("tem_imagem")]

    analise = {
        "total_avaliado": total,
        "total_erros": len(erros),
        "erros_com_imagem": len(erros_com_imagem),
        "erros_sem_imagem": len(erros_sem_imagem),
        "casos": []
    }

    for r in erros:
        caso = {
            "ano": r["ano"],
            "numero": r["numero"],
            "gabarito": r["gabarito"],
            "resposta_modelo": r["resposta_modelo"],
            "tem_imagem": r["tem_imagem"],
            "resposta_completa": r["resposta_completa"],

            # preencher manualmente depois
            "motivo_erro": "",
            "observacao": ""
        }

        analise["casos"].append(caso)

    os.makedirs("resultados/metricas", exist_ok=True)

    with open(SAIDA_JSON, "w", encoding="utf-8") as f:
        json.dump(analise, f, ensure_ascii=False, indent=2)

    with open(SAIDA_CSV, "w", encoding="utf-8", newline="") as f:
        campos = [
            "ano",
            "numero",
            "gabarito",
            "resposta_modelo",
            "tem_imagem",
            "motivo_erro",
            "observacao",
            "resposta_completa"
        ]

        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()

        for caso in analise["casos"]:
            writer.writerow(caso)

    print("Análise salva em:")
    print(SAIDA_JSON)
    print(SAIDA_CSV)

    print()
    print(f"Total avaliado: {total}")
    print(f"Total de erros: {len(erros)}")
    print(f"Erros com imagem: {len(erros_com_imagem)}")
    print(f"Erros sem imagem: {len(erros_sem_imagem)}")


if __name__ == "__main__":
    main()