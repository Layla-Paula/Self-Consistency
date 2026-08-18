from datetime import datetime
from pathlib import Path

from tqdm import tqdm

from codigo.utils import (
    carregar_enem,
    carregar_gsm8k,
    consultar_ollama,
    extrair_letra_resposta,
    extrair_resposta_numerica,
    extrair_gabarito_gsm8k,
    comparar_numeros,
    salvar_json,
)

from codigo.chain_of_thought.prompts import (
    prompt_cot_enem,
    prompt_cot_gsm8k,
)


# ============================================================
# CONFIGURAÇÕES
# ============================================================

METODO = "chain_of_thought"
MODELO = "llama3.2"

PASTA_ENEM = Path(
    "resultados/chain_of_thought/enem"
)

PASTA_GSM8K = Path(
    "resultados/chain_of_thought/gsm8k"
)


# ============================================================
# CRIA IDENTIFICADOR DA EXECUÇÃO
# ============================================================

def criar_id_execucao(dataset, limite, pasta):
    """
    Cria um identificador simples para a execução.

    Formato:

        cot_enem_20260817_100_1

    Onde:

        cot      -> técnica utilizada
        enem     -> dataset
        20260817 -> data da execução
        100      -> quantidade de questões
        1        -> número da execução no mesmo dia
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

    id_execucao = criar_id_execucao(
        dataset="enem",
        limite=limite,
        pasta=PASTA_ENEM
    )

    resultados = []

    print()
    print("=" * 60)
    print("CHAIN-OF-THOUGHT - ENEM")
    print("=" * 60)

    print(f"ID da execução: {id_execucao}")
    print(f"Modelo: {MODELO}")
    print(f"Quantidade: {len(questoes)}")
    print()

    for q in tqdm(
        questoes,
        desc="CoT ENEM"
    ):

        # ----------------------------------------------------
        # Montagem do prompt
        # ----------------------------------------------------

        prompt = prompt_cot_enem(q)

        # ----------------------------------------------------
        # Consulta ao Ollama
        # ----------------------------------------------------

        resposta_completa = consultar_ollama(
            prompt=prompt,
            temperature=0.0,
            num_predict=800
        )

        # ----------------------------------------------------
        # Extração da resposta
        # ----------------------------------------------------

        resposta_modelo = (
            extrair_letra_resposta(
                resposta_completa
            )
        )

        gabarito = q["gabarito"]

        acertou = (
            resposta_modelo == gabarito
        )

        # ----------------------------------------------------
        # Resultado individual
        # ----------------------------------------------------

        item = {
            "numero": q["numero"],
            "ano": q["ano"],
            "gabarito": gabarito,
            "resposta_modelo": resposta_modelo,
            "acertou": acertou,
            "tem_imagem": q.get(
                "tem_imagem",
                False
            ),
            "resposta_completa": (
                resposta_completa
            )
        }

        resultados.append(item)

    # ========================================================
    # MÉTRICAS
    # ========================================================

    total = len(resultados)

    acertos = sum(
        1
        for resultado in resultados
        if resultado["acertou"]
    )

    erros = total - acertos

    precisao = (
        (acertos / total) * 100
        if total > 0
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
            "temperature": 0.0,
            "num_predict": 800,
            "limite": limite
        },

        "resultados": resultados
    }

    # ========================================================
    # SALVAMENTO
    # ========================================================

    PASTA_ENEM.mkdir(
        parents=True,
        exist_ok=True
    )

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
    print(f"Total: {total}")
    print(f"Acertos: {acertos}")
    print(f"Erros: {erros}")
    print(f"Precisão: {precisao:.2f}%")
    print()


# ============================================================
# EXECUÇÃO GSM8K
# ============================================================

def executar_gsm8k(limite=None):

    problemas = carregar_gsm8k()

    if limite is not None:
        problemas = problemas[:limite]

    id_execucao = criar_id_execucao(
        dataset="gsm8k",
        limite=limite,
        pasta=PASTA_GSM8K
    )

    resultados = []

    print()
    print("=" * 60)
    print("CHAIN-OF-THOUGHT - GSM8K")
    print("=" * 60)

    print(f"ID da execução: {id_execucao}")
    print(f"Modelo: {MODELO}")
    print(f"Quantidade: {len(problemas)}")
    print()

    for i, p in enumerate(
        tqdm(
            problemas,
            desc="CoT GSM8K"
        )
    ):

        # ----------------------------------------------------
        # Montagem do prompt
        # ----------------------------------------------------

        prompt = prompt_cot_gsm8k(p)

        # ----------------------------------------------------
        # Consulta ao Ollama
        # ----------------------------------------------------

        resposta_completa = consultar_ollama(
            prompt=prompt,
            temperature=0.0,
            num_predict=800
        )

        # ----------------------------------------------------
        # Extração
        # ----------------------------------------------------

        resposta_modelo = (
            extrair_resposta_numerica(
                resposta_completa
            )
        )

        gabarito = (
            extrair_gabarito_gsm8k(p)
        )

        acertou = comparar_numeros(
            resposta_modelo,
            gabarito
        )

        # ----------------------------------------------------
        # Resultado individual
        # ----------------------------------------------------

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

            "resposta_modelo": resposta_modelo,

            "acertou": acertou,

            "resposta_completa": (
                resposta_completa
            )
        }

        resultados.append(item)

    # ========================================================
    # MÉTRICAS
    # ========================================================

    total = len(resultados)

    acertos = sum(
        1
        for resultado in resultados
        if resultado["acertou"]
    )

    erros = total - acertos

    precisao = (
        (acertos / total) * 100
        if total > 0
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
            "temperature": 0.0,
            "num_predict": 800,
            "limite": limite
        },

        "resultados": resultados
    }

    # ========================================================
    # SALVAMENTO
    # ========================================================

    PASTA_GSM8K.mkdir(
        parents=True,
        exist_ok=True
    )

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


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

if __name__ == "__main__":

    executar_enem(
        limite=100
    )

    executar_gsm8k(
        limite=100
    )