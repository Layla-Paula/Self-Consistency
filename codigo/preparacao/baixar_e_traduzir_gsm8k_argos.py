"""
GSM8K -> Português
Autor: Layla Paula

Baixa o dataset GSM8K apenas se o original não existir
Utiliza a versão original já armazenada
Traduz para PT-BR com Argos Translate (offline)
Salva progresso automaticamente
Gera JSON final mantendo a estrutura existente
"""

from datasets import load_dataset
from argostranslate import package, translate

import json
import os
import re
from datetime import datetime
from collections import Counter


# PASTAS

PASTA_BASE = "dados/gsm8k"
PASTA_ORIGINAIS = os.path.join(PASTA_BASE, "originais")
PASTA_TRADUCOES = os.path.join(PASTA_BASE, "traducoes")
PASTA_FINAL = os.path.join(PASTA_BASE, "final")

ARQ_ORIGINAL = os.path.join(PASTA_ORIGINAIS, "gsm8k_original.json")
ARQ_PROGRESSO = os.path.join(PASTA_TRADUCOES, "progresso_traducao_argos.json")
ARQ_FINAL = os.path.join(PASTA_FINAL, "gsm8k_ptbr.json")


ORIGINAIS_ANTIGOS = [
    os.path.join(PASTA_BASE, "gsm8k_original.json"),
    os.path.join(PASTA_ORIGINAIS, "gsm8k_todos_original.json"),
]
PROGRESSOS_ANTIGOS = [
    os.path.join(PASTA_BASE, "progresso_traducao_argos.json"),
]


# CRIAR PASTAS

for pasta in (PASTA_ORIGINAIS, PASTA_TRADUCOES, PASTA_FINAL):
    os.makedirs(pasta, exist_ok=True)


# BAIXAR DATASET


def baixar_gsm8k():
    print("Baixando GSM8K...")
    dataset = load_dataset("openai/gsm8k", "main")
    dados = []
    for split in ("train", "test"):
        for i, item in enumerate(dataset[split]):
            dados.append({
                "id": f"{split}_{i}",
                "split": split,
                "question": item["question"],
                "answer": item["answer"]
            })
    print(f"Total: {len(dados)}")
    return dados


# SALVAR ORIGINAL


def salvar_json_seguro(caminho, dados):
    """Grava no caminho informado sem criar arquivos auxiliares."""
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    # Grava diretamente no JSON já existente, sem criar arquivos .tmp.
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def salvar_original(dados):
    salvar_json_seguro(ARQ_ORIGINAL, dados)


def carregar_original():
    # Não cria uma cópia do original na pasta de traduções.
    for caminho in [ARQ_ORIGINAL] + ORIGINAIS_ANTIGOS:
        if not os.path.isfile(caminho):
            continue
        with open(caminho, "r", encoding="utf-8") as arquivo:
            conteudo = json.load(arquivo)
        if isinstance(conteudo, dict):
            conteudo = conteudo.get("problemas", conteudo.get("dados"))
        if not isinstance(conteudo, list):
            raise ValueError(f"Estrutura inesperada no original: {caminho}")
        dados = []
        for registro in conteudo:
            if "question" in registro and "answer" in registro:
                dados.append({k: registro[k] for k in ("id", "split", "question", "answer")})
            elif "question_en" in registro and "answer_en" in registro:
                dados.append({
                    "id": registro["id"], "split": registro["split"],
                    "question": registro["question_en"], "answer": registro["answer_en"]
                })
            else:
                raise ValueError(f"Campos desconhecidos no original: {caminho}")
        print(f"Usando dataset original já existente: {caminho}")
        return dados
    dados = baixar_gsm8k()
    salvar_original(dados)
    return dados


# CARREGAR PROGRESSO


