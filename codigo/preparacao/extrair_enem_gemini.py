
import os
import re
import json
import time
import io
import fitz
from PIL import Image
from google import genai
from google.genai import types

# =====================================================
# CONFIGURAÇÃO
# =====================================================

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Kb2tTS5TwKnO4IPjlofG6Evhol7uEOGpVQFEd2u7Fsjw")

if not GEMINI_KEY:
    raise ValueError("Defina a variável GEMINI_API_KEY.")

client = genai.Client(api_key=GEMINI_KEY)

MODELO = "gemini-2.5-flash"

PASTA_PDFS = "dados/enem/pdfs"
PASTA_SAIDA = "dados/enem/extraidos"
PASTA_IMAGENS = "dados/enem/imagens_questoes"

os.makedirs(PASTA_SAIDA, exist_ok=True)
os.makedirs(PASTA_IMAGENS, exist_ok=True)

# =====================================================
# PROMPT
# =====================================================

PROMPT = """
Você receberá UMA página de uma prova do ENEM.

Extraia SOMENTE questões de Matemática, isto é, questões de número 136 a 180.

Se a página não tiver questões de Matemática, retorne:
{
  "questoes": []
}

Para cada questão de Matemática encontrada, retorne:
{
  "numero": 145,
  "enunciado": "...",
  "tem_imagem": true,
  "tipo_imagem": "grafico",
  "descricao_visual": "...",
  "bbox_questao": [x1, y1, x2, y2],
  "bbox_visual": [x1, y1, x2, y2],
  "alternativas": {
    "A": "...",
    "B": "...",
    "C": "...",
    "D": "...",
    "E": "..."
  }
}

Regras:
1. Retorne SOMENTE JSON válido.
2. Não use markdown.
3. Extraia apenas questões 136 a 180.
4. Preserve enunciado, fórmulas, unidades e alternativas.
5. Se houver gráfico, tabela, figura, mapa, diagrama ou desenho, use tem_imagem true.
6. bbox_questao deve envolver a questão COMPLETA, incluindo enunciado, imagem, tabela, gráfico e alternativas.
7. Prefira uma bbox_questao MAIOR. Nunca corte partes da questão.
8. bbox_visual pode envolver apenas o elemento visual.
9. Se não houver elemento visual, use bbox_visual: [].
10. As coordenadas bbox devem estar em escala de 0 a 1000.

Formato final:
{
  "questoes": []
}
"""

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================

def limpar_json(texto):
    if not texto:
        return ""

    texto = texto.strip()
    texto = texto.replace("```json", "")
    texto = texto.replace("```", "")

    inicio = texto.find("{")

    if inicio == -1:
        return ""

    contador = 0
    fim = -1

    for i in range(inicio, len(texto)):
        if texto[i] == "{":
            contador += 1
        elif texto[i] == "}":
            contador -= 1

            if contador == 0:
                fim = i
                break

    if fim != -1:
        return texto[inicio:fim + 1]

    return ""


def renderizar_pagina(pagina, escala=2):
    pix = pagina.get_pixmap(
        matrix=fitz.Matrix(escala, escala),
        alpha=False
    )

    return Image.open(
        io.BytesIO(pix.tobytes("png"))
    ).convert("RGB")


def imagem_para_part(img):
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    return types.Part.from_bytes(
        data=buffer.getvalue(),
        mime_type="image/png"
    )


def bbox_1000_para_pixels(bbox, largura, altura):
    if not bbox or len(bbox) != 4:
        return None

    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except Exception:
        return None

    x1 = int((x1 / 1000) * largura)
    y1 = int((y1 / 1000) * altura)
    x2 = int((x2 / 1000) * largura)
    y2 = int((y2 / 1000) * altura)

    x1 = max(0, min(x1, largura))
    y1 = max(0, min(y1, altura))
    x2 = max(0, min(x2, largura))
    y2 = max(0, min(y2, altura))

    if x2 <= x1 or y2 <= y1:
        return None

    return x1, y1, x2, y2


