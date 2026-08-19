import os #arquivos do pc
import re # encontrar questão ou alternativas
import json
import fitz # abrir pdfs, localizar textos

PASTA_PDFS = "dados/enem/pdfs"
PASTA_SAIDA = "dados/enem/extraidos"
PASTA_IMAGENS = "dados/enem/imagens_questoes"
PASTA_FINAL = "dados/enem/final"

os.makedirs(PASTA_SAIDA, exist_ok=True) # se já existe não dê erro
os.makedirs(PASTA_IMAGENS, exist_ok=True)
os.makedirs(PASTA_FINAL, exist_ok=True)


def normalizar_texto(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


def extrair_gabarito(gabarito_path):
    respostas = {}

    if not os.path.exists(gabarito_path):
        print(f"Gabarito não encontrado: {gabarito_path}")
        return respostas

    doc = fitz.open(gabarito_path)
    texto = "\n".join(page.get_text() for page in doc)
    doc.close()

    pares = re.findall(
        r"\b(\d{2,3})\s+(A|B|C|D|E|Anulado)\b",
        texto,
        re.I
    )

    for numero, resposta in pares:
        numero = int(numero)
        resposta = resposta.upper()

        if 136 <= numero <= 180 and numero not in respostas:
            respostas[numero] = resposta

    return respostas


def encontrar_questoes_pagina(texto):
    encontrados = []

    for m in re.finditer(
        r"Quest[aã]o\s*(\d{3})|QUEST[AÃ]O\s*(\d{3})|Questao\s*(\d{3})|QUESTAO\s*(\d{3})",
        texto,
        re.I
    ):
        grupos = [g for g in m.groups() if g]

        if not grupos:
            continue

        numero = int(grupos[0])

        if 136 <= numero <= 180:
            encontrados.append((numero, m.start()))

    return sorted(set(encontrados), key=lambda x: x[1])


def localizar_rect_questao(pagina, numero):
    termos = [
        f"Questão {numero}",
        f"QUESTÃO {numero}",
        f"Questao {numero}",
        f"QUESTAO {numero}"
    ]

    rects = []

    for termo in termos:
        rects.extend(pagina.search_for(termo))

    if not rects:
        return None

    return sorted(rects, key=lambda r: (r.y0, r.x0))[0]


def obter_marcadores_pagina(pagina, numeros):
    marcadores = []

    for numero in numeros:
        rect = localizar_rect_questao(pagina, numero)

        if rect:
            marcadores.append({
                "numero": numero,
                "rect": rect,
                "x": rect.x0,
                "y": rect.y0
            })

    return marcadores


def obter_rect_recorte(pagina, marcador, marcadores):
    largura = pagina.rect.width
    altura = pagina.rect.height
    meio = largura / 2

    if marcador["x"] < meio:
        x1 = 0
        x2 = meio
        proximas = [
            m for m in marcadores
            if m["x"] < meio and m["y"] > marcador["y"]
        ]
    else:
        x1 = meio
        x2 = largura
        proximas = [
            m for m in marcadores
            if m["x"] >= meio and m["y"] > marcador["y"]
        ]

    proximas = sorted(proximas, key=lambda m: m["y"])

    y1 = max(0, marcador["y"] - 8)

    if proximas:
        y2 = proximas[0]["y"] - 5
    else:
        y2 = altura - 25

    return fitz.Rect(x1, y1, x2, y2)


def extrair_texto_clip(pagina, rect):
    return pagina.get_text("text", clip=rect)


def detectar_contextos_compartilhados(texto_pagina):
    contextos = []

    padrao = re.compile(
        r"(Texto para as questões\s+(\d{3})\s+e\s+(\d{3}).*?)(?=Quest[aã]o\s+\d{3})",
        re.I | re.S
    )

    for m in padrao.finditer(texto_pagina):
        contexto = normalizar_texto(m.group(1))
        q1 = int(m.group(2))
        q2 = int(m.group(3))

        for q in range(q1, q2 + 1):
            contextos.append({
                "numero": q,
                "contexto": contexto
            })

    return contextos


def extrair_bloco_texto(texto, numero, proximo_numero=None):
    inicio = re.search(
        rf"Quest[aã]o\s*{numero}\b|QUEST[AÃ]O\s*{numero}\b|Questao\s*{numero}\b|QUESTAO\s*{numero}\b",
        texto,
        re.I
    )

    if not inicio:
        return ""

    ini = inicio.start()
    fim = len(texto)

    if proximo_numero:
        prox = re.search(
            rf"Quest[aã]o\s*{proximo_numero}\b|QUEST[AÃ]O\s*{proximo_numero}\b|Questao\s*{proximo_numero}\b|QUESTAO\s*{proximo_numero}\b",
            texto[ini + 1:],
            re.I
        )

        if prox:
            fim = ini + 1 + prox.start()

    return texto[ini:fim].strip()


def separar_alternativas(texto):
    texto = normalizar_texto(texto)

    padrao = re.compile(
        r"\bA\s+(.+?)\s+B\s+(.+?)\s+C\s+(.+?)\s+D\s+(.+?)\s+E\s+(.+)$",
        re.S
    )

    matches = list(padrao.finditer(texto))

    if not matches:
        return {}

    m = matches[-1]

    return {
        "A": normalizar_texto(m.group(1)),
        "B": normalizar_texto(m.group(2)),
        "C": normalizar_texto(m.group(3)),
        "D": normalizar_texto(m.group(4)),
        "E": normalizar_texto(m.group(5))
    }


def remover_alternativas_do_enunciado(texto):
    texto = normalizar_texto(texto)

    padrao = re.compile(
        r"\bA\s+.+?\s+B\s+.+?\s+C\s+.+?\s+D\s+.+?\s+E\s+.+$",
        re.S
    )

    matches = list(padrao.finditer(texto))

    if not matches:
        return texto

    return texto[:matches[-1].start()].strip()


def detectar_visual_por_texto(texto):
    texto = texto.lower()

    palavras = [
        "figura",
        "gráfico",
        "grafico",
        "tabela",
        "quadro",
        "mapa",
        "diagrama",
        "desenho",
        "imagem",
        "ao lado",
        "a seguir",
        "representa",
        "mostra",
        "observe",
        "esquema",
        "exibem"
    ]

    return any(p in texto for p in palavras)


def detectar_visual_por_pdf(pagina, rect):
    for img in pagina.get_images(full=True):
        xref = img[0]

        try:
            rects = pagina.get_image_rects(xref)
        except Exception:
            rects = []

        for r in rects:
            inter = r & rect

            if not inter.is_empty and inter.get_area() > 500:
                return True

    return False


def salvar_recorte_questao(pagina, rect, caminho):
    pix = pagina.get_pixmap(
        matrix=fitz.Matrix(3, 3),
        clip=rect,
        alpha=False
    )

    pix.save(caminho)


def processar_ano(ano):
    pdf_path = os.path.join(
        PASTA_PDFS,
        ano,
        f"prova_{ano}.pdf"
    )

    gabarito_path = os.path.join(
        PASTA_PDFS,
        ano,
        f"gabarito_{ano}.pdf"
    )

    if not os.path.exists(pdf_path):
        print(f"PDF não encontrado: {pdf_path}")
        return []

    print(f"\nProcessando {ano}")

    gabarito = extrair_gabarito(gabarito_path)

    print(f"Gabaritos encontrados: {len(gabarito)}")

    pdf = fitz.open(pdf_path)

    pasta_img_ano = os.path.join(PASTA_IMAGENS, ano)
    os.makedirs(pasta_img_ano, exist_ok=True)

    questoes = []

    for i in range(len(pdf)):
        pagina = pdf[i]
        texto_pagina = pagina.get_text()

        encontrados = encontrar_questoes_pagina(texto_pagina)

        if not encontrados:
            continue

        numeros = [n for n, _ in encontrados]
        marcadores = obter_marcadores_pagina(pagina, numeros)
        contextos = detectar_contextos_compartilhados(texto_pagina)

        contexto_por_questao = {
            c["numero"]: c["contexto"]
            for c in contextos
        }

        for idx, numero in enumerate(numeros):
            marcador = next(
                (m for m in marcadores if m["numero"] == numero),
                None
            )

            if not marcador:
                continue

            rect = obter_rect_recorte(
                pagina,
                marcador,
                marcadores
            )

            bloco = extrair_texto_clip(pagina, rect)

            if not bloco:
                continue

            alternativas = separar_alternativas(bloco)
            enunciado = remover_alternativas_do_enunciado(bloco)

            contexto = contexto_por_questao.get(numero, "")

            if contexto and contexto not in enunciado:
                enunciado = normalizar_texto(contexto + " " + enunciado)

            tem_imagem = (
                detectar_visual_por_texto(bloco)
                or detectar_visual_por_pdf(pagina, rect)
            )

            imagens = []

            if tem_imagem:
                nome_img = f"enem_{ano}_q{numero}_p{i+1}.png"

                caminho_img = os.path.join(
                    pasta_img_ano,
                    nome_img
                )

                salvar_recorte_questao(
                    pagina,
                    rect,
                    caminho_img
                )

                imagens = [
                    os.path.join(
                        PASTA_IMAGENS,
                        ano,
                        nome_img
                    )
                ]

            questoes.append({
                "ano": int(ano),
                "numero": numero,
                "pagina": i + 1,
                "enunciado": enunciado,
                "tem_imagem": bool(imagens),
                "imagens": imagens,
                "alternativas": alternativas,
                "gabarito": gabarito.get(numero, "")
            })

    pdf.close()

    unicas = {}

    for q in questoes:
        if q["numero"] not in unicas:
            unicas[q["numero"]] = q

    questoes = sorted(
        unicas.values(),
        key=lambda q: q["numero"]
    )

    saida = {
        "ano": int(ano),
        "total_questoes": len(questoes),
        "questoes": questoes
    }

    caminho_json = os.path.join(
        PASTA_SAIDA,
        f"enem_{ano}.json"
    )

    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(
            saida,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"Salvo: {caminho_json}")
    print(f"Questões extraídas: {len(questoes)}")

    sem_gabarito = [
        q["numero"]
        for q in questoes
        if not q["gabarito"]
    ]

    if sem_gabarito:
        print(f"Sem gabarito: {sem_gabarito}")

    return questoes


def main():
    anos = sorted([
        p for p in os.listdir(PASTA_PDFS)
        if os.path.isdir(os.path.join(PASTA_PDFS, p))
    ])

    print(f"{len(anos)} anos encontrados.")

    todas = []

    for ano in anos:
        questoes = processar_ano(ano)
        todas.extend(questoes)

    caminho_final = os.path.join(
        PASTA_FINAL,
        "enem_matematica_completo.json"
    )

    with open(caminho_final, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total_questoes": len(todas),
                "questoes": todas
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"\nJSON final salvo: {caminho_final}")
    print(f"Total geral: {len(todas)}")


if __name__ == "__main__":
    main()