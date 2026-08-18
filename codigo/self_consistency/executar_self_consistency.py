from datetime import datetime
from pathlib import Path

from tqdm import tqdm

from codigo.utils import (
    carregar_enem,
    carregar_gsm8k,
    extrair_letra_resposta,
    extrair_resposta_numerica,
    extrair_gabarito_gsm8k,
    comparar_numeros,
    salvar_json,
)

from codigo.self_consistency.prompts import (
    prompt_self_consistency_enem,
    prompt_self_consistency_gsm8k,
)

from codigo.self_consistency.experimentos import (
    executar_experimento_self_consistency,
)


# ============================================================
# CONFIGURAÇÕES
# ============================================================

METODO = "self_consistency"
MODELO = "llama3.2"

N_AMOSTRAS = 5
TEMPERATURE = 0.7
NUM_PREDICT = 800

PASTA_ENEM = Path(
    "resultados/self_consistency/enem"
)

PASTA_GSM8K = Path(
    "resultados/self_consistency/gsm8k"
)


# ============================================================
# IDENTIFICAÇÃO DA EXECUÇÃO
# ============================================================

def criar_id_execucao(dataset, limite, pasta):
    """
    Exemplos:

    self_consistency_enem_20260817_100_1
    self_consistency_enem_20260817_100_2

    self_consistency_gsm8k_20260817_100_1
    """

    data = datetime.now().strftime("%Y%m%d")

    limite_nome = (
        str(limite)
        if limite is not None
        else "todos"
    )

    prefixo = (
        f"{METODO}_{dataset}_{data}_{limite_nome}_"
    )

    pasta.mkdir(
        parents=True,
        exist_ok=True
    )

    numero_execucao = 1

    while True:

        id_execucao = (
            f"{prefixo}{numero_execucao}"
        )

        caminho = (
            pasta / f"{id_execucao}.json"
        )

        if not caminho.exists():
            return id_execucao

        numero_execucao += 1


# ============================================================
# EXECUÇÃO ENEM
# ============================================================

