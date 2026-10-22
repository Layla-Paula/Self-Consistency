"""Execução Few-shot: GSM8K, AQuA-RAT e Censo Escolar.
"""
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
from codigo.protocolo_experimentos import (
    selecionar_exemplos_comuns, pasta_configuracao, novo_nome, resumo_protocolo,
    N_EXEMPLOS_PADRAO, ordem_exemplos_censo,
    USAR_LIMITE_PADRAO, resolver_limite
)
import re
import unicodedata
from codigo.utils import (
    carregar_gsm8k, carregar_aqua_rat, carregar_censo, consultar_ollama,
    extrair_gabarito_gsm8k, extrair_gabarito_aqua_rat,
    extrair_gabarito_censo, extrair_resposta_numerica,
    extrair_letra_resposta, comparar_numeros,
    montar_questao_gsm8k, montar_questao_aqua_rat,
)
from codigo.few_shot.prompts import (
    prompt_few_shot_gsm8k, prompt_few_shot_aqua_rat,
    prompt_few_shot_censo,
)
try:
    import psutil
except ImportError:
    psutil = None
MODELO = "llama3.2"
TEMPERATURE = 0.0
NUM_PREDICT = 800
SALVAR_CADA = 10
PASTA_BASE = Path("resultados/few_shot")
# Faixas temáticas das 50 questões do Censo (posições no JSON).
# A seleção é automática, determinística e alterna entre os seis blocos.
# Avaliação do Censo incorporada: este arquivo não depende de revisao_censo.py.
from codigo.avaliacao.avaliacao_censo import avaliar_censo

def agora():
    return datetime.now().isoformat(timespec="seconds")
def salvar(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)
def selecionar_exemplos(dataset, registros, quantidade):
    return selecionar_exemplos_comuns(dataset, registros, quantidade)

def metricas(resultados, tempo_total, quantidade, dataset):
    validos = [r for r in resultados if not r.get("falha_tecnica", False)]
    avaliadas = [r for r in validos if isinstance(r.get("acertou"), bool)]
    tempos = [r["tempo_segundos"] for r in validos]

    def acuracia(itens):
        return round(100 * sum(r["acertou"] for r in itens) / len(itens), 2) if itens else None

    def media(chave):
        valores = [r[chave] for r in validos if isinstance(r.get(chave), (int, float))]
        return round(statistics.mean(valores), 2) if valores else None

    def resumo(itens):
        return {
            "questoes": len(itens),
            "acertos": sum(r["acertou"] for r in itens),
            "erros": sum(not r["acertou"] for r in itens),
            "acuracia_percentual": acuracia(itens),
        }

    por_split = {}
    if dataset != "censo":
        for split in ("train", "validation", "test"):
            itens = [r for r in avaliadas if r.get("split") == split]
            if itens:
                por_split[split] = resumo(itens)

    return {
        "exemplos_utilizados": quantidade,
        "questoes_executadas": len(resultados),
        "questoes_avaliadas": len(avaliadas),
        "acertos": sum(r["acertou"] for r in avaliadas),
        "erros": sum(not r["acertou"] for r in avaliadas),
        "falhas_tecnicas": sum(bool(r.get("falha_tecnica", False)) for r in resultados),
        "detalhes_falhas_tecnicas": [
            {
                "id": r["id"],
                "motivo": r.get("motivo"),
                "tentativas": r.get("tentativas_consulta"),
            }
            for r in resultados if r.get("falha_tecnica", False)
        ],
        "acuracia_percentual": acuracia(avaliadas),
        "acuracia_por_split": por_split,
        "respostas_sem_extracao": sum(not r["resposta_valida"] for r in validos),
        "revisoes_necessarias": sum(r["revisao_necessaria"] for r in validos),
        "tempo_total_segundos": round(tempo_total, 2),
        "tempo_medio_segundos": round(statistics.mean(tempos), 2) if tempos else None,
        "tokens_entrada": sum(r.get("tokens_entrada") or 0 for r in validos),
        "tokens_saida": sum(r.get("tokens_saida") or 0 for r in validos),
        "cpu_media_percentual": media("cpu_percentual"),
        "ram_media_percentual": media("ram_percentual"),
    }