def salvar_recorte(img, bbox, caminho, margem=100):
    largura, altura = img.size
    coords = bbox_1000_para_pixels(bbox, largura, altura)

    if coords is None:
        return False

    x1, y1, x2, y2 = coords

    x1 = max(0, x1 - margem)
    y1 = max(0, y1 - margem)
    x2 = min(largura, x2 + margem)
    y2 = min(altura, y2 + margem)

    recorte = img.crop((x1, y1, x2, y2))
    recorte.save(caminho)

    return True


def pagina_tem_matematica(texto):
    texto = texto.lower()

    padroes = [
        r"quest[aã]o\s+1[3-7][0-9]",
        r"quest[aã]o\s+180",
        r"\b1[3-7][0-9]\s*[.)-]",
        r"\b180\s*[.)-]"
    ]

    for padrao in padroes:
        if re.search(padrao, texto):
            return True

    return False


def encontrar_paginas_candidatas(doc):
    paginas = []

    for i in range(len(doc)):
        texto = doc[i].get_text()

        if pagina_tem_matematica(texto):
            paginas.append(i)

    return paginas


def carregar_json_parcial(caminho):
    modelo_vazio = {
        "ano": None,
        "total_questoes": 0,
        "paginas_processadas": [],
        "questoes": []
    }

    if not os.path.exists(caminho):
        return modelo_vazio

    if os.path.getsize(caminho) == 0:
        return modelo_vazio

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)

    except json.JSONDecodeError:
        print(f"JSON inválido encontrado: {caminho}")
        print("Recriando JSON limpo.")
        return modelo_vazio

    dados.setdefault("ano", None)
    dados.setdefault("questoes", [])
    dados.setdefault("paginas_processadas", [])
    dados.setdefault("total_questoes", len(dados["questoes"]))

    return dados


def salvar_json(caminho, dados):
    dados["questoes"] = sorted(
        dados["questoes"],
        key=lambda q: q.get("numero", 0)
    )

    dados["paginas_processadas"] = sorted(
        list(set(dados.get("paginas_processadas", [])))
    )

    dados["total_questoes"] = len(dados["questoes"])

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(
            dados,
            f,
            ensure_ascii=False,
            indent=2
        )

# =====================================================
# GEMINI
# =====================================================

def extrair_questoes_da_pagina(img, numero_pagina):
    prompt = PROMPT + f"\n\nEsta é a página {numero_pagina} da prova."

    tentativas = 0

    while tentativas < 4:
        try:
            resposta = client.models.generate_content(
                model=MODELO,
                contents=[
                    prompt,
                    imagem_para_part(img)
                ],
                config={
                    "temperature": 0,
                    "response_mime_type": "application/json"
                }
            )

            texto_resposta = getattr(resposta, "text", None)

            if not texto_resposta:
                print(f"  Resposta vazia na página {numero_pagina}")
                return {"questoes": []}

            texto = limpar_json(texto_resposta)

            if not texto:
                return {"questoes": []}

            try:
                return json.loads(texto)

            except Exception as e:
                print(f"  JSON inválido na página {numero_pagina}: {e}")

                arquivo_debug = f"debug_pagina_{numero_pagina}.txt"

                with open(arquivo_debug, "w", encoding="utf-8") as f:
                    f.write(texto)

                return {"questoes": []}

        except Exception as e:
            erro = str(e)

            if "503" in erro or "UNAVAILABLE" in erro:
                espera = 30 * (tentativas + 1)
                print(f"  Modelo indisponível. Tentando de novo em {espera}s...")
                time.sleep(espera)
                tentativas += 1
                continue

            if "429" in erro or "RESOURCE_EXHAUSTED" in erro:
                print("  Limite diário/minuto da API atingido.")
                print("  Salvando progresso e parando este ano.")
                raise RuntimeError("LIMITE_API_GEMINI")

            if "Name or service not known" in erro:
                espera = 60
                print(f"  Erro de conexão. Tentando de novo em {espera}s...")
                time.sleep(espera)
                tentativas += 1
                continue

            raise

    raise Exception(f"Falhou após várias tentativas na página {numero_pagina}")

# =====================================================
# PROCESSAR ANO
# =====================================================

