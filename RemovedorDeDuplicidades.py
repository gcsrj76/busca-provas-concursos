import json
import re
import unicodedata
from pathlib import Path


PASTA_ORIGEM = r"/home/palinux/Área de trabalho/Concursos/PDFs FGV - Páginas 1 a 5/Provas por Matérias/JSONs/raciocínio_lógico"
PASTA_DESTINO = r"/home/palinux/Área de trabalho/Concursos/PDFs FGV - Páginas 1 a 5/Prontos para Importação/Raciocínio Lógico/Json"


def normalizar_texto(texto):
    """
    Normaliza texto para comparação.
    """

    if texto is None:
        return ""

    texto = unicodedata.normalize("NFKD", str(texto))

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = texto.lower()

    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def gerar_chave_questao(questao):
    """
    Considera iguais apenas:

    - enunciado
    - respostas[].texto

    Todo o restante é ignorado.
    """

    enunciado = normalizar_texto(
        questao.get("enunciado", "")
    )

    respostas = []

    for resposta in questao.get("respostas", []):

        respostas.append(
            normalizar_texto(
                resposta.get("texto", "")
            )
        )

    return (
        enunciado,
        tuple(respostas)
    )


def possui_imagem(questao):
    """
    Retorna True se o campo imagem estiver preenchido.
    """

    imagem = questao.get("imagem")

    if imagem is None:
        return False

    if str(imagem).strip() == "":
        return False

    return True


def remover_duplicadas_json(
    arquivo_entrada,
    arquivo_saida
):

    with open(
        arquivo_entrada,
        "r",
        encoding="utf-8"
    ) as f:

        dados = json.load(f)

    questoes = dados.get("dados", [])

    questoes_por_chave = {}

    removidas = 0

    for questao in questoes:

        chave = gerar_chave_questao(
            questao
        )

        if chave not in questoes_por_chave:

            questoes_por_chave[chave] = questao
            continue

        questao_existente = questoes_por_chave[chave]

        existente_tem_imagem = possui_imagem(
            questao_existente
        )

        nova_tem_imagem = possui_imagem(
            questao
        )

        # Regra:
        # prevalece a que possui imagem

        if (
            not existente_tem_imagem
            and nova_tem_imagem
        ):

            questoes_por_chave[chave] = questao

        removidas += 1

    questoes_unicas = list(
        questoes_por_chave.values()
    )

    dados["dados"] = questoes_unicas

    arquivo_saida.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        arquivo_saida,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            dados,
            f,
            ensure_ascii=False,
            indent=2
        )

    return (
        len(questoes),
        removidas,
        len(questoes_unicas)
    )



def processar_pasta():

    pasta_origem = Path(PASTA_ORIGEM)
    pasta_destino = Path(PASTA_DESTINO)

    total_arquivos = 0
    total_questoes = 0
    total_removidas = 0

    for arquivo in pasta_origem.rglob("*"):

        if not arquivo.is_file():
            continue

        if arquivo.suffix.lower() != ".json":
            continue

        total_arquivos += 1

        caminho_relativo = arquivo.relative_to(
            pasta_origem
        )

        arquivo_saida = (
            pasta_destino /
            caminho_relativo
        )

        try:

            qtd_original, qtd_removidas, qtd_final = (
                remover_duplicadas_json(
                    arquivo,
                    arquivo_saida
                )
            )

            total_questoes += qtd_original
            total_removidas += qtd_removidas

            print(
                f"[OK] {caminho_relativo}"
                f" | Questões: {qtd_original}"
                f" | Removidas: {qtd_removidas}"
                f" | Final: {qtd_final}"
            )

        except Exception as e:

            print(
                f"[ERRO] {caminho_relativo}"
                f" -> {e}"
            )

    print()
    print("=" * 80)
    print(f"Arquivos processados : {total_arquivos}")
    print(f"Questões analisadas  : {total_questoes}")
    print(f"Duplicadas removidas : {total_removidas}")
    print("=" * 80)


if __name__ == "__main__":
    processar_pasta()