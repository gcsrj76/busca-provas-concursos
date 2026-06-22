import json
from pathlib import Path


PASTA_JSONS = r"/home/palinux/Downloads/Exportação APP"
PASTA_IMAGENS = r"/home/palinux/Downloads/Exportação APP"


def obter_imagens_referenciadas():

    imagens_referenciadas = set()

    # Apenas JSONs da pasta informada
    for arquivo_json in Path(PASTA_JSONS).glob("*.json"):

        try:

            with open(
                arquivo_json,
                "r",
                encoding="utf-8"
            ) as f:

                dados = json.load(f)

            for questao in dados.get("dados", []):

                imagem = questao.get("imagem")

                if imagem is None:
                    continue

                imagem = str(imagem).strip()

                if imagem == "":
                    continue

                imagens_referenciadas.add(
                    Path(imagem).name
                )

        except Exception as e:

            print(
                f"[ERRO JSON] {arquivo_json}: {e}"
            )

    return imagens_referenciadas


def remover_imagens_orfas():

    imagens_referenciadas = (
        obter_imagens_referenciadas()
    )

    total_imagens = 0
    total_removidas = 0

    extensoes = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".webp"
    }

    # Apenas imagens da pasta informada
    for arquivo in Path(PASTA_IMAGENS).glob("*"):

        if not arquivo.is_file():
            continue

        if arquivo.suffix.lower() not in extensoes:
            continue

        total_imagens += 1

        if arquivo.name not in imagens_referenciadas:

            try:

                arquivo.unlink()

                total_removidas += 1

                print(
                    f"[REMOVIDA] {arquivo.name}"
                )

            except Exception as e:

                print(
                    f"[ERRO] {arquivo}: {e}"
                )

    print()
    print("=" * 80)
    print(f"Imagens encontradas : {total_imagens}")
    print(f"Imagens removidas   : {total_removidas}")
    print(f"Imagens mantidas    : {total_imagens - total_removidas}")
    print("=" * 80)


if __name__ == "__main__":
    remover_imagens_orfas()