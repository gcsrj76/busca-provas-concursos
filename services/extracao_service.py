import os
import time
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

from database.connection import SessionLocal
from database.models import QuestaoSimuladoModel
from google import genai
from google.genai import types

import re
import json
from pypdf import PdfReader



"""
# 1. Definição da estrutura de dados esperada (Pydantic) para garantir o JSON correto
class QuestaoSchema(BaseModel):
    enunciado: str = Field(description="O enunciado completo da questão de concurso.")
    alternativa_A: str = Field(description="Texto da alternativa A.")
    alternativa_B: str = Field(description="Texto da alternativa B.")
    alternativa_C: str = Field(description="Texto da alternativa C.")
    alternativa_D: str = Field(description="Texto da alternativa D.")
    alternativa_E: str = Field(description="Texto da alternativa E.")
    alternativa_correta: Optional[str] = Field(description="Apenas a letra correspondente à alternativa correta (A, B, C, D ou E). Se não houver, nulo.")
"""

class RespostaSchema(BaseModel):
    texto: str = Field(description="O texto descritivo da alternativa.")
    eh_correta: int = Field(description="1 se for a alternativa correta, 0 caso contrário.")

class QuestaoSchema(BaseModel):
    enunciado: str = Field(description="O enunciado ou pergunta da questão.")
    texto_referencia: Optional[str] = Field(
        default="", 
        description="Texto de apoio, crônica, poesia ou aviso que antecede a questão (ex: 'Atenção: o texto a seguir refere-se... Os alunos de hoje...'). Se a questão não tiver texto base associado diretamente na página, deixe este campo vazio."
    )
    respostas: List[RespostaSchema] = Field(description="Lista contendo exatamente as alternativas da questão (Geralmente de A a E).")

class EstruturaFinalSchema(BaseModel):
    # Forçamos o tipo Literal para que o Gemini não invente dados baseados no cabeçalho do PDF
    entidade: Literal["Questao"] = "Questao"
    materia: Literal["MATÉRIA IMPORTADA"] = "MATÉRIA IMPORTADA"
    ementa: Literal["MENTA IMPORTADA"] = "EMENTA IMPORTADA"
    dados: List[QuestaoSchema]

class ListaQuestoesSchema(BaseModel):
    questoes: List[QuestaoSchema]


