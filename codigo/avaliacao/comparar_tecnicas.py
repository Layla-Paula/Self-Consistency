import json
from pathlib import Path



# PASTAS DOS EXPERIMENTOS


PASTAS = {
    "few_shot": {
        "enem": Path(
            "resultados/few_shot/enem"
        ),

        "gsm8k": Path(
            "resultados/few_shot/gsm8k"
        ),
    },

    "chain_of_thought": {
        "enem": Path(
            "resultados/chain_of_thought/enem"
        ),

        "gsm8k": Path(
            "resultados/chain_of_thought/gsm8k"
        ),
    },

    "self_consistency": {
        "enem": Path(
            "resultados/self_consistency/enem"
        ),

        "gsm8k": Path(
            "resultados/self_consistency/gsm8k"
        ),
    },
}


PASTA_METRICAS = Path(
    "resultados/metricas"
)

SAIDA_JSON = (
    PASTA_METRICAS
    / "historico_execucoes.json"
)



# CARREGAMENTO


def carregar_execucao(
    caminho,
    metodo,
    dataset
):

    try:

        with open(
            caminho,
            "r",
            encoding="utf-8"
        ) as f:

            dados = json.load(f)

        resultados = dados.get(
            "resultados",
            []
        )

        total = len(resultados)

        acertos = sum(
            1
            for r in resultados
            if r.get("acertou", False)
        )

        erros = total - acertos

        precisao = (
            acertos / total * 100
            if total > 0
            else 0
        )

        parametros = dados.get(
            "parametros",
            {}
        )

        return {
            "id_execucao": dados.get(
                "id_execucao",
                caminho.stem
            ),

            "arquivo": caminho.name,

            "data_execucao": dados.get(
                "data_execucao",
                ""
            ),

            "metodo": dados.get(
                "metodo",
                metodo
            ),

            "dataset": dados.get(
                "dataset",
                dataset
            ),

            "modelo": dados.get(
                "modelo",
                ""
            ),

            "total": total,

            "acertos": acertos,

            "erros": erros,

            "precisao": round(
                precisao,
                2
            ),

            "limite": parametros.get(
                "limite",
                total
            ),

            "temperature": parametros.get(
                "temperature",
                ""
            ),

            "num_predict": parametros.get(
                "num_predict",
                ""
            ),

            "n_amostras": parametros.get(
                "n_amostras",
                ""
            ),

            "prompt_versao": dados.get(
                "prompt_versao",
                ""
            )
        }

    except Exception as e:

        print(
            f"Erro em {caminho}: {e}"
        )

        return None



# CARREGAR HISTÓRICO COMPLETO


def carregar_historico():

    historico = []

    for metodo, datasets in PASTAS.items():

        for dataset, pasta in datasets.items():

            if not pasta.exists():
                continue

            arquivos = sorted(
                pasta.glob("*.json")
            )

            for arquivo in arquivos:

                execucao = carregar_execucao(
                    arquivo,
                    metodo,
                    dataset
                )

                if execucao:
                    historico.append(
                        execucao
                    )

    return historico



# EXIBIR HISTÓRICO


def exibir_historico(historico):

    print()
    print("=" * 100)
    print("HISTÓRICO DE EXPERIMENTOS")
    print("=" * 100)

    for execucao in historico:

        print()

        print(
            f"ID: {execucao['id_execucao']}"
        )

        print(
            f"  Método     : "
            f"{execucao['metodo']}"
        )

        print(
            f"  Dataset    : "
            f"{execucao['dataset']}"
        )

        print(
            f"  Modelo     : "
            f"{execucao['modelo']}"
        )

        print(
            f"  Total      : "
            f"{execucao['total']}"
        )

        print(
            f"  Acertos    : "
            f"{execucao['acertos']}"
        )

        print(
            f"  Erros      : "
            f"{execucao['erros']}"
        )

        print(
            f"  Precisão   : "
            f"{execucao['precisao']:.2f}%"
        )



# AGRUPAMENTO PARA COMPARAÇÃO


def agrupar_por_dataset_total(
    historico
):

    grupos = {}

    for execucao in historico:

        chave = (
            execucao["dataset"],
            execucao["total"]
        )

        if chave not in grupos:
            grupos[chave] = []

        grupos[chave].append(
            execucao
        )

    return grupos



# COMPARAÇÕES


def exibir_comparacoes(
    historico
):

    grupos = agrupar_por_dataset_total(
        historico
    )

    print()
    print("=" * 100)
    print("COMPARAÇÕES POR TAMANHO DA AMOSTRA")
    print("=" * 100)

    for (
        dataset,
        total
    ), execucoes in sorted(
        grupos.items()
    ):

        metodos_presentes = set(
            e["metodo"]
            for e in execucoes
        )

        # Só mostra comparação quando houver
        # pelo menos duas técnicas
        if len(metodos_presentes) < 2:
            continue

        print()
        print(
            f"{dataset.upper()} "
            f"- {total} questões"
        )

        print("-" * 60)

        for execucao in execucoes:

            print(
                f"{execucao['metodo']:<22} "
                f"{execucao['precisao']:>6.2f}% "
                f"| "
                f"{execucao['acertos']}/"
                f"{execucao['total']} "
                f"| "
                f"{execucao['id_execucao']}"
            )



# SALVAR HISTÓRICO


def salvar_historico(
    historico
):

    PASTA_METRICAS.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        SAIDA_JSON,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "total_execucoes": (
                    len(historico)
                ),
                "execucoes": historico
            },
            f,
            ensure_ascii=False,
            indent=2
        )



# MAIN


def main():

    historico = carregar_historico()

    salvar_historico(
        historico
    )

    exibir_historico(
        historico
    )

    exibir_comparacoes(
        historico
    )

    print()
    print("=" * 100)

    print(
        f"Histórico salvo em: "
        f"{SAIDA_JSON}"
    )


if __name__ == "__main__":
    main()