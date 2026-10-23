from codigo.agente_censo import consultar_censo_agente, executar_consultas_demonstracao
"""Execução Chain-of-Thought: GSM8K, AQuA-RAT e Censo Escolar.

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
from codigo.chain_of_thought.prompts import (
    prompt_cot_gsm8k, prompt_cot_aqua_rat, prompt_cot_censo,
)

try:
    import psutil
except ImportError:
    psutil = None

from codigo.utils import MODELO_OLLAMA, SEMENTE_OLLAMA
MODELO = MODELO_OLLAMA
TEMPERATURE = 0.0
NUM_PREDICT = 1200
SALVAR_CADA = 10
PASTA_BASE = Path("resultados/chain_of_thought")

# Faixas temáticas das 50 questões do Censo (posições no JSON).
# A seleção é automática, determinística e alterna entre os seis blocos.

# Avaliação do Censo 
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
    """Falhas técnicas não participam da acurácia nem das médias de desempenho."""
    avaliadas = [
        r for r in resultados
        if not r.get("falha_tecnica", False) and isinstance(r.get("acertou"), bool)
    ]
    falhas = [r for r in resultados if r.get("falha_tecnica", False)]
    tempos = [r["tempo_segundos"] for r in avaliadas if isinstance(r.get("tempo_segundos"), (int, float))]
    def acuracia(itens):
        return round(100 * sum(r["acertou"] for r in itens) / len(itens), 2) if itens else None
    def media(chave):
        valores = [r[chave] for r in avaliadas if isinstance(r.get(chave), (int, float))]
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
        "falhas_tecnicas": len(falhas),
        "questoes_descartadas_por_falha_tecnica": len(falhas),
        "detalhes_falhas_tecnicas": [
            {"id": r["id"], "motivo": r.get("motivo"), "tentativas": r.get("tentativas_consulta")}
            for r in falhas
        ],
        "acertos": sum(r["acertou"] for r in avaliadas),
        "erros": sum(not r["acertou"] for r in avaliadas),
        "acuracia_percentual": acuracia(avaliadas),
        "acuracia_por_split": por_split,
        "respostas_sem_extracao": sum(not r.get("resposta_valida", False) for r in avaliadas),
        "revisoes_necessarias": sum(bool(r.get("revisao_necessaria", False)) for r in avaliadas),
        "tempo_total_segundos": round(tempo_total, 2),
        "tempo_medio_segundos": round(statistics.mean(tempos), 2) if tempos else None,
        "tokens_entrada": sum(r.get("tokens_entrada") or 0 for r in avaliadas),
        "tokens_saida": sum(r.get("tokens_saida") or 0 for r in avaliadas),
        "cpu_ollama_media_percentual": media("cpu_ollama_percentual"),
        "ram_ollama_pico_mib": max((r["ram_ollama_pico_mib"] for r in avaliadas if r.get("ram_ollama_pico_mib") is not None), default=None),
        "ram_ollama_media_mib": media("ram_ollama_media_mib"),
    }

def recursos():
    if psutil is None:
        return {"cpu_percentual": None, "ram_percentual": None}
    return {
        "cpu_percentual": psutil.cpu_percent(interval=None),
        "ram_percentual": psutil.virtual_memory().percent,
    }

def identificador_novo(dataset, limite, quantidade):
    pasta = pasta_configuracao("chain_of_thought", dataset, limite, quantidade)
    return novo_nome("chain_of_thought", dataset, pasta)

def tempo_legivel(segundos):
    horas, resto = divmod(round(segundos), 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{horas}h {minutos}min {segundos}s" if horas else f"{minutos}min {segundos}s"

def mostrar_resumo(dataset, dados, caminho):
    m = dados["metricas"]
    acuracia = m["acuracia_percentual"]
    print(f"\n{dataset.upper()} | Chain-of-Thought")
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
    consultas_exemplos = None
    if dataset == "censo":
        try:
            from codigo.consulta_censo import SessaoCenso, verificar_consultas
        except ImportError as erro:
            raise ImportError(
                "O Censo exige SessaoCenso e verificar_consultas em codigo/consulta_censo.py."
            ) from erro
        verificar_consultas(exemplos + questoes)
        sessao = SessaoCenso()
        contextos_exemplos = {str(e["id"]): "Consulte a tabela matriculas por SQL." for e in exemplos}
        consultas_exemplos = executar_consultas_demonstracao(sessao, exemplos)
        raciocinios_exemplos = {}
        for exemplo in exemplos:
            raciocinio = str(exemplo.get("raciocinio") or "").strip()
            if not raciocinio:
                raise ValueError(
                    f"Censo {exemplo['id']} sem raciocínio. Execute baixar_preparar_censo.py "
                    "para gerar o JSON com as demonstrações CoT."
                )
            raciocinios_exemplos[str(exemplo["id"])] = raciocinio

    pasta = pasta_configuracao("chain_of_thought", dataset, limite, quantidade)
    nome = (Path(retomar).name.removesuffix(".progresso.json") if retomar
            else identificador_novo(dataset, limite, quantidade))
    caminho = pasta / f"{nome}.json"
    progresso = pasta / f"{nome}.progresso.json"
    parametros = {
        "modelo": MODELO,
        "seed": SEMENTE_OLLAMA,
        "temperatura": TEMPERATURE,
        "limite": limite,
        "maximo_tokens_resposta": NUM_PREDICT,
        "quantidade_exemplos": quantidade,
        "ids_exemplos": [str(e["id"]) for e in exemplos],
        "ids_questoes": [str(q["id"]) for q in questoes],
        "criterio_avaliacao": "todos_splits_sem_demonstracoes",
        "tipo_demonstracao": "questao_raciocinio_resposta",
        "origem_raciocinios_censo": "json_preparado" if dataset == "censo" else None,
    }
    if dataset == 'censo':
        parametros['arquitetura_censo'] = 'agente_sql_direto_v1_max_5_consultas'
        parametros['demonstracoes_censo'] = 'consultas_sql_executadas_v1'
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
            "tecnica": "chain_of_thought",
            "dataset": dataset,
            "data_inicio": agora(),
            "parametros": parametros,
            "resultados": resultados,
            "status": "em_andamento",
        }

    concluidos = {str(r["id"]) for r in resultados}
    if len(concluidos) != len(resultados):
        raise ValueError("Checkpoint contém questões duplicadas.")
    pendentes = [q for q in questoes if str(q["id"]) not in concluidos]
    tempo_anterior = dados.get("tempo_acumulado_segundos", 0.0)
    inicio = time.perf_counter()
    print(f"\n{dataset.upper()} | {len(questoes)} questões | {quantidade} exemplos")

    def checkpoint():
        total = tempo_anterior + time.perf_counter() - inicio
        dados["tempo_acumulado_segundos"] = total
        dados["metricas_parciais"] = metricas(resultados, total, quantidade, dataset)
        salvar(progresso, dados)

    try:
        for questao in tqdm(pendentes, desc=f"Chain-of-Thought {dataset}"):
            demonstracao = str(questao["id"]) in ids_exemplos
            if dataset == "gsm8k":
                exemplos_prompt = [e for e in exemplos if str(e["id"]) != str(questao["id"])]
                if not exemplos_prompt:
                    raise ValueError("É necessário ter outra demonstração para avaliar esta questão.")
                prompt = prompt_cot_gsm8k(questao, exemplos_prompt)
                gabarito = extrair_gabarito_gsm8k(questao)
            elif dataset == "aqua_rat":
                exemplos_prompt = [e for e in exemplos if str(e["id"]) != str(questao["id"])]
                if not exemplos_prompt:
                    raise ValueError("É necessário ter outra demonstração para avaliar esta questão.")
                prompt = prompt_cot_aqua_rat(questao, exemplos_prompt)
                gabarito = extrair_gabarito_aqua_rat(questao)
            else:
                contexto = sessao.consultar(questao)
                # Segurança: não permite que a questão avaliada seja demonstração.
                exemplos_prompt = [e for e in exemplos if str(e["id"]) != str(questao["id"])]
                if not exemplos_prompt:
                    raise ValueError("Censo precisa de pelo menos dois exemplos para executar demonstrações.")
                prompt = prompt_cot_censo(questao, contexto, exemplos_prompt, contextos_exemplos, raciocinios_exemplos, consultas_exemplos)
                gabarito = extrair_gabarito_censo(questao)

            inicio_questao = time.perf_counter()
            info = (consultar_censo_agente(
                prompt, sessao, temperature=TEMPERATURE,
                num_predict=NUM_PREDICT, retornar_metricas=True,
            ) if dataset == "censo" else consultar_ollama(
                prompt, temperature=TEMPERATURE,
                num_predict=NUM_PREDICT, retornar_metricas=True,
            ))
            duracao = round(time.perf_counter() - inicio_questao, 3)
            if not isinstance(info, dict):
                info = {"resposta": None}
            texto = info.get("resposta")
            erro_consulta = texto is None

            if erro_consulta:
                # consultar_ollama já fez as três tentativas. Registra e segue.
                detalhe = info.get("erro_detalhado") or info.get("erro") or (
                    "Falha do Ollama após 3 tentativas (ver erro no terminal)"
                )
                resultados.append({
                    "id": str(questao["id"]), "split": questao.get("split"),
                    "usada_como_exemplo": False, "avaliacao_independente": False,
                    "gabarito": gabarito, "resposta": None, "texto_modelo": None,
                    "resposta_valida": False, "falha_tecnica": True,
                    "acertou": None, "motivo": detalhe,
                    "tentativas_consulta": info.get("tentativas", 3),
                    "revisao_necessaria": False, "metodo_avaliacao": "falha_tecnica",
                    "tempo_segundos": duracao, "tokens_entrada": None,
                    "tokens_saida": None, "consultas_censo": info.get("consultas_censo", []) if dataset == "censo" else [], "texto_descartado": info.get("texto_descartado", ""), "transcricoes_censo": info.get("transcricoes_censo", []), "motivo_encerramento_censo": info.get("motivo_encerramento_censo"), "consultas_repetidas_bloqueadas": info.get("consultas_repetidas_bloqueadas", 0), **{k: info.get(k) for k in ("cpu_ollama_percentual", "ram_ollama_pico_mib", "ram_ollama_media_mib", "amostras_monitoramento")},
                })
                print(f"\n[FALHA TÉCNICA] {dataset}/{questao['id']}: {detalhe}. "
                      "Fora da acurácia; avançando.")
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
                    resultados.append({
                        "id": str(questao["id"]), "split": questao.get("split"),
                        "usada_como_exemplo": False, "avaliacao_independente": False,
                        "gabarito": gabarito, "resposta": resposta,
                        "texto_modelo": texto, "resposta_valida": valida,
                        "falha_tecnica": True, "acertou": None,
                        "motivo": "Avaliador inconclusivo: " + avaliacao_censo["motivo"],
                        "tentativas_consulta": 3, "revisao_necessaria": False,
                        "metodo_avaliacao": "falha_tecnica_avaliador",
                        "tempo_segundos": duracao,
                        "tokens_entrada": info.get("prompt_eval_count"),
                        "tokens_saida": info.get("eval_count"),
                "consultas_censo": info.get("consultas_censo", []) if dataset == "censo" else [], "texto_descartado": info.get("texto_descartado", ""), "transcricoes_censo": info.get("transcricoes_censo", []), "motivo_encerramento_censo": info.get("motivo_encerramento_censo"), "consultas_repetidas_bloqueadas": info.get("consultas_repetidas_bloqueadas", 0),
                "rodadas_censo": info.get("rodadas_censo", 0) if dataset == "censo" else 0, **{k: info.get(k) for k in ("cpu_ollama_percentual", "ram_ollama_pico_mib", "ram_ollama_media_mib", "amostras_monitoramento")},
                    })
                    checkpoint()
                    continue

            # Falha HTTP/timeout não é erro matemático; resposta sem letra/número é erro.
            if erro_consulta:
                acertou = None

            independente = not demonstracao  # Todos os splits são avaliados, exceto demonstrações.
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
                "avaliacao_independente": independente,
                "gabarito": gabarito,
                "resposta": resposta,
                "texto_modelo": texto,
                "resposta_valida": valida,
                "falha_tecnica": erro_consulta,
                "acertou": acertou,
                "motivo": motivo,
                "revisao_necessaria": revisao,
                "metodo_avaliacao": ("falha_tecnica" if erro_consulta else avaliacao_censo["metodo_avaliacao"] if dataset == "censo" else "comparacao_exata"),
                "tempo_segundos": duracao,
                "tokens_entrada": info.get("prompt_eval_count"),
                "tokens_saida": info.get("eval_count"),
                "consultas_censo": info.get("consultas_censo", []) if dataset == "censo" else [], "texto_descartado": info.get("texto_descartado", ""), "transcricoes_censo": info.get("transcricoes_censo", []), "motivo_encerramento_censo": info.get("motivo_encerramento_censo"), "consultas_repetidas_bloqueadas": info.get("consultas_repetidas_bloqueadas", 0),
                "rodadas_censo": info.get("rodadas_censo", 0) if dataset == "censo" else 0,
                **{k: info.get(k) for k in ("cpu_ollama_percentual", "ram_ollama_pico_mib", "ram_ollama_media_mib", "amostras_monitoramento")},
            })
            if len(resultados) % SALVAR_CADA == 0:
                checkpoint()
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