def executar_enem(limite=None):

    questoes = carregar_enem()

    if limite is not None:
        questoes = questoes[:limite]

    total_selecionado = len(questoes)

    id_execucao = criar_id_execucao(
        dataset="enem",
        limite=total_selecionado,
        pasta=PASTA_ENEM
    )

    resultados = []

    print()
    print("=" * 60)
    print("SELF-CONSISTENCY - ENEM")
    print("=" * 60)

    print(f"ID da execução: {id_execucao}")
    print(f"Modelo: {MODELO}")
    print(f"Quantidade: {total_selecionado}")
    print(f"Amostras por questão: {N_AMOSTRAS}")
    print(f"Temperature: {TEMPERATURE}")
    print()

    for q in tqdm(
        questoes,
        desc="Self-Consistency ENEM"
    ):

        prompt = (
            prompt_self_consistency_enem(q)
        )

        resultado_sc = (
            executar_experimento_self_consistency(
                prompt=prompt,
                extrair_resposta=extrair_letra_resposta,
                n_amostras=N_AMOSTRAS,
                temperature=TEMPERATURE,
                num_predict=NUM_PREDICT
            )
        )

        gabarito = q["gabarito"]

        resposta_modelo = (
            resultado_sc["resposta_modelo"]
        )

        acertou = (
            resposta_modelo == gabarito
        )

        item = {
            "ano": q["ano"],
            "numero": q["numero"],
            "gabarito": gabarito,
            "tem_imagem": q.get(
                "tem_imagem",
                False
            ),

            "respostas_extraidas": (
                resultado_sc[
                    "respostas_extraidas"
                ]
            ),

            "distribuicao_votos": (
                resultado_sc[
                    "distribuicao_votos"
                ]
            ),

            "resposta_modelo": resposta_modelo,

            "votos_resposta_modelo": (
                resultado_sc[
                    "votos_resposta_modelo"
                ]
            ),

            "houve_empate": (
                resultado_sc[
                    "houve_empate"
                ]
            ),

            "acertou": acertou,

            "amostras": (
                resultado_sc["amostras"]
            )
        }

        resultados.append(item)

    # ========================================================
    # MÉTRICAS
    # ========================================================

    total = len(resultados)

    acertos = sum(
        1
        for r in resultados
        if r["acertou"]
    )

    erros = total - acertos

    precisao = (
        acertos / total * 100
        if total > 0
        else 0
    )

    # --------------------------------------------------------
    # MÉTRICAS DE VOTAÇÃO
    # --------------------------------------------------------

    unanimidades = sum(
        1
        for r in resultados
        if r["votos_resposta_modelo"]
        == N_AMOSTRAS
    )

    maioria_4 = sum(
        1
        for r in resultados
        if r["votos_resposta_modelo"] == 4
    )

    maioria_3 = sum(
        1
        for r in resultados
        if r["votos_resposta_modelo"] == 3
    )

    empates = sum(
        1
        for r in resultados
        if r["houve_empate"]
    )

    media_votos = (
        sum(
            r["votos_resposta_modelo"]
            for r in resultados
        )
        / total
        if total > 0
        else 0
    )

    # --------------------------------------------------------
    # MÉTRICAS VISUAIS ENEM
    # --------------------------------------------------------

    com_imagem = [
        r
        for r in resultados
        if r["tem_imagem"]
    ]

    sem_imagem = [
        r
        for r in resultados
        if not r["tem_imagem"]
    ]

    acertos_com_imagem = sum(
        1
        for r in com_imagem
        if r["acertou"]
    )

    acertos_sem_imagem = sum(
        1
        for r in sem_imagem
        if r["acertou"]
    )

    precisao_com_imagem = (
        acertos_com_imagem
        / len(com_imagem)
        * 100
        if com_imagem
        else 0
    )

    precisao_sem_imagem = (
        acertos_sem_imagem
        / len(sem_imagem)
        * 100
        if sem_imagem
        else 0
    )

    # ========================================================
    # DADOS DA EXECUÇÃO
    # ========================================================

    dados = {
        "id_execucao": id_execucao,

        "data_execucao": datetime.now().isoformat(
            timespec="seconds"
        ),

        "metodo": METODO,

        "dataset": "enem",

        "modelo": MODELO,

        "total": total,

        "acertos": acertos,

        "erros": erros,

        "precisao": round(
            precisao,
            2
        ),

        "parametros": {
            "n_amostras": N_AMOSTRAS,
            "temperature": TEMPERATURE,
            "num_predict": NUM_PREDICT,
            "limite": limite
        },

        "metricas_votacao": {
            "unanimidades": unanimidades,
            "maioria_4_de_5": maioria_4,
            "maioria_3_de_5": maioria_3,
            "empates": empates,
            "media_votos_vencedor": round(
                media_votos,
                2
            )
        },

        "metricas_visuais": {
            "total_com_imagem": len(
                com_imagem
            ),
            "acertos_com_imagem": (
                acertos_com_imagem
            ),
            "precisao_com_imagem": round(
                precisao_com_imagem,
                2
            ),

            "total_sem_imagem": len(
                sem_imagem
            ),
            "acertos_sem_imagem": (
                acertos_sem_imagem
            ),
            "precisao_sem_imagem": round(
                precisao_sem_imagem,
                2
            )
        },

        "resultados": resultados
    }

    # ========================================================
    # SALVAMENTO
    # ========================================================

    caminho = (
        PASTA_ENEM
        / f"{id_execucao}.json"
    )

    salvar_json(
        str(caminho),
        dados
    )

    # ========================================================
    # RESUMO
    # ========================================================

    print()
    print(f"Salvo: {caminho}")

    print()
    print("RESULTADO")
    print(f"Total: {total}")
    print(f"Acertos: {acertos}")
    print(f"Erros: {erros}")
    print(f"Precisão: {precisao:.2f}%")

    print()
    print("VOTAÇÃO")
    print(f"Unanimidades: {unanimidades}")
    print(f"Maioria 4/5: {maioria_4}")
    print(f"Maioria 3/5: {maioria_3}")
    print(f"Empates: {empates}")
    print(
        f"Média de votos vencedores: "
        f"{media_votos:.2f}"
    )

    print()
    print("QUESTÕES COM IMAGEM")
    print(f"Total: {len(com_imagem)}")
    print(
        f"Acertos: "
        f"{acertos_com_imagem}"
    )
    print(
        f"Precisão: "
        f"{precisao_com_imagem:.2f}%"
    )

    print()
    print("QUESTÕES SEM IMAGEM")
    print(f"Total: {len(sem_imagem)}")
    print(
        f"Acertos: "
        f"{acertos_sem_imagem}"
    )
    print(
        f"Precisão: "
        f"{precisao_sem_imagem:.2f}%"
    )
    print()


# ============================================================
# EXECUÇÃO GSM8K
# ============================================================

