import argparse
import csv
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

# Endereço do pacote oficial
URL_CENSO = "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2025_.zip"
PASTA_CENSO = Path("dados/censo_escolar")
PASTA_ORIGINAL = PASTA_CENSO / "originais"
PASTA_EXTRAIDA = PASTA_ORIGINAL / "microdados_2025"
ARQUIVO_ZIP = PASTA_ORIGINAL / "microdados_censo_escolar_2025_.zip"
ARQUIVO_QUESTOES = PASTA_CENSO / "final" / "censo_escolar_2025.json"

# Documento padrão: permite executar o módulo sem informar --docx.

ARQUIVO_DOCX_PADRAO = PASTA_ORIGINAL / "Censo_Escolar_2025_50_Questoes.docx"

# Reconhece "1. Pergunta" e "Bloco 1 — Título" no DOCX.
PADRAO_QUESTAO = re.compile(r"^\s*(\d{1,2})\s*\.\s*(.+)$", re.S)
PADRAO_BLOCO = re.compile(r"^Bloco\s+(\d+)(?:\s*[—–-]\s*(.*))?$", re.I)

TOTAL_QUESTOES = 50
TOTAL_ESCOLAS_REFERENCIA = 178766


def salvar_json(caminho, dados):
    """Grava o JSON com segurança, substituindo o destino somente ao terminar."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    arquivo_temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".tmp",
            dir=caminho.parent, delete=False
        ) as arquivo:
            arquivo_temporario = Path(arquivo.name)
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo_temporario.replace(caminho)
    finally:
        if arquivo_temporario is not None:
            arquivo_temporario.unlink(missing_ok=True)


def baixar_zip(url):
    """Baixa o ZIP, reutilizando um arquivo válido já existente."""
    ARQUIVO_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if ARQUIVO_ZIP.is_file() and zipfile.is_zipfile(ARQUIVO_ZIP):
        print(f"ZIP já baixado: {ARQUIVO_ZIP}")
        return
    arquivo_parcial = ARQUIVO_ZIP.with_suffix(".zip.part")
    print("Baixando microdados oficiais do Inep...")
    try:
        pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(pedido, timeout=120) as resposta, arquivo_parcial.open("wb") as saida:
            shutil.copyfileobj(resposta, saida, length=1024 * 1024)
        if not zipfile.is_zipfile(arquivo_parcial):
            raise ValueError("O download não resultou em um ZIP válido.")
        arquivo_parcial.replace(ARQUIVO_ZIP)
    finally:
        arquivo_parcial.unlink(missing_ok=True)


def escolher_arquivos_do_zip(pacote):
    """Seleciona uma tabela de matrícula e os dicionários/arquivos explicativos."""
    arquivos = [arquivo for arquivo in pacote.infolist() if not arquivo.is_dir()]
    tabelas = [
        arquivo for arquivo in arquivos
        if Path(arquivo.filename).suffix.lower() == ".csv"
        and "matricula" in arquivo.filename.lower().replace("í", "i")
    ]
    if not tabelas:
        raise FileNotFoundError("Não encontrei um CSV de matrícula no ZIP. Confira a versão do pacote.")
    # Primeiro procura a versão exata do professor; depois, a maior tabela candidata.
    tabelas.sort(key=lambda arquivo: (
        Path(arquivo.filename).name.casefold() != "tabela_matricula_2025_v2.csv",
        -arquivo.file_size,
    ))
    tabela_escolhida = tabelas[0]
    auxiliares = [
        arquivo for arquivo in arquivos
        if arquivo != tabela_escolhida
        and any(palavra in arquivo.filename.casefold() for palavra in
                ("dicion", "layout", "leia-me", "leia_me", "instru", "nota_tecnica"))
        and Path(arquivo.filename).suffix.lower() in
        {".xlsx", ".xls", ".csv", ".pdf", ".txt", ".ods", ".docx"}
    ]
    return tabela_escolhida, auxiliares


def extrair_arquivos():
    """Extrai apenas os arquivos úteis; impede sobrescrever nomes repetidos no ZIP."""
    PASTA_EXTRAIDA.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARQUIVO_ZIP) as pacote:
        tabela, auxiliares = escolher_arquivos_do_zip(pacote)
        selecionados = [tabela, *auxiliares]
        nomes = [Path(arquivo.filename).name.casefold() for arquivo in selecionados]
        if len(nomes) != len(set(nomes)):
            raise ValueError("O ZIP possui arquivos selecionados com nomes repetidos. Extração interrompida.")
        for arquivo in selecionados:
            destino = PASTA_EXTRAIDA / Path(arquivo.filename).name
            # Não confia apenas no tamanho: extrai de novo para evitar arquivos antigos.
            arquivo_parcial = destino.with_name(destino.name + ".part")
            try:
                with pacote.open(arquivo) as origem, arquivo_parcial.open("wb") as saida:
                    shutil.copyfileobj(origem, saida, length=1024 * 1024)
                if arquivo_parcial.stat().st_size != arquivo.file_size:
                    raise ValueError(f"Extração incompleta: {destino.name}")
                arquivo_parcial.replace(destino)
            finally:
                arquivo_parcial.unlink(missing_ok=True)
            print(f"Extraído: {destino.name}")
    return PASTA_EXTRAIDA / Path(tabela.filename).name


def conferir_csv(caminho_csv):
    """Confere cabeçalho e número de registros sem carregar a tabela na memória."""
    codificacao = "utf-8-sig"
    try:
        with caminho_csv.open(encoding=codificacao) as arquivo:
            amostra = arquivo.read(8192)
    except UnicodeDecodeError:
        codificacao = "latin-1"
        with caminho_csv.open(encoding=codificacao) as arquivo:
            amostra = arquivo.read(8192)
    # O CSV do Inep costuma usar ponto e vírgula.
    delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
    with caminho_csv.open(encoding=codificacao, newline="") as arquivo:
        leitor = csv.reader(arquivo, delimiter=delimitador)
        colunas = next(leitor, [])
        total_registros = sum(1 for linha in leitor if linha)
    if "QT_MAT_BAS" not in colunas:
        raise ValueError("A tabela selecionada não possui a coluna QT_MAT_BAS.")
    print(f"Tabela: {caminho_csv.name}")
    print(f"Escolas/registros: {total_registros:,} | Colunas: {len(colunas)}")
    if caminho_csv.name.casefold() != "tabela_matricula_2025_v2.csv":
        print("AVISO: nome diferente da Tabela_Matricula_2025_V2.csv usada pelo professor.")
    if total_registros != TOTAL_ESCOLAS_REFERENCIA:
        print(f"AVISO: o professor utilizou {TOTAL_ESCOLAS_REFERENCIA:,} escolas. "
              "A equivalência da base não foi confirmada.")
    return total_registros


def ler_elementos_docx(documento):
    """Percorre parágrafos e tabelas na mesma ordem em que aparecem no Word."""
    for elemento in documento.element.body.iterchildren():
        if elemento.tag == qn("w:p"):
            yield "paragrafo", Paragraph(elemento, documento).text.strip()
        elif elemento.tag == qn("w:tbl"):
            tabela = Table(elemento, documento)
            linhas = []
            for linha in tabela.rows:
                celulas = [celula.text.strip().replace("\n", " / ") for celula in linha.cells]
                linhas.append(" | ".join(celulas))
            yield "tabela", "\n".join(linhas)


def converter_questoes_docx(caminho_docx):
    """Transforma as 50 perguntas e respostas em JSON, validando numeração e blocos."""
    if not caminho_docx.is_file():
        raise FileNotFoundError(f"DOCX não encontrado: {caminho_docx}")
    secao_atual = None
    bloco_atual = None
    numero_atual = None
    temas_dos_blocos = {}
    perguntas = {}
    respostas = {}
    for tipo, texto in ler_elementos_docx(Document(caminho_docx)):
        if not texto:
            continue
        if tipo == "paragrafo" and "PARTE I" in texto and "QUESTÕES" in texto:
            secao_atual, bloco_atual, numero_atual = "perguntas", None, None
            continue
        if tipo == "paragrafo" and "PARTE II" in texto and "RESPOSTAS" in texto:
            secao_atual, bloco_atual, numero_atual = "respostas", None, None
            continue
        if tipo == "paragrafo" and texto.casefold() == "fontes":
            break
        if secao_atual is None:
            continue
        bloco_encontrado = PADRAO_BLOCO.fullmatch(texto) if tipo == "paragrafo" else None
        if bloco_encontrado:
            bloco_atual = int(bloco_encontrado.group(1))
            if secao_atual == "perguntas":
                temas_dos_blocos[bloco_atual] = bloco_encontrado.group(2) or ""
            numero_atual = None
            continue
        numero_encontrado = PADRAO_QUESTAO.match(texto) if tipo == "paragrafo" else None
        itens = perguntas if secao_atual == "perguntas" else respostas
        if numero_encontrado:
            numero_atual = int(numero_encontrado.group(1))
            if numero_atual in itens:
                raise ValueError(f"Questão repetida em {secao_atual}: {numero_atual}")
            itens[numero_atual] = {
                "texto": numero_encontrado.group(2).strip(), "bloco": bloco_atual
            }
        elif numero_atual is not None:
            # Parágrafos de continuação e tabelas pertencem à questão anterior.
            separador = "\n" if tipo == "tabela" else " "
            itens[numero_atual]["texto"] += separador + texto
    numeros_esperados = set(range(1, TOTAL_QUESTOES + 1))
    if set(perguntas) != numeros_esperados or set(respostas) != numeros_esperados:
        raise ValueError("DOCX incompleto: não foram encontradas as 50 perguntas e respostas. "
                         f"Perguntas: {sorted(perguntas)}; respostas: {sorted(respostas)}")
    questoes = []
    for numero in range(1, TOTAL_QUESTOES + 1):
        pergunta = perguntas[numero]
        resposta = respostas[numero]
        if pergunta["bloco"] is None or pergunta["bloco"] != resposta["bloco"]:
            raise ValueError(f"Bloco ausente ou divergente na questão {numero}")
        questoes.append({
            "id": f"censo_2025_{numero:02d}",
            "pergunta": pergunta["texto"],
            "resposta_esperada": resposta["texto"],
        })
    return {
        "dataset_info": {
            "nome": "Censo Escolar 2025 — 50 questões do professor",
            "total": len(questoes),
        },
        "questoes": questoes,
    }


def executar():
    """Coordena download, extração, validação e conversão, preservando o ZIP."""
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument(
        "--docx",
        type=Path,
        default=ARQUIVO_DOCX_PADRAO,
        help="Caminho do DOCX com as 50 questões (opcional).",
    )
    argumentos.add_argument("--url", default=URL_CENSO, help="URL do ZIP oficial do Inep")
    argumentos.add_argument("--sem-download", action="store_true",
                            help="Usa ZIP já existente, sem baixar novamente")
    opcoes = argumentos.parse_args()
    # Verifica o documento antes de iniciar um download potencialmente grande.
    if not opcoes.docx.is_file():
        raise FileNotFoundError(f"DOCX não encontrado: {opcoes.docx}")
    if not opcoes.sem_download:
        baixar_zip(opcoes.url)
    if not ARQUIVO_ZIP.is_file() or not zipfile.is_zipfile(ARQUIVO_ZIP):
        raise FileNotFoundError(f"ZIP não encontrado ou inválido: {ARQUIVO_ZIP}")
    caminho_csv = extrair_arquivos()
    conferir_csv(caminho_csv)
    dados_questoes = converter_questoes_docx(opcoes.docx)
    salvar_json(ARQUIVO_QUESTOES, dados_questoes)
    print(f"50 questões salvas em: {ARQUIVO_QUESTOES}")
    # Mantém o ZIP original para reproduzir o experimento ou reextrair os dados.
    print(f"ZIP original preservado em: {ARQUIVO_ZIP}")
    print("IMPORTANTE: não fornecer 'resposta_esperada' ao modelo.")


if __name__ == "__main__":
    executar()