# 2. Classe de Serviço Unificada
class ExtracaoService:
    def __init__(self):
        """Inicializa o cliente do Gemini se a biblioteca e a chave estiverem disponíveis."""

    @staticmethod
    def extrair_texto_materia(caminho_pdf, callback_interface):
        """
        Varre os PDFs, identifica o bloco de texto entre a materia_inicial e a próxima matéria
        da lista de possíveis matérias da FGV, concatena tudo, sanitiza o excesso de linhas
        em branco consecutivas e gera um arquivo texto final limpo (removendo a marcação inicial).
        """
        import os
        import re
        from pypdf import PdfReader

        arquivos_brutos = [f for f in os.listdir(caminho_pdf) if f.lower().endswith(".pdf")]

        # Ordenação dos arquivos por alfanuméricos(para facilitar o entendimento/leitura do processo)
        arquivos = sorted(
            arquivos_brutos, 
            key=lambda s: [int(texto) if texto.isdigit() else texto.lower() for texto in re.split(r'(\d+)', s)]
        )       

        total = len(arquivos)#"""

        if total == 0:
            callback_interface("Nenhum PDF encontrado na pasta de origem.", 1.0, "Processamento vazio.\n")
            return

        # Texto acumulador que conterá o resultado de todos os arquivos processados
        texto_acumulado_final = ""
        arquivos_processados = 0

        for i, nome_arq in enumerate(arquivos):
            prog = (i + 1) / total
            callback_interface(f"Analisando arquivo {i+1}/{total}: {nome_arq}...", prog, f"Analisando {nome_arq}...\n")
            caminho_origem = os.path.join(caminho_pdf, nome_arq)
            
            texto_completo_prova = ""
            try:
                with open(caminho_origem, "rb") as f:                    
                    leitor = PdfReader(f)
                    for num_pag in range(len(leitor.pages)):
                        # Mantendo o modo layout para evitar misturar textos horizontais de duas colunas
                        if num_pag == 0:
                            continue

                        texto_pag = leitor.pages[num_pag].extract_text(extraction_mode="layout")
                        if texto_pag:
                            texto_completo_prova += ExtracaoService.unificar_colunas(texto_pag)

                # Remove repetições na prova (cabeçalho, rodapé, ...)
                texto_completo_prova = ExtracaoService.limpa_repeticoes(texto_completo_prova)
                
                texto_acumulado_final += texto_completo_prova
               
                arquivos_processados += 1

            except Exception as ex:
                callback_interface(None, prog, f"❌ Falha ao processar {nome_arq}: {str(ex)}\n")

        # Remove linhas em branco (3 ou mais)
        texto_acumulado_final = re.sub(r'(\n\s*){3,}', '\n\n', texto_acumulado_final)


        # 4. Gravação do arquivo texto final com todo o conteúdo concatenado e revisado
        if arquivos_processados > 0:
            try:
                nome_arquivo_txt = f"extracao_acumulada_completo.txt"
                caminho_salvamento_txt = os.path.join(caminho_pdf, nome_arquivo_txt)
              
                with open(caminho_salvamento_txt, "w", encoding="utf-8") as f_txt:
                    f_txt.write(texto_acumulado_final.strip())
                
                callback_interface(
                    "Extração Concluída!", 
                    1.0, 
                    f"\n=== PROCESSO FINALIZADO ===\nTexto gerado e concatenado de {arquivos_processados} arquivo(s) em:\n➡️ {caminho_salvamento_txt}\n"
                )
            except Exception as e:
                callback_interface("Erro ao salvar arquivo txt.", 1.0, f"❌ Não foi possível gerar o arquivo texto consolidado: {e}\n")
        else:
            callback_interface("Processamento Concluído sem resultados.", 1.0, "⚠️ Nenhuma matéria correspondente foi localizada para extração.\n")

    @staticmethod
    def unificar_colunas(texto_pagina):

        coluna_esquerda = ""
        coluna_direita =  ""

        linhas = texto_pagina.splitlines()

        VALOR_MINIMO_ESPACOS = 5

        for linha in linhas:

            inicia_deslocada = bool(re.match(r'^ {30,}', linha))

            # Linha limpa nas pontas para a análise de intervalos internos
            linha_limpa = linha.strip()

            # Encontra todos os blocos de espaços internos (mínimo de X espaços)
            # O padrão r' {5,}' captura sequências de 5 ou mais espaços
            intervalos_encontrados = re.findall(r' {5,}', linha_limpa)

            # Se encontrou algum intervalo válido dentro da linha limpa
            if intervalos_encontrados:
                # Determina dinamicamente qual é o maior intervalo daquela linha específica
                maior_intervalo = max(intervalos_encontrados, key=len)    

                partes = re.split(re.escape(maior_intervalo), linha_limpa, maxsplit=1)                        

                if len(partes) == 2:
                    coluna_esquerda += partes[0].rstrip() + "\n"
                    coluna_direita += partes[1].lstrip() + "\n"
                else:
                    # segurança
                    if inicia_deslocada:
                        coluna_direita += linha_limpa + "\n"
                    else:
                        coluna_esquerda += linha_limpa + "\n"

            else:

                if inicia_deslocada:
                    coluna_direita += linha_limpa + "\n"
                else:
                    coluna_esquerda += linha_limpa + "\n"

        return coluna_esquerda + "\n" + coluna_direita

    @staticmethod
    def extrair_questoes_json(caminho_txt, caminho_json_saida):
        import os
        import re
        import json

        if not os.path.exists(caminho_txt):
            print("Arquivo de origem não encontrado.")
            return

        with open(caminho_txt, "r", encoding="utf-8") as f:
            conteudo = f.read()

        lista_dados_questoes = []

        # 1. Separa o arquivo por blocos de fontes/páginas para processamento estruturado
        blocos_fontes = conteudo.split("================================================================================")
        
        for bloco_fonte in blocos_fontes:
            if not bloco_fonte.strip() or "FONTE:" in bloco_fonte:
                continue

            # --- LINHA POR LINHA: SEPARAÇÃO REAL DE COLUNAS VIRTUAIS ---
            linhas = bloco_fonte.split("\n")
            linhas_coluna_esquerda = []
            linhas_coluna_direita = []

            for linha in linhas:
                # Usa o método existente no seu ExtracaoService para quebrar a linha física em duas partes
                #esq, direi = ExtracaoService.separar_colunas_se_houver(linha)
                
                # Limpeza imediata de ruídos estruturais do PDF de forma isolada nas colunas
                for termo_ruido in ["", "FGV Projetos", "Tipo 1", "Tipo 2", "Tipo 3", "Tipo 4", "Tipo Branca", "Tipo Verde", "Tipo Amarela", "Tipo Azul"]:
                    if termo_ruido.lower() in esq.lower():
                        esq = ""
                    if direi and termo_ruido.lower() in direi.lower():
                        direi = ""

                if esq.strip():
                    linhas_coluna_esquerda.append(esq.rstrip())
                if direi and direi.strip():
                    linhas_coluna_direita.append(direi.rstrip())

            # Reconstrói o texto do bloco: Garante que TODA a coluna da esquerda venha ANTES da coluna da direita
            texto_linearizado = "\n".join(linhas_coluna_esquerda) + "\n" + "\n".join(linhas_coluna_direita)

            # 2. Agora que o texto está linearizado, os números das questões estão REALMENTE isolados em suas próprias linhas
            padrao_divisao = r"\n\s*([1-9][0-9]?)\s*\n"
            partes = re.split(padrao_divisao, texto_linearizado)
            
            if len(partes) < 2:
                continue

            # O fragmento inicial que antecede a primeira questão da página é o Texto de Referência padrão
            texto_contexto_atual = partes[0].strip()
            # Remove linhas puramente numéricas que possam ter sobrado no topo
            texto_contexto_atual = "\n".join([l for l in texto_contexto_atual.split("\n") if not l.strip().isdigit()])

            # Percorre os fragmentos de 2 em 2 (Índice Ímpar = Número da Questão, Índice Par = Conteúdo da Questão)
            for idx in range(1, len(partes), 2):
                num_questao = partes[idx].strip()
                corpo_bloco = partes[idx+1] if idx+1 < len(partes) else ""
                
                if not corpo_bloco.strip():
                    continue

                # 3. Captura e isola as alternativas (A) até (E) de forma sequencial dentro do bloco limpo
                padrao_alternativas = r"(\([A-E]\))"
                fragmentos_alternativas = re.split(padrao_alternativas, corpo_bloco)
                
                # REGRA: O que vem antes da alternativa (A) é estritamente o Enunciado
                enunciado_cru = fragmentos_alternativas[0].strip()
                
                # Remove o número da questão se ele tiver persistido grudado no início do enunciado
                enunciado_limpo = re.sub(rf"^{num_questao}\s*", "", enunciado_cru).strip()
                enunciado_limpo = re.sub(r'\s+', ' ', enunciado_limpo).strip()
                
                lista_respostas = []
                
                # REGRA: Processa as alternativas de (A) a (E) descartando os marcadores textuais solicitados
                for j in range(1, len(fragmentos_alternativas), 2):
                    letra_marcador = fragmentos_alternativas[j].strip()
                    texto_alt = fragmentos_alternativas[j+1] if j+1 < len(fragmentos_alternativas) else ""
                    
                    # Evita vazamentos truncando caso detecte o início de outra alternativa ou bloco
                    texto_alt = re.split(r"\s*\([A-E]\)", texto_alt)[0]
                    texto_alt = re.split(r"\n\s*[1-9][0-9]?\s*\n", texto_alt)[0]
                    
                    # --- A TRAVA DE SEGURANÇA MÁXIMA NA ALTERNATIVA (E) ---
                    if letra_marcador == "(E)":
                        # Como o texto está linearizado, a alternativa (E) termina na sua própria quebra física.
                        # Damos o split em '\n' e coletamos apenas a primeira linha legítima.
                        linhas_alt_e = texto_alt.split("\n")
                        texto_alt = linhas_alt_e[0] if len(linhas_alt_e) > 0 else ""

                    # Limpa espaços excessivos e consolida o texto em uma linha limpa para o JSON
                    texto_alt = re.sub(r'\s+', ' ', texto_alt).strip()
                    
                    if texto_alt:
                        lista_respostas.append({
                            "texto": texto_alt,  # A letra da alternativa ((A), (B)...) foi EXCLUÍDA aqui
                            "eh_correta": 0
                        })

                # REGRA: Define o Texto de Referência com base no contexto que antecedeu o enunciado
                texto_referencia_final = ""
                # Se o enunciado fizer menção expressa a texto ou se o contexto acumulado for um texto real longo
                if "texto" in enunciado_limpo.lower() or "conforme o autor" in enunciado_limpo.lower() or "no fragmento" in enunciado_limpo.lower():
                    texto_referencia_final = texto_contexto_atual
                else:
                    # Só associa o texto de apoio se ele tiver tamanho relevante (evita associar fragmentos órfãos)
                    texto_referencia_final = texto_contexto_atual if len(texto_contexto_atual) > 60 else ""

                # Sanitização final do texto de referência para o layout JSON
                if texto_referencia_final:
                    texto_referencia_final = "\n".join([l for l in texto_referencia_final.split("\n") if not l.strip().isdigit()])
                    texto_referencia_final = re.sub(r'\s+', ' ', texto_referencia_final).strip()

                # Ignora quebras falsas detectadas pelo parser
                if not enunciado_limpo or len(lista_respostas) < 2:
                    continue

                # Monta os dados da questão com a remoção total dos marcadores
                questao_dados = {
                    "enunciado": enunciado_limpo,  # O número da questão foi EXCLUÍDO aqui
                    "texto_referencia": texto_referencia_final if texto_referencia_final else None,
                    "respostas": lista_respostas
                }
                
                lista_dados_questoes.append(questao_dados)

        # 4. Estruturação do objeto JSON final de acordo com o padrão exigido
        json_final_estruturado = {
            "entidade": "Questao",
            "materia": "MATERIA IMPORTAÇÃO",
            "ementa": "EMENTA IMPORTAÇÃO",
            "dados": lista_dados_questoes
        }

        # Escrita física do JSON no disco
        with open(caminho_json_saida, "w", encoding="utf-8") as f_json:
            json.dump(json_final_estruturado, f_json, ensure_ascii=False, indent=4)
            
        print(f"Sucesso! {len(lista_dados_questoes)} questões estruturadas linha por linha e salvas em: {caminho_json_saida}")

    @staticmethod
    def limpa_repeticoes(texto, min_len=10, min_rep=3):
        """
        Garante que apenas LINHAS INTEIRAS repetidas (como cabeçalhos e rodapés)
        sejam removidas, protegendo a integridade das palavras e textos do documento.
        """
        if not texto:
            return ""

        linhas = texto.split("\n")
        contagem_linhas = {}
        
        # Conta apenas linhas completas que tenham relevância de tamanho
        for linha in linhas:
            linha_limpa = linha.strip()
            if len(linha_limpa) >= min_len:
                contagem_linhas[linha_limpa] = contagem_linhas.get(linha_limpa, 0) + 1

        # Identifica quais linhas limpas são lixo repetitivo (aparecem >= 4 vezes)

        # Padrão para identificar alternativas como (A), (B), (C), (D), (E)
        padrao_alternativa = re.compile(r'^\s*\([A-E]\)')

        #linhas_lixo = {linha for linha, qtd in contagem_linhas.items() if qtd >= min_rep}
        linhas_lixo = {
            linha for linha, qtd in contagem_linhas.items() 
            if qtd >= min_rep and not padrao_alternativa.match(linha.strip())
        }        

        if not linhas_lixo:
            return texto

        # 3. Reconstrói o texto filtrando e ignorando as linhas que batem com o lixo
        linhas_finais = []
        for linha in linhas:
            if linha.strip() in linhas_lixo:
                continue  # Remove a linha repetitiva inteira
            linhas_finais.append(linha)

        return "\n".join(linhas_finais)            