def processar_ano(ano):
    pdf_path = os.path.join(
        PASTA_PDFS,
        ano,
        f"prova_{ano}.pdf"
    )

    if not os.path.exists(pdf_path):
        print(f"PDF não encontrado: {pdf_path}")
        return

    print(f"\nProcessando {ano}")

    pasta_imagens_ano = os.path.join(
        PASTA_IMAGENS,
        ano
    )

    os.makedirs(pasta_imagens_ano, exist_ok=True)

    caminho_saida = os.path.join(
        PASTA_SAIDA,
        f"enem_{ano}.json"
    )

    saida = carregar_json_parcial(caminho_saida)
    saida["ano"] = int(ano)
    saida.setdefault("paginas_processadas", [])
    saida.setdefault("questoes", [])
    saida.setdefault("total_questoes", 0)

    paginas_processadas = set(saida["paginas_processadas"])

    doc = fitz.open(pdf_path)

    paginas_candidatas = encontrar_paginas_candidatas(doc)

    if not paginas_candidatas:
        print("Nenhuma página candidata encontrada. Verifique o PDF.")
        doc.close()
        return

    print(
        "Páginas candidatas:",
        [p + 1 for p in paginas_candidatas]
    )

    for indice_pagina in paginas_candidatas:
        numero_pagina = indice_pagina + 1

        if numero_pagina in paginas_processadas:
            print(f"  Página {numero_pagina} já processada. Pulando.")
            continue

        print(f"  Página {numero_pagina}/{len(doc)}")

        pagina = doc[indice_pagina]
        img = renderizar_pagina(pagina)

        try:
            resultado = extrair_questoes_da_pagina(
                img,
                numero_pagina
            )

        except RuntimeError as e:
            if str(e) == "LIMITE_API_GEMINI":
                salvar_json(caminho_saida, saida)
                doc.close()
                print("Progresso salvo. Rode novamente quando a cota liberar.")
                return

            raise

        except Exception as e:
            print(f"  Erro na página {numero_pagina}: {e}")
            salvar_json(caminho_saida, saida)
            time.sleep(30)
            continue

        questoes = resultado.get("questoes", [])

        for questao in questoes:
            numero = questao.get("numero")

            try:
                numero = int(numero)
            except Exception:
                continue

            if numero < 136 or numero > 180:
                continue

            questao["ano"] = int(ano)
            questao["pagina"] = numero_pagina

            if questao.get("tem_imagem", False):
                bbox_visual = questao.get("bbox_visual", [])
                bbox_questao = questao.get("bbox_questao", [])

                nome_img = f"enem_{ano}_q{numero}_p{numero_pagina}.png"

                caminho_img = os.path.join(
                    pasta_imagens_ano,
                    nome_img
                )

                salvou = False

                # PRIORIDADE: questão inteira, com margem.
                if bbox_questao:
                    salvou = salvar_recorte(
                        img,
                        bbox_questao,
                        caminho_img,
                        margem=140
                    )

                # Reserva: visual com margem maior.
                if not salvou and bbox_visual:
                    salvou = salvar_recorte(
                        img,
                        bbox_visual,
                        caminho_img,
                        margem=180
                    )

                if salvou:
                    questao["imagens"] = [
                        os.path.join(
                            "dados/enem/imagens_questoes",
                            ano,
                            nome_img
                        )
                    ]
                else:
                    questao["imagens"] = []

            else:
                questao["imagens"] = []

            saida["questoes"] = [
                q for q in saida["questoes"]
                if not (
                    q.get("numero") == numero
                    and q.get("ano") == int(ano)
                )
            ]

            saida["questoes"].append(questao)

        if numero_pagina not in saida["paginas_processadas"]:
            saida["paginas_processadas"].append(numero_pagina)

        salvar_json(caminho_saida, saida)

        print(f"  Página {numero_pagina} salva.")
        time.sleep(20)

    doc.close()

    salvar_json(caminho_saida, saida)

    print(f"Salvo: {caminho_saida}")
    print(f"Questões extraídas: {len(saida['questoes'])}")

# =====================================================
# MAIN
# =====================================================

def main():
    anos = sorted([
        p
        for p in os.listdir(PASTA_PDFS)
        if os.path.isdir(
            os.path.join(PASTA_PDFS, p)
        )
    ])

    print(f"{len(anos)} anos encontrados.")

    for ano in anos:
        try:
            processar_ano(ano)

        except Exception as e:
            print(f"Erro {ano}: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()