def recursos():
    if psutil is None:
        return {"cpu_percentual": None, "ram_percentual": None}
    return {
        "cpu_percentual": psutil.cpu_percent(interval=None),
        "ram_percentual": psutil.virtual_memory().percent,
    }
def identificador_novo(dataset, limite, quantidade):
    pasta = pasta_configuracao("few_shot", dataset, limite, quantidade)
    return novo_nome("few_shot", dataset, pasta)

def tempo_legivel(segundos):
    horas, resto = divmod(round(segundos), 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{horas}h {minutos}min {segundos}s" if horas else f"{minutos}min {segundos}s"
def mostrar_resumo(dataset, dados, caminho):
    m = dados["metricas"]
    acuracia = m["acuracia_percentual"]
    print(f"\n{dataset.upper()} | Few-shot")
    print(f"Questões executadas: {m['questoes_executadas']}")
    print(f"Questões avaliadas: {m['questoes_avaliadas']}")
    print(f"Exemplos utilizados: {m['exemplos_utilizados']}")
    print(f"Acertos: {m['acertos']}")
    print(f"Erros: {m['erros']}")
    print(f"Falhas técnicas: {m['falhas_tecnicas']}")
    print(f"Acurácia: {acuracia:.2f}%" if acuracia is not None else "Acurácia: indisponível")
    print(f"Tempo de execução: {tempo_legivel(m['tempo_total_segundos'])}")
    print(f"Resultados salvos em: {caminho}")


def executar_dataset(dataset, limite=USAR_LIMITE_PADRAO, n_exemplos=None, retomar=None):
    carregadores = {
        "gsm8k": carregar_gsm8k,
        "aqua_rat": carregar_aqua_rat,
        "censo": carregar_censo,
    }
    if dataset not in carregadores:
        raise ValueError(f"Dataset desconhecido: {dataset}")
    limite = resolver_limite(dataset, limite)
    quantidade = N_EXEMPLOS_PADRAO[dataset] if n_exemplos is None else n_exemplos
    registros = carregadores[dataset](split=None)
    ids = [str(q.get("id", "")) for q in registros]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Há IDs ausentes ou duplicados no dataset.")
    exemplos = selecionar_exemplos(dataset, registros, quantidade)
    ids_exemplos = {str(e["id"]) for e in exemplos}
    # Exclui automaticamente as questões utilizadas como exemplos, pelos IDs.
    # Preserva a ordem original e aplica o limite somente após a exclusão.
    questoes_disponiveis = [
        questao for questao in registros
        if str(questao["id"]) not in ids_exemplos
    ]
    questoes = (questoes_disponiveis[:limite]
               if limite is not None else questoes_disponiveis)
    if not questoes:
        raise ValueError("Nenhuma questão disponível para avaliação após excluir os exemplos.")
    sessao = None
    contextos_exemplos = None
    if dataset == "censo":
        try:
            from codigo.consulta_censo import SessaoCenso, verificar_consultas
        except ImportError as erro:
            raise ImportError(
                "O Censo exige SessaoCenso e verificar_consultas em codigo/consulta_censo.py."
            ) from erro
        verificar_consultas(exemplos + questoes)
        sessao = SessaoCenso()
        contextos_exemplos = {str(e["id"]): sessao.consultar(e) for e in exemplos}
    pasta = pasta_configuracao("few_shot", dataset, limite, quantidade)
    nome = (Path(retomar).name.removesuffix(".progresso.json") if retomar
            else identificador_novo(dataset, limite, quantidade))
    caminho = pasta / f"{nome}.json"
    progresso = pasta / f"{nome}.progresso.json"
    parametros = {
        "modelo": MODELO,
        "temperatura": TEMPERATURE,
        "limite": limite,
        "maximo_tokens_resposta": NUM_PREDICT,
        "quantidade_exemplos": quantidade,
        "ids_exemplos": [str(e["id"]) for e in exemplos],
        "ids_questoes": [str(q["id"]) for q in questoes],
        "criterio_avaliacao": "todos_splits_sem_demonstracoes" if dataset != "censo" else "fora_das_demonstracoes",
    }
    parametros['protocolo'] = resumo_protocolo(dataset, exemplos, questoes, limite, quantidade)
    parametros['top_k'] = 40
    parametros['top_p'] = 0.9
    parametros['num_ctx'] = 8192
    if retomar:
        with progresso.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        if dados["parametros"] != parametros:
            raise ValueError("Os parâmetros atuais diferem do checkpoint.")
        resultados = dados["resultados"]
    else:
        resultados = []
        dados = {
            "id_execucao": nome,
            "tecnica": "few_shot",
            "dataset": dataset,
            "data_inicio": agora(),
            "parametros": parametros,
            "resultados": resultados,
            "status": "em_andamento",
        }
    concluidos = {str(r["id"]) for r in resultados}
    if len(concluidos) != len(resultados):
        raise ValueError("Checkpoint contém questões duplicadas.")
    questoes_para_executar = [q for q in questoes if str(q["id"]) not in concluidos]
    tempo_anterior = dados.get("tempo_acumulado_segundos", 0.0)
    inicio = time.perf_counter()
    print(f"\n{dataset.upper()} | {len(questoes)} questões | {quantidade} exemplos ")
    def checkpoint():
        total = tempo_anterior + time.perf_counter() - inicio
        dados["tempo_acumulado_segundos"] = total
        dados["metricas_parciais"] = metricas(resultados, total, quantidade, dataset)
        salvar(progresso, dados)
    try:
        barra = tqdm(questoes_para_executar, desc=f"Few-shot {dataset}")
        for questao in barra:
            barra.set_postfix(restantes=len(questoes) - len(resultados))
            demonstracao = str(questao["id"]) in ids_exemplos
            if dataset == "gsm8k":
                exemplos_prompt = [e for e in exemplos if str(e["id"]) != str(questao["id"])]
                if not exemplos_prompt:
                    raise ValueError("É necessário ter outra demonstração para avaliar esta questão.")
                prompt = prompt_few_shot_gsm8k(questao, exemplos_prompt)
                gabarito = extrair_gabarito_gsm8k(questao)
            elif dataset == "aqua_rat":
                exemplos_prompt = [e for e in exemplos if str(e["id"]) != str(questao["id"])]
                if not exemplos_prompt:
                    raise ValueError("É necessário ter outra demonstração para avaliar esta questão.")
                prompt = prompt_few_shot_aqua_rat(questao, exemplos_prompt)
                gabarito = extrair_gabarito_aqua_rat(questao)
            else:
                contexto = sessao.consultar(questao)
                # Para questões de demonstração, exclui a própria questão do prompt.
                exemplos_prompt = [e for e in exemplos if str(e["id"]) != str(questao["id"])]
                if not exemplos_prompt:
                    raise ValueError("Censo precisa de pelo menos dois exemplos para executar demonstrações.")
                prompt = prompt_few_shot_censo(questao, contexto, exemplos_prompt, contextos_exemplos)
                gabarito = extrair_gabarito_censo(questao)
            inicio_questao = time.perf_counter()
            info = consultar_ollama(
                prompt, temperature=TEMPERATURE,
                num_predict=NUM_PREDICT, retornar_metricas=True,
            )
            duracao = round(time.perf_counter() - inicio_questao, 3)
            if not isinstance(info, dict):
                info = {"resposta": None}
            texto = info.get("resposta")
            erro_consulta = texto is None
            if erro_consulta:
                motivo = info.get("erro_detalhado") or info.get("erro") or "Falha na consulta ao Ollama"
                resultados.append({
                    "id": str(questao["id"]), "split": questao.get("split"),
                    "usada_como_exemplo": False,
                    "gabarito": gabarito, "resposta": None, "texto_modelo": None,
                    "resposta_valida": False, "acertou": None,
                    "falha_tecnica": True, "motivo": motivo,
                    "tentativas_consulta": info.get("tentativas", 3),
                    "revisao_necessaria": False, "metodo_avaliacao": "falha_tecnica_consulta",
                    "tempo_segundos": duracao, "tokens_entrada": None,
                    "tokens_saida": None, **recursos(),
                })
                print(f"\n[FALHA TÉCNICA] {dataset}/{questao['id']}: {motivo}. Avançando.")
                checkpoint()
                continue

            if dataset == "gsm8k":
                resposta = extrair_resposta_numerica(texto)
                valida = bool(resposta)
                acertou = comparar_numeros(resposta, gabarito) if valida else False
            elif dataset == "aqua_rat":
                resposta = extrair_letra_resposta(texto)
                valida = bool(resposta)
                acertou = resposta == gabarito if valida else False
            else:
                resposta = str(texto).strip() if texto is not None else ""
                valida = bool(resposta)
                # Avalia automaticamente com o gabarito, sem usá-lo no prompt da questão.
                # Respostas inconclusivas ou sem resultado identificável são erros.
                avaliacao_censo = avaliar_censo(questao, resposta, consultar_ollama)
                acertou = avaliacao_censo["acertou"]
                if acertou is None:
                    motivo = "Falha na avaliação do Censo: " + avaliacao_censo["motivo"]
                    resultados.append({
                        "id": str(questao["id"]), "split": questao.get("split"),
                        "usada_como_exemplo": False,
                        "gabarito": gabarito, "resposta": resposta, "texto_modelo": texto,
                        "resposta_valida": valida, "acertou": None,
                        "falha_tecnica": True, "motivo": motivo,
                        "tentativas_consulta": 3,
                        "revisao_necessaria": False,
                        "metodo_avaliacao": "falha_tecnica_avaliador",
                        "tempo_segundos": duracao,
                        "tokens_entrada": info.get("prompt_eval_count"),
                        "tokens_saida": info.get("eval_count"), **recursos(),
                    })
                    print(f"\n[FALHA TÉCNICA] {dataset}/{questao['id']}: {motivo}. Avançando.")
                    checkpoint()
                    continue

            revisao = False  # Avaliação binária: não há fila de revisão.
            if erro_consulta:
                motivo = "Falha na consulta ao modelo"
            elif not valida:
                motivo = "Resposta não identificada"
            elif acertou is False:
                motivo = "Resposta incorreta"
            elif acertou is None:
                motivo = "Avaliação inconclusiva"
            else:
                motivo = None
            if dataset == "censo" and not erro_consulta:
                motivo = avaliacao_censo["motivo"]
            resultados.append({
                "id": str(questao["id"]),
                "split": questao.get("split"),
                "usada_como_exemplo": demonstracao,
                "gabarito": gabarito,
                "resposta": resposta,
                "texto_modelo": texto,
                "resposta_valida": valida,
                "acertou": acertou,
                "falha_tecnica": False,
                "tentativas_consulta": info.get("tentativas", 1),
                "motivo": motivo,
                "revisao_necessaria": revisao,
                "metodo_avaliacao": (avaliacao_censo["metodo_avaliacao"] if dataset == "censo" else "comparacao_exata"),
                "tempo_segundos": duracao,
                "tokens_entrada": info.get("prompt_eval_count"),
                "tokens_saida": info.get("eval_count"),
                **recursos(),
            })
            if len(resultados) % SALVAR_CADA == 0:
                checkpoint()
        barra.set_postfix(restantes=0)
    except BaseException:
        checkpoint()
        raise
    dados["data_fim"] = agora()
    dados["status"] = "concluido"
    dados["tempo_acumulado_segundos"] = tempo_anterior + time.perf_counter() - inicio
    dados["metricas"] = metricas(resultados, dados["tempo_acumulado_segundos"], quantidade, dataset)
    dados.pop("metricas_parciais", None)
    salvar(caminho, dados)
    if progresso.exists():
        progresso.unlink()
    mostrar_resumo(dataset, dados, caminho)
    return dados
def executar_gsm8k(limite=USAR_LIMITE_PADRAO, n_exemplos=None, retomar=None):
    return executar_dataset("gsm8k", limite, n_exemplos, retomar)
def executar_aqua_rat(limite=USAR_LIMITE_PADRAO, n_exemplos=None, retomar=None):
    return executar_dataset("aqua_rat", limite, n_exemplos, retomar)
def executar_censo(limite=USAR_LIMITE_PADRAO, n_exemplos=None, retomar=None):
    return executar_dataset("censo", limite, n_exemplos, retomar)



if __name__ == "__main__":
    executar_gsm8k()
    executar_aqua_rat()
    executar_censo()
    
  