def carregar_progresso():
    """Recupera o progresso do Argos, inclusive do caminho usado anteriormente."""
    por_id = {}
    for caminho in PROGRESSOS_ANTIGOS + [ARQ_PROGRESSO]:
        if not os.path.isfile(caminho):
            continue
        with open(caminho, "r", encoding="utf-8") as arquivo:
            registros = json.load(arquivo)
        if isinstance(registros, dict):
            registros = registros.get("problemas", [])
        if not isinstance(registros, list):
            raise ValueError(f"Progresso inválido: {caminho}")
        for registro in registros:
            if isinstance(registro, dict) and registro.get("id"):
                por_id[registro["id"]] = registro
    return por_id


# SALVAR PROGRESSO


def salvar_progresso(registros):
    salvar_json_seguro(ARQ_PROGRESSO, registros)


# TRADUTOR


def configurar_tradutor():
    """Reutiliza o modelo inglês -> português já instalado no Argos."""
    idiomas = translate.get_installed_languages()
    ingles = next((i for i in idiomas if i.code == "en"), None)
    portugues = next((i for i in idiomas if i.code == "pt"), None)
    tradutor = ingles.get_translation(portugues) if ingles and portugues else None
    if tradutor is None:
        print("Modelo en -> pt não instalado; baixando somente o modelo necessário...")
        package.update_package_index()
        candidato = next(
            (p for p in package.get_available_packages()
             if p.from_code == "en" and p.to_code == "pt"), None
        )
        if candidato is None:
            raise RuntimeError("Modelo Argos en -> pt não encontrado.")
        package.install_from_path(candidato.download())
        idiomas = translate.get_installed_languages()
        ingles = next((i for i in idiomas if i.code == "en"), None)
        portugues = next((i for i in idiomas if i.code == "pt"), None)
        tradutor = ingles.get_translation(portugues) if ingles and portugues else None
    if tradutor is None:
        raise RuntimeError("Não foi possível carregar o tradutor en -> pt.")
    return tradutor


# PRESERVAR NÚMEROS E MARCADORES MATEMÁTICOS

PADRAO_MARCADOR = re.compile(r"<<.*?>>|####\s*[-+]?\d[\d.,]*", re.S)
# Protege apenas os algarismos e seus separadores decimais. Sinais, frações,
# porcentagens e ordinais ficam fora do token: o Argos não pode alterá-los
# ao modificar espaços, mas a comparação não confunde 10-8 com 10 - 8.
PADRAO_NUMERO = re.compile(r"\d+(?:[.,]\d+)*")
PADRAO_GABARITO = re.compile(r"####\s*([-+]?\d[\d.,]*)\s*$")


def numeros(texto):
    """Obtém todos os valores escritos com algarismos, na ordem original."""
    return PADRAO_NUMERO.findall(PADRAO_MARCADOR.sub("", texto))


def gabarito(texto):
    encontrado = PADRAO_GABARITO.search(texto)
    if not encontrado:
        raise ValueError("Gabarito ausente: esperado '#### número'.")
    return encontrado.group(1)


def traduzir_livre(texto, tradutor):
    if not texto.strip():
        return texto
    inicio = texto[:len(texto) - len(texto.lstrip())]
    fim = texto[len(texto.rstrip()):]
    resultado = tradutor.translate(texto.strip())
    if not isinstance(resultado, str) or not resultado.strip():
        raise ValueError("O Argos retornou uma tradução vazia.")
    return inicio + resultado.strip() + fim


