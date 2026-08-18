import json
import csv
from pathlib import Path


# ============================================================
# CONFIGURAÇÕES
# ============================================================

PASTAS_ENEM = {
    "few_shot": Path(
        "resultados/few_shot/enem"
    ),
    "chain_of_thought": Path(
        "resultados/chain_of_thought/enem"
    ),
    "self_consistency": Path(
        "resultados/self_consistency/enem"
    ),
}


PASTA_SAIDA = Path(
    "resultados/metricas"
)

SAIDA_JSON = (
    PASTA_SAIDA
    / "analise_erros_visuais_enem.json"
)

SAIDA_CSV = (
    PASTA_SAIDA
    / "analise_erros_visuais_enem.csv"
)


# ============================================================
# CARREGAR EXECUÇÕES
# ============================================================

def carregar_execucoes():

    execucoes = []

    for metodo, pasta in PASTAS_ENEM.items():

        if not pasta.exists():
            continue

        arquivos = sorted(
            pasta.glob("*.json")
        )

        for caminho in arquivos:

            try:

                with open(
                    caminho,
                    "r",
                    encoding="utf-8"
                ) as f:

                    dados = json.load(f)

                execucoes.append(
                    {
                        "arquivo": caminho.name,
                        "caminho": str(caminho),
                        "metodo": metodo,
                        "dados": dados
                    }
                )

            except Exception as e:

                print(
                    f"Erro ao carregar "
                    f"{caminho}: {e}"
                )

    return execucoes


# ============================================================
# ANALISAR
# ============================================================

def analisar():

    execucoes = carregar_execucoes()

    casos = []

    resumo_execucoes = []

    for execucao in execucoes:

        dados = execucao["dados"]

        resultados = dados.get(
            "resultados",
            []
        )

        erros = [
            r
            for r in resultados
            if not r.get("acertou", False)
        ]

        erros_com_imagem = [
            r
            for r in erros
            if r.get("tem_imagem", False)
        ]

        erros_sem_imagem = [
            r
            for r in erros
            if not r.get("tem_imagem", False)
        ]

        total_com_imagem = sum(
            1
            for r in resultados
            if r.get("tem_imagem", False)
        )

        total_sem_imagem = (
            len(resultados)
            - total_com_imagem
        )

        acertos_com_imagem = sum(
            1
            for r in resultados
            if (
                r.get("tem_imagem", False)
                and r.get("acertou", False)
            )
        )

        acertos_sem_imagem = sum(
            1
            for r in resultados
            if (
                not r.get(
                    "tem_imagem",
                    False
                )
                and r.get(
                    "acertou",
                    False
                )
            )
        )

        precisao_com_imagem = (
            acertos_com_imagem
            / total_com_imagem
            * 100
            if total_com_imagem > 0
            else 0
        )

        precisao_sem_imagem = (
            acertos_sem_imagem
            / total_sem_imagem
            * 100
            if total_sem_imagem > 0
            else 0
        )

        resumo_execucoes.append(
            {
                "id_execucao": dados.get(
                    "id_execucao",
                    execucao["arquivo"]
                ),

                "data_execucao": dados.get(
                    "data_execucao",
                    ""
                ),

                "metodo": dados.get(
                    "metodo",
                    execucao["metodo"]
                ),

                "modelo": dados.get(
                    "modelo",
                    ""
                ),

                "total": len(resultados),

                "total_erros": len(erros),

                "erros_com_imagem": len(
                    erros_com_imagem
                ),

                "erros_sem_imagem": len(
                    erros_sem_imagem
                ),

                "total_com_imagem": (
                    total_com_imagem
                ),

                "acertos_com_imagem": (
                    acertos_com_imagem
                ),

                "precisao_com_imagem": round(
                    precisao_com_imagem,
                    2
                ),

                "total_sem_imagem": (
                    total_sem_imagem
                ),

                "acertos_sem_imagem": (
                    acertos_sem_imagem
                ),

                "precisao_sem_imagem": round(
                    precisao_sem_imagem,
                    2
                )
            }
        )

        # ----------------------------------------------------
        # CASOS INDIVIDUAIS DE ERRO
        # ----------------------------------------------------

        for r in erros:

            caso = {
                "id_execucao": dados.get(
                    "id_execucao",
                    execucao["arquivo"]
                ),

                "data_execucao": dados.get(
                    "data_execucao",
                    ""
                ),

                "metodo": dados.get(
                    "metodo",
                    execucao["metodo"]
                ),

                "modelo": dados.get(
                    "modelo",
                    ""
                ),

                "ano": r.get(
                    "ano",
                    ""
                ),

                "numero": r.get(
                    "numero",
                    ""
                ),

                "gabarito": r.get(
                    "gabarito",
                    ""
                ),

                "resposta_modelo": r.get(
                    "resposta_modelo",
                    ""
                ),

                "tem_imagem": r.get(
                    "tem_imagem",
                    False
                ),

                # preencher manualmente
                "motivo_erro": "",

                "observacao": "",

                "resposta_completa": r.get(
                    "resposta_completa",
                    ""
                )
            }

            casos.append(caso)

    return {
        "total_execucoes": len(execucoes),
        "resumo_execucoes": resumo_execucoes,
        "casos": casos
    }


# ============================================================
# SALVAR
# ============================================================

def salvar(analise):

    PASTA_SAIDA.mkdir(
        parents=True,
        exist_ok=True
    )

    # JSON
    with open(
        SAIDA_JSON,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            analise,
            f,
            ensure_ascii=False,
            indent=2
        )

    # CSV
    campos = [
        "id_execucao",
        "data_execucao",
        "metodo",
        "modelo",
        "ano",
        "numero",
        "gabarito",
        "resposta_modelo",
        "tem_imagem",
        "motivo_erro",
        "observacao",
        "resposta_completa",
    ]

    with open(
        SAIDA_CSV,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=campos
        )

        writer.writeheader()

        for caso in analise["casos"]:
            writer.writerow(caso)


# ============================================================
# MAIN
# ============================================================

def main():

    analise = analisar()

    salvar(analise)

    print()
    print("=" * 60)
    print("ANÁLISE DE ERROS VISUAIS - ENEM")
    print("=" * 60)

    print(
        f"Execuções encontradas: "
        f"{analise['total_execucoes']}"
    )

    print()

    for resumo in analise[
        "resumo_execucoes"
    ]:

        print(
            f"{resumo['id_execucao']}"
        )

        print(
            f"  Método: "
            f"{resumo['metodo']}"
        )

        print(
            f"  Total: "
            f"{resumo['total']}"
        )

        print(
            f"  Erros: "
            f"{resumo['total_erros']}"
        )

        print(
            f"  Com imagem: "
            f"{resumo['acertos_com_imagem']}/"
            f"{resumo['total_com_imagem']} "
            f"("
            f"{resumo['precisao_com_imagem']:.2f}%"
            f")"
        )

        print(
            f"  Sem imagem: "
            f"{resumo['acertos_sem_imagem']}/"
            f"{resumo['total_sem_imagem']} "
            f"("
            f"{resumo['precisao_sem_imagem']:.2f}%"
            f")"
        )

        print()

    print("Arquivos:")
    print(SAIDA_JSON)
    print(SAIDA_CSV)


if __name__ == "__main__":
    main()