def executar_gsm8k(limite=None):

    problemas = carregar_gsm8k()

    if limite is not None:
        problemas = problemas[:limite]

    total_selecionado = len(problemas)

    id_execucao = criar_id_execucao(
        dataset="gsm8k",
        limite=total_selecionado,
        pasta=PASTA_GSM8K
    )

    resultados = []

    print()
    print("=" * 60)
    print("SELF-CONSISTENCY - GSM8K")
    print("=" * 60)

    print(f"ID da execução: {id_execucao}")
    print(f"Modelo: {MODELO}")
    print(f"Quantidade: {total_selecionado}")
    print(f"Amostras por questão: {N_AMOSTRAS}")
    print(f"Temperature: {TEMPERATURE}")
    print()

    for i, p in enumerate(
        tqdm(
            problemas,
            desc="Self-Consistency GSM8K"
        )
    ):

        prompt = (
            prompt_self_consistency_gsm8k(p)
        )

        resultado_sc = (
            executar_experimento_self_consistency(
                prompt=prompt,
                extrair_resposta=(
                    extrair_resposta_numerica
                ),
                n_amostras=N_AMOSTRAS,
                temperature=TEMPERATURE,
                num_predict=NUM_PREDICT
            )
        )

        gabarito = (
            extrair_gabarito_gsm8k(p)
        )

        resposta_modelo = (
            resultado_sc["resposta_modelo"]
        )

        acertou = comparar_numeros(
            resposta_modelo,
            gabarito
        )

        item = {
            "id": p.get(
                "id",
                i
            ),

            "split": p.get(
                "split",
                ""
            ),

            "gabarito": gabarito,

            "respostas_extraidas": (
                resultado_sc[
                    "respostas_extraidas"
                ]
            ),

            "distribuicao_votos": (
                resultado_sc[
                    "distribuicao_votos"
                ]
            ),

            "resposta_modelo": resposta_modelo,

            "votos_resposta_modelo": (
                resultado_sc[
                    "votos_resposta_modelo"
                ]
            ),

            "houve_empate": (
                resultado_sc[
                    "houve_empate"
                ]
            ),

            "acertou": acertou,

            "amostras": (
                resultado_sc["amostras"]
            )
        }

        resultados.append(item)

    # ========================================================
    # MÉTRICAS
    # ========================================================

    total = len(resultados)

    acertos = sum(
        1
        for r in resultados
        if r["acertou"]
    )

    erros = total - acertos

    precisao = (
        acertos / total * 100
        if total > 0
        else 0
    )

    unanimidades = sum(
        1
        for r in resultados
        if r["votos_resposta_modelo"]
        == N_AMOSTRAS
    )

    maioria_4 = sum(
        1
        for r in resultados
        if r["votos_resposta_modelo"] == 4
    )

    maioria_3 = sum(
        1
        for r in resultados
        if r["votos_resposta_modelo"] == 3
    )

    empates = sum(
        1
        for r in resultados
        if r["houve_empate"]
    )

    media_votos = (
        sum(
            r["votos_resposta_modelo"]
            for r in resultados
        )
        / total
        if total > 0
        else 0
    )

    # ========================================================
    # DADOS
    # ========================================================

    dados = {
        "id_execucao": id_execucao,

        "data_execucao": datetime.now().isoformat(
            timespec="seconds"
        ),

        "metodo": METODO,

        "dataset": "gsm8k",

        "modelo": MODELO,

        "total": total,

        "acertos": acertos,

        "erros": erros,

        "precisao": round(
            precisao,
            2
        ),

        "parametros": {
            "n_amostras": N_AMOSTRAS,
            "temperature": TEMPERATURE,
            "num_predict": NUM_PREDICT,
            "limite": limite
        },

        "metricas_votacao": {
            "unanimidades": unanimidades,
            "maioria_4_de_5": maioria_4,
            "maioria_3_de_5": maioria_3,
            "empates": empates,
            "media_votos_vencedor": round(
                media_votos,
                2
            )
        },

        "resultados": resultados
    }

    # ========================================================
    # SALVAMENTO
    # ========================================================

    caminho = (
        PASTA_GSM8K
        / f"{id_execucao}.json"
    )

    salvar_json(
        str(caminho),
        dados
    )

    # ========================================================
    # RESUMO
    # ========================================================

    print()
    print(f"Salvo: {caminho}")
    print(f"Total: {total}")
    print(f"Acertos: {acertos}")
    print(f"Erros: {erros}")
    print(f"Precisão: {precisao:.2f}%")

    print()
    print("VOTAÇÃO")
    print(f"Unanimidades: {unanimidades}")
    print(f"Maioria 4/5: {maioria_4}")
    print(f"Maioria 3/5: {maioria_3}")
    print(f"Empates: {empates}")
    print(
        f"Média de votos vencedores: "
        f"{media_votos:.2f}"
    )

    print()


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

if __name__ == "__main__":

    executar_enem(
        limite=500
    )

    executar_gsm8k(
        limite=500
    )