def traduzir_bloco_sem_numeros(texto, tradutor):
    """Traduz sem aceitar algarismos novos; reduz os trechos quando necessário."""
    if not texto.strip():
        return texto

    # Tradução integral preserva melhor o contexto e tem prioridade.
    tentativa = traduzir_livre(texto, tradutor)
    if not PADRAO_NUMERO.search(tentativa):
        return tentativa

    # O Argos pode criar algarismos (ex.: 'first' -> '1º'). Traduz frases
    # menores; quando necessário, grupos de palavras, sem inventar valores.
    pedacos = re.split(r"(?<=[.!?;:])(?=\s)|(?<=,)(?=\s)", texto)
    if len(pedacos) == 1:
        pedacos = re.findall(r"\S+\s*|\s+", texto)
        tamanho = 5
        pedacos = ["".join(pedacos[i:i + tamanho])
                   for i in range(0, len(pedacos), tamanho)]

    saida = []
    for bloco in pedacos:
        if not bloco.strip():
            saida.append(bloco)
            continue
        versao = traduzir_livre(bloco, tradutor)
        if not PADRAO_NUMERO.search(versao):
            saida.append(versao)
            continue
        # Última tentativa: palavras individuais. Se ainda houver algarismos
        # introduzidos pelo tradutor, conserva somente aquela palavra original.
        for palavra in re.findall(r"\S+\s*|\s+", bloco):
            if not palavra.strip():
                saida.append(palavra)
                continue
            alternativa = traduzir_livre(palavra, tradutor)
            saida.append(alternativa if not PADRAO_NUMERO.search(alternativa)
                         else palavra)

    resultado = "".join(saida)
    if PADRAO_NUMERO.search(resultado):
        raise ValueError("O Argos introduziu algarismos em um trecho sem números.")
    return resultado


def juntar_sem_fundir_numeros(fragmentos, referencia):
    """Evita que números vizinhos se fundam ao recompor trechos traduzidos.

    Exemplo: '12' + '. ' + '5' pode virar '12.5' quando o Argos
    elimina um espaço. A reconstrução testa os limites sem mexer nos dígitos.
    """
    resultado = ""
    for fragmento in fragmentos:
        if not fragmento:
            continue
        candidato = resultado + fragmento
        # Se a junção fundir dois números (inclusive 1. + 5 -> 1.5),
        # insere um separador entre os fragmentos.
        if resultado and numeros(candidato) != (
            numeros(resultado) + numeros(fragmento)
        ):
            candidato = resultado + " " + fragmento
        resultado = candidato
    return resultado


def traduzir_com_numeros_protegidos(texto, tradutor):
    """Traduz somente trechos sem algarismos e recompõe sem fundir números."""
    fragmentos = []
    anterior = 0
    for encontrado in PADRAO_NUMERO.finditer(texto):
        trecho = texto[anterior:encontrado.start()]
        if trecho:
            fragmentos.append(traduzir_bloco_sem_numeros(trecho, tradutor))
        fragmentos.append(encontrado.group(0))
        anterior = encontrado.end()
    restante = texto[anterior:]
    if restante:
        fragmentos.append(traduzir_bloco_sem_numeros(restante, tradutor))
    resultado = juntar_sem_fundir_numeros(fragmentos, texto)
    if numeros(texto) != numeros(resultado):
        raise ValueError(
            f"Números diferentes: original={numeros(texto)!r} | "
            f"tradução={numeros(resultado)!r} | "
            f"trecho={texto[:180]!r} | saída={resultado[:180]!r}"
        )
    return resultado



def traduzir_blindado(texto, tradutor):
    """Último recurso: nunca deixa o tradutor tocar nos algarismos.

    Cada sequência numérica é copiada literalmente do original. Os textos
    entre números são traduzidos separadamente. Se o Argos introduzir um
    algarismo em um desses textos, mantém SOMENTE o trecho original.
    Se a recomposição alterar a leitura numérica, mantém a linha original.
    Isso evita corrupção de dados, mas pode deixar trechos em inglês.
    """
    if not texto.strip():
        return texto

    partes = []
    posicao = 0
    for achado in PADRAO_NUMERO.finditer(texto):
        texto_livre = texto[posicao:achado.start()]
        if texto_livre:
            try:
                traducao = traduzir_livre(texto_livre, tradutor)
                if PADRAO_NUMERO.search(traducao):
                    traducao = texto_livre
            except Exception:
                traducao = texto_livre
            partes.append(traducao)
        partes.append(achado.group(0))  # número: cópia literal
        posicao = achado.end()

    texto_livre = texto[posicao:]
    if texto_livre:
        try:
            traducao = traduzir_livre(texto_livre, tradutor)
            if PADRAO_NUMERO.search(traducao):
                traducao = texto_livre
        except Exception:
            traducao = texto_livre
        partes.append(traducao)

    resultado = juntar_sem_fundir_numeros(partes, texto)
    # Falha fechada: nunca aceita uma linha com números modificados.
    if numeros(resultado) != numeros(texto):
        return texto
    return resultado

