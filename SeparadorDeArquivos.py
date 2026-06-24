from pathlib import Path
from pypdf import PdfReader
import shutil
import re

# Pasta raiz onde as subpastas serão criadas
ORIGEM = "/home/palinux/Área de trabalho/Concursos - 2/PDFs - 1 a 7/Prova"
DESTINO_RAIZ = Path("/home/palinux/Área de trabalho/Concursos - 2/Limpando")

# Definição das subpastas
PASTA_NOME = DESTINO_RAIZ / "Conhecimentos Gerais"
PASTA_CONTEUDO = DESTINO_RAIZ / "Tecnologia da Informação"

# ====================================================
# TERMOS DE BUSCA SEPARADOS POR PROPÓSITO
# ====================================================

# Termos da REGRA ANTERIOR 1 (Exatos, procurados no Arquivo ou na Página 1)
TERMOS_ARQUIVO_RAW = ["ti", "tecnologia", "sistema", "sistemas", "informatica", "informação", "analista", "análise", "computação"]
TERMOS_ARQUIVO = [re.compile(rf'\b{termo}\b', re.IGNORECASE) for termo in TERMOS_ARQUIVO_RAW]

# Termos da REGRA ANTERIOR 2 (Rígidos, início de linha, buscados da Página 2 em diante)
TERMOS_CONTEUDO = {
    "Tecnologia Informação": re.compile(r'^\s*\bTecnologia(?:\s+(?:da|de|em))?\s+Informação\b', re.IGNORECASE | re.MULTILINE),
    "Analista Tecnologia": re.compile(r'^\s*\bAnalista(?:\s+(?:da|de|em))?\s+Tecnologia\b', re.IGNORECASE | re.MULTILINE),
    "Analista Sistema": re.compile(r'^\s*\bAnalista(?:\s+(?:da|de|em))?\s+Sistema\b', re.IGNORECASE | re.MULTILINE),  
    "Ciência de Dados": re.compile(r'^\s*\bCiência\s+de\s+Dados\b', re.IGNORECASE | re.MULTILINE),  
    "Banco de Dados": re.compile(r'^\s*\bBanco\s+de\s+Dados\b', re.IGNORECASE | re.MULTILINE)      
}

def obter_nome_destino(destino):
    if not destino.exists():
        return destino
    contador = 1
    while True:
        novo = destino.with_name(f"{destino.stem}_{contador}{destino.suffix}")
        if not novo.exists():
            return novo
        contador += 1

# Garante a criação das subpastas
PASTA_NOME.mkdir(parents=True, exist_ok=True)
PASTA_CONTEUDO.mkdir(parents=True, exist_ok=True)

total_pdfs = 0
total_copiados = 0

for pdf in Path(ORIGEM).rglob("*.pdf"):
    total_pdfs += 1
    
    # Flags de controle do fluxo
    regra_conteudo_atendida = False
    regra_flexivel_atendida = False
    
    motivo_copia = ""
    subpasta_destino = None

    try:
        reader = PdfReader(str(pdf))
        total_paginas = len(reader.pages)

        # ====================================================
        # [NOVA REGRA 1] - ANTERIOR REGRA 2: BUSCA POR CONTEÚDO (PAG 2 DIANTE)
        # ====================================================
        if total_paginas > 1:
            # Varre o arquivo a partir da página 2 (índice 1 no Python)
            for numero_pagina, pagina in enumerate(reader.pages[1:], start=2):
                texto_pag = pagina.extract_text(extraction_mode="plain") or ""

                for nome_termo, padrao in TERMOS_CONTEUDO.items():
                    # 'padrao' possui ^\s* e re.MULTILINE, validando início de linha
                    if padrao.search(texto_pag):
                        regra_conteudo_atendida = True
                        motivo_copia = f"Regra de Conteúdo Atendida | Termo '{nome_termo}' no início da linha na página {numero_pagina}"
                        subpasta_destino = PASTA_CONTEUDO  # Vai para a pasta Por Conteúdo
                        break
                
                if regra_conteudo_atendida:
                    break

        # ====================================================
        # [NOVA REGRA 2] - ANTERIOR REGRA 1: SÓ EXECUTA SE A ANTERIOR FALHOU
        # ====================================================
        if not regra_conteudo_atendida:
            cargo_flexivel_encontrado = False
            origem_cargo_flexivel = ""

            # Passo A: Tenta pelo Nome do Arquivo (Exige 2 ou mais termos)
            nome_arquivo = pdf.name
            termos_no_arquivo = [p.pattern.replace(r'\b', '') for p in TERMOS_ARQUIVO if p.search(nome_arquivo)]
            
            if len(termos_no_arquivo) >= 2:
                cargo_flexivel_encontrado = True
                origem_cargo_flexivel = f"Nome do arquivo contendo {termos_no_arquivo}"
                subpasta_destino = PASTA_NOME
            
            # Passo B: Se falhou no nome, tenta na Página 1 (Mesma regra de 2 ou mais termos)
            elif total_paginas > 0:
                texto_p1 = reader.pages[0].extract_text(extraction_mode="plain") or ""
                termos_na_p1 = [p.pattern.replace(r'\b', '') for p in TERMOS_ARQUIVO if p.search(texto_p1)]
                
                if len(termos_na_p1) >= 2:
                    cargo_flexivel_encontrado = True
                    origem_cargo_flexivel = f"Texto da Página 1 contendo {termos_na_p1}"
                    subpasta_destino = PASTA_CONTEUDO

            # Passo C: Se o cargo flexível foi achado, valida se existe "Conhecimentos Específicos"
            if cargo_flexivel_encontrado:
                for numero_pagina, pagina in enumerate(reader.pages, start=1):
                    texto_pag = pagina.extract_text(extraction_mode="plain") or ""

                    # Busca por "Conhecimentos Específicos" obrigatoriamente no início da linha
                    if re.search(r"^\s*Conhecimentos Específicos\b", texto_pag, re.MULTILINE | re.IGNORECASE):
                        regra_flexivel_atendida = True
                        motivo_copia = f"Regra Flexível Atendida ({origem_cargo_flexivel}) | Conhecimentos Específicos na página {numero_pagina}"
                        break

        # ====================================================
        # [FASE DE SEPARAÇÃO] - COPIA BASEADO NA REGRA QUE BATEU
        # ====================================================
        if regra_conteudo_atendida or regra_flexivel_atendida:
            destino = obter_nome_destino(subpasta_destino / pdf.name)
            shutil.copy2(pdf, destino)
            total_copiados += 1
            print(f"[COPIADO] {pdf.name} -> [{subpasta_destino.name}] | {motivo_copia}")
        else:
            print(f"[IGNORADO] {pdf.name} | Não atendeu a nenhuma das regras")

    except Exception as e:
        print(f"[ERRO] {pdf.name} -> {e}")

print()
print("=" * 80)
print(f"PDFs analisados : {total_pdfs}")
print(f"PDFs copiados   : {total_copiados}")
print("=" * 80)