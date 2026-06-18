from pathlib import Path
from pypdf import PdfReader
import shutil
import re
import unicodedata

ORIGEM = "/home/palinux/Área de trabalho/Concursos/PDFs FGV - Páginas 1 a 5/Prova"
DESTINO = "/home/palinux/Área de trabalho/Concursos/PDFs FGV - Páginas 1 a 5/Provas por Matérias/Analista de Tecnologia"

TERMOS = [
    "Tecnologia em Informação",
    "Tecnologia da Informação",
    "Analista em Tecnologia",
    "Analista de Tecnologia",
    "Analista de Sistemas",
    "Analista de Sistema"
]


def remover_acentos(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


def reorganizar_duas_colunas(texto_pagina):
    """
    Tenta reorganizar PDFs em duas colunas.
    """

    coluna_esquerda = []
    coluna_direita = []

    linhas = texto_pagina.splitlines()

    for linha in linhas:

        encontrado = re.search(r' {5,}', linha)

        if encontrado:

            esquerda = linha[:encontrado.start()].rstrip()
            direita = linha[encontrado.end():].rstrip()

            if esquerda:
                coluna_esquerda.append(esquerda)

            if direita:
                coluna_direita.append(direita)

        else:
            coluna_esquerda.append(linha.rstrip())

    return "\n".join(coluna_esquerda) + "\n" + "\n".join(coluna_direita)


def obter_nome_destino(destino):

    if not destino.exists():
        return destino

    contador = 1

    while True:

        novo = destino.with_name(
            f"{destino.stem}_{contador}{destino.suffix}"
        )

        if not novo.exists():
            return novo

        contador += 1


Path(DESTINO).mkdir(parents=True, exist_ok=True)

total_pdfs = 0
total_copiados = 0

for pdf in Path(ORIGEM).rglob("*.pdf"):

    total_pdfs += 1

    cargo_encontrado = False
    conhecimentos_especificos = False

    motivo_cargo = ""

    try:

        # ====================================================
        # REGRA 1
        # PROCURA TERMOS NO NOME DO ARQUIVO
        # ====================================================

        nome_arquivo = remover_acentos(
            pdf.name.lower()
        )

        for termo in TERMOS:

            termo_normalizado = remover_acentos(
                termo.lower()
            )

            if termo_normalizado in nome_arquivo:

                cargo_encontrado = True
                motivo_cargo = f"Nome do arquivo -> {termo}"
                break

        # ====================================================
        # ABRE PDF
        # ====================================================

        reader = PdfReader(str(pdf))

        # ====================================================
        # REGRA 1 (continuação)
        # PROCURA TERMOS NA PRIMEIRA PÁGINA
        # ====================================================

        if not cargo_encontrado and len(reader.pages) > 0:

            texto_p1 = (
                reader.pages[0].extract_text() or ""
            )

            texto_p1 = reorganizar_duas_colunas(
                texto_p1
            )

            texto_p1_normalizado = remover_acentos(
                texto_p1.lower()
            )

            for termo in TERMOS:

                termo_normalizado = remover_acentos(
                    termo.lower()
                )

                if termo_normalizado in texto_p1_normalizado:

                    cargo_encontrado = True
                    motivo_cargo = f"Página 1 -> {termo}"
                    break

        # ====================================================
        # REGRA 2
        # PROCURA "Conhecimentos Específicos"
        # EM QUALQUER PÁGINA
        # ====================================================

        if cargo_encontrado:

            for numero_pagina, pagina in enumerate(reader.pages, start=1):

                texto = pagina.extract_text() or ""

                texto = reorganizar_duas_colunas(texto)

                encontrou = re.search(
                    r"^\s*Conhecimentos Específicos\b",
                    texto,
                    re.MULTILINE
                )

                if encontrou:

                    conhecimentos_especificos = True
                    pagina_encontrada = numero_pagina
                    break

        # ====================================================
        # COPIA
        # ====================================================

        if cargo_encontrado and conhecimentos_especificos:

            destino = obter_nome_destino(
                Path(DESTINO) / pdf.name
            )

            shutil.copy2(pdf, destino)

            total_copiados += 1

            print(
                f"[COPIADO] {pdf.name}"
                f" | {motivo_cargo}"
                f" | Conhecimentos Específicos página {pagina_encontrada}"
            )

        else:

            if not cargo_encontrado:

                print(
                    f"[IGNORADO] {pdf.name}"
                    f" | Cargo não encontrado"
                )

            elif not conhecimentos_especificos:

                print(
                    f"[IGNORADO] {pdf.name}"
                    f" | Sem 'Conhecimentos Específicos'"
                )

    except Exception as e:

        print(
            f"[ERRO] {pdf.name} -> {e}"
        )

print()
print("=" * 80)
print(f"PDFs analisados : {total_pdfs}")
print(f"PDFs copiados   : {total_copiados}")
print("=" * 80)