def traduzir_segmento_seguro(texto, tradutor):
    """Mantém compatibilidade com a função de tradução protegida."""
    return traduzir_com_numeros_protegidos(texto, tradutor)


def traduzir_por_partes(texto, tradutor):
    """Divide frases preservando os algarismos originais em cada trecho."""
    pedacos = re.split(r"(?<=[.!?;:])(?=\s)|(?<=,)(?=\s)", texto)
    saida = []
    for pedaco in pedacos:
        if not pedaco.strip():
            saida.append(pedaco)
        else:
            saida.append(traduzir_com_numeros_protegidos(pedaco, tradutor))
    resultado = juntar_sem_fundir_numeros(saida, texto)
    if numeros(texto) != numeros(resultado):
        raise ValueError(
            f"Diferença após divisão: original={numeros(texto)!r} | "
            f"tradução={numeros(resultado)!r}"
        )
    return resultado


def traduzir(texto, tradutor, modo="normal"):
    """Traduz preservando os números, marcadores e o gabarito original."""
    partes = PADRAO_MARCADOR.split(texto)
    marcadores = PADRAO_MARCADOR.findall(texto)
    saida = []
    for indice, parte in enumerate(partes):
        if parte:
            for linha in parte.splitlines(keepends=True):
                conteudo = linha.rstrip("\r\n")
                quebra = linha[len(conteudo):]
                if not conteudo.strip():
                    saida.append(linha)
                    continue
                if modo == "blindado":
                    tentativa = traduzir_blindado(conteudo, tradutor)
                elif modo == "partes":
                    tentativa = traduzir_por_partes(conteudo, tradutor)
                elif modo == "protegido":
                    tentativa = traduzir_com_numeros_protegidos(conteudo, tradutor)
                else:
                    tentativa = traduzir_livre(conteudo, tradutor)
                    if numeros(conteudo) != numeros(tentativa):
                        tentativa = traduzir_com_numeros_protegidos(conteudo, tradutor)
                if numeros(conteudo) != numeros(tentativa):
                    raise ValueError(
                        f"Números diferentes: original={numeros(conteudo)!r} | "
                        f"tradução={numeros(tentativa)!r}"
                    )
                saida.append(tentativa + quebra)
        if indice < len(marcadores):
            saida.append(marcadores[indice])
    resultado = "".join(saida)
    if numeros(texto) != numeros(resultado):
        raise ValueError(
            f"Números diferentes no texto completo: "
            f"original={numeros(texto)!r} | tradução={numeros(resultado)!r}"
        )
    if PADRAO_MARCADOR.findall(texto) != PADRAO_MARCADOR.findall(resultado):
        raise ValueError("A tradução alterou marcadores matemáticos.")
    return resultado


def montar_registro(item, tradutor, modo="normal"):
    """Mantém exatamente os seis campos definidos para cada problema."""
    registro = {
        "id": item["id"],
        "split": item["split"],
        "question_en": item["question"],
        "question_pt": traduzir(item["question"], tradutor, modo),
        "answer_en": item["answer"],
        "answer_pt": traduzir(item["answer"], tradutor, modo),
    }
    if not registro_valido(registro, item):
        raise ValueError("Tradução não passou na validação.")
    return registro


def registro_valido(registro, item):
    """Verifica estrutura e números, sem prometer equivalência semântica."""
    if not isinstance(registro, dict):
        return False
    if registro.get("id") != item["id"] or registro.get("split") != item["split"]:
        return False
    if registro.get("question_en") != item["question"]:
        return False
    if registro.get("answer_en") != item["answer"]:
        return False
    if not isinstance(registro.get("question_pt"), str) or not registro["question_pt"].strip():
        return False
    if not isinstance(registro.get("answer_pt"), str) or not registro["answer_pt"].strip():
        return False
    try:
        return (
            numeros(item["question"]) == numeros(registro["question_pt"])
            and numeros(item["answer"]) == numeros(registro["answer_pt"])
            and PADRAO_MARCADOR.findall(item["answer"]) == PADRAO_MARCADOR.findall(registro["answer_pt"])
            and gabarito(item["answer"]) == gabarito(registro["answer_pt"])
        )
    except ValueError:
        return False


