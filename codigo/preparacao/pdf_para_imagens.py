import fitz
from pathlib import Path

PDFS = Path("dados/enem/pdfs")
SAIDA = Path("dados/enem/imagens")

for pasta_ano in PDFS.iterdir():

    if not pasta_ano.is_dir():
        continue

    ano = pasta_ano.name

    pdf = pasta_ano / f"prova_{ano}.pdf"

    if not pdf.exists():
        continue

    destino = SAIDA / ano
    destino.mkdir(parents=True, exist_ok=True)

    print(f"\nConvertendo {ano}")

    documento = fitz.open(pdf)

    for pagina in range(len(documento)):

        page = documento[pagina]

        pix = page.get_pixmap(
            matrix=fitz.Matrix(2, 2)
        )

        arquivo = destino / f"pagina_{pagina+1}.png"

        pix.save(arquivo)

    print(
        f"{len(documento)} páginas salvas"
    )