# TRADUÇÃO


def traduzir_dataset(dados, tradutor):
    progresso = carregar_progresso()
    print(f"Registros Argos recuperados: {len(progresso)}")
    pendentes = []
    revisao_humana = []
    total = len(dados)
    validos = 0  # Contador incremental: evita revalidar milhares de questões a cada atualização.
    alterado = False  # Só grava o progresso se alguma tradução realmente mudou.

    try:
        # PRIMEIRA PASSAGEM: reaproveita traduções válidas já salvas.
        for indice, item in enumerate(dados, 1):
            anterior = progresso.get(item["id"])
            if registro_valido(anterior, item):
                validos += 1
            else:
                print(f"[{indice}/{total}] Traduzindo {item['id']}")
                try:
                    # O Argos só é carregado quando realmente existe questão para traduzir.
                    if tradutor is None:
                        print("Preparando o tradutor Argos...")
                        tradutor = configurar_tradutor()
                    progresso[item["id"]] = montar_registro(item, tradutor)
                    validos += 1
                    alterado = True
                except Exception as erro:
                    pendentes.append(item)
                    print(f"  ATENÇÃO: {item['id']} pendente: {erro}")
            if indice % 500 == 0 or indice == total:
                # Evita regravar o JSON inteiro a cada 25 questões.
                if alterado:
                    salvar_progresso(list(progresso.values()))
                    alterado = False
                print(f"Processados: {indice}/{total} | válidos: "
                      f"{validos} | pendentes: {len(pendentes)}")

        # REVISÃO FINAL DAS PENDENTES
        # Tenta uma tradução com números protegidos e depois por partes.
        if pendentes:
            print(f"\nRevisando {len(pendentes)} questões pendentes...")
        for indice, item in enumerate(pendentes, 1):
            if registro_valido(progresso.get(item["id"]), item):
                continue
            print(f"[Revisão {indice}/{len(pendentes)}] {item['id']}")
            for modo in ("protegido", "partes", "blindado"):
                try:
                    registro = montar_registro(item, tradutor, modo)
                    progresso[item["id"]] = registro
                    alterado = True
                    print(f"  Recuperada com método: {modo}")
                    if modo == "blindado":
                        revisao_humana.append({
                            "id": item["id"],
                            "motivo": "Tradução blindada: conferir trechos mantidos em inglês e sentido matemático.",
                            "question_en": item["question"],
                            "question_pt": registro["question_pt"],
                            "answer_en": item["answer"],
                            "answer_pt": registro["answer_pt"]
                        })
                    break
                except Exception as erro:
                    print(f"  Tentativa '{modo}' falhou: {erro}")
                    if modo == "blindado":
                        print(f"  Questão original: {item['question'][:220]!r}")
            if indice % 50 == 0 and alterado:
                salvar_progresso(list(progresso.values()))
                alterado = False
    finally:
        # Salva inclusive quando a execução é interrompida com Ctrl+C,
        # mas somente se houver traduções novas; preserva o progresso existente.
        if alterado:
            salvar_progresso(list(progresso.values()))

    # Informa a necessidade de revisão no terminal, sem criar outro arquivo.
    if revisao_humana:
        print(f"\nATENÇÃO: {len(revisao_humana)} questões exigem revisão humana:")
        for registro in revisao_humana:
            print(f"  - {registro['id']}: {registro['motivo']}")

    faltantes = [item["id"] for item in dados
                if not registro_valido(progresso.get(item["id"]), item)]
    if faltantes:
        print(f"\nATENÇÃO: {len(faltantes)} questões ainda pendentes.")
        print("IDs para revisão manual:", ", ".join(faltantes))
        print("O JSON final existente NÃO será substituído por um dataset incompleto.")
        return None
    return [progresso[item["id"]] for item in dados]


# JSON FINAL


def gerar_json_final(traduzidos):
    resultado = {
        "dataset_info": {
            "nome": "GSM8K PT-BR",
            "data_criacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(traduzidos)
        },
        "problemas": traduzidos
    }

    # Esta função só é chamada se traduzir_dataset retornar todas as questões válidas.
    # Só atualiza o JSON final existente após todas as questões estarem válidas.
    # Não cria backups, arquivos temporários nem um novo JSON final.
    if not os.path.isfile(ARQ_FINAL):
        print(f"ATENÇÃO: JSON final não encontrado: {ARQ_FINAL}")
        print("Nenhum JSON final será criado. Verifique o caminho existente.")
        return
    salvar_json_seguro(ARQ_FINAL, resultado)

    # Confirma que o JSON final foi gravado corretamente antes de remover backups.
    with open(ARQ_FINAL, "r", encoding="utf-8") as arquivo:
        conferido = json.load(arquivo)
    if (not isinstance(conferido, dict)
            or not isinstance(conferido.get("problemas"), list)
            or len(conferido["problemas"]) != len(traduzidos)):
        raise ValueError("JSON final não passou na conferência; backup preservado.")

    # Procura backups antigos nas subpastas do GSM8K, não apenas em dois caminhos.
    # Só remove .bak de um dos três JSONs do projeto quando o original está íntegro.
    nomes_permitidos = {
        os.path.basename(ARQ_ORIGINAL),
        os.path.basename(ARQ_PROGRESSO),
        os.path.basename(ARQ_FINAL),
    }
    removidos = 0
    for pasta_atual, _, arquivos in os.walk(PASTA_BASE):
        for nome in arquivos:
            if not nome.endswith(".json.bak"):
                continue
            nome_json = nome[:-4]  # retira somente o sufixo .bak
            if nome_json not in nomes_permitidos:
                continue  # nunca apaga backups de outros arquivos
            backup = os.path.join(pasta_atual, nome)
            principal = os.path.join(pasta_atual, nome_json)
            try:
                # Nunca apaga o backup se o JSON correspondente estiver ausente
                # ou inválido. Confere a estrutura, não apenas a sintaxe.
                with open(principal, "r", encoding="utf-8") as arquivo:
                    conteudo = json.load(arquivo)
                if nome_json == os.path.basename(ARQ_FINAL):
                    if not isinstance(conteudo, dict) or not isinstance(conteudo.get("problemas"), list) or len(conteudo["problemas"]) != len(traduzidos):
                        raise ValueError("JSON final incompleto")
                elif nome_json == os.path.basename(ARQ_PROGRESSO):
                    if not isinstance(conteudo, list) and not (isinstance(conteudo, dict) and isinstance(conteudo.get("problemas"), list)):
                        raise ValueError("Estrutura de progresso inválida")
                elif not isinstance(conteudo, (list, dict)):
                    raise ValueError("Estrutura do original inválida")
                os.remove(backup)
                removidos += 1
                print(f"Backup removido: {backup}")
            except (OSError, ValueError, json.JSONDecodeError) as erro:
                print(f"Backup preservado: {backup} ({erro})")
    print(f"Limpeza concluída: {removidos} backup(s) removido(s).")


# MAIN


def main():
    print("=" * 60)
    print("GSM8K PT-BR (Argos Translate)")
    print("=" * 60)

    dados = carregar_original()
    print(f"Total de questões originais: {len(dados)}")
    # Carregamento sob demanda: não ocupa memória com Argos quando tudo já está traduzido.
    traduzidos = traduzir_dataset(dados, None)
    if traduzidos is None:
        print("Tradução parcial salva em:", ARQ_PROGRESSO)
        return
    gerar_json_final(traduzidos)
    print("\nConcluído!")
    print(f"Total traduzido: {len(traduzidos)}")
    print(f"JSON final: {ARQ_FINAL}")
  


if __name__ == "__main__":
    main()