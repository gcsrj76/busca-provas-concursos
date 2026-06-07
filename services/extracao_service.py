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
    def extrair_texto_limpo(caminho_pdf, materia, callback_interface):
        import os
        import re
        from pypdf import PdfReader
        from collections import Counter

        arquivos_brutos = [f for f in os.listdir(caminho_pdf) if f.lower().endswith(".pdf")]

        # Ordenação dos arquivos por alfanuméricos
        arquivos = sorted(
            arquivos_brutos, 
            key=lambda s: [int(texto) if texto.isdigit() else texto.lower() for texto in re.split(r'(\d+)', s)]
        )       

        total = len(arquivos)

        if total == 0:
            callback_interface("Nenhum PDF encontrado na pasta de origem.", 1.0, "Processamento vazio.\n")
            return

        # Lista de matérias permitidas fornecida
        materias_obrigatorias = {
            "Língua Portuguesa", 
            "Legislação",
            "Raciocínio Lógico", 
            "Informática", 
            "Analista de Tecnologia", 
            "Direito", 
            "Conhecimentos Específicos", 
            "Matemática", 
            "Língua Inglesa", 
            "História", 
            "Geografia"
        }

        texto_acumulado_final = ""
        arquivos_processados = 0

        for i, nome_arq in enumerate(arquivos):
            prog = (i + 1) / total
            callback_interface(f"Analisando arquivo {i+1}/{total}: {nome_arq}...", prog, f"Analisando {nome_arq}...\n")
            caminho_origem = os.path.join(caminho_pdf, nome_arq)

            try:
                texto_completo = ""
                
                # -----------------------------------------------------------------
                # ROTINA DE VERIFICAÇÃO DE REPETIÇÃO (Linha inteira idêntica)
                # -----------------------------------------------------------------
                leitor = PdfReader(caminho_origem)
                contador_linhas_globais = Counter()
                
                # Primeira passada rápida no PDF para mapear o que se repete entre as páginas
                for num_pag in range(len(leitor.pages)):
                    if num_pag < 2:  # Mantém seu critério de pular as duas primeiras páginas
                        continue
                    texto_pag = leitor.pages[num_pag].extract_text(extraction_mode="plain")
                    if texto_pag:
                        for linha in texto_pag.splitlines():
                            linha_f = linha.strip()
                            if linha_f:
                                contador_linhas_globais[linha_f] += 1
                
                # Guardamos as linhas exatas que aparecem em mais de 2 páginas (Cabeçalhos/Rodapés fixos)
                linhas_repetidas_lixo = {linha for linha, qtd in contador_linhas_globais.items() if qtd > 2}
                
                # -----------------------------------------------------------------
                # SEGUNDA PASSADA: PROCESSAMENTO E EXTRAÇÃO FILTRADA
                # -----------------------------------------------------------------
                for num_pag in range(len(leitor.pages)):
                    if num_pag < 2:
                        continue

                    texto_pag = leitor.pages[num_pag].extract_text(extraction_mode="plain")
                    if not texto_pag:
                        continue

                    linhas_com_conteudo = [l for l in texto_pag.splitlines() if l.strip()]

                    # Se a página tiver menos de 6 linhas de texto útil (como a página que só tem "Realização"), ela é descartada!
                    if len(linhas_com_conteudo) < 6:
                        continue                                                                        
                    
                    linhas_corrigidas = []
                    prefixo_atual = ""      
                    conteudo_acumulado = [] 
                    
                    for linha in texto_pag.splitlines():
                        linha_limpa = linha.strip()

                        if not linha_limpa:
                            if prefixo_atual == "(E)" and conteudo_acumulado:
                                texto_completo_bloco = " ".join(conteudo_acumulado)
                                texto_limpo_bloco = " ".join(texto_completo_bloco.split())
                                linhas_corrigidas.append(f"{prefixo_atual} {texto_limpo_bloco}".strip())
                                prefixo_atual = ""
                                conteudo_acumulado = []
                            continue                        
                       
                        # A) Filtro por Repetição Absoluta (Pega "Concurso Público...", rodapés fixos, etc.)
                        if linha_limpa in linhas_repetidas_lixo:
                            continue
                            
                        # B) Filtro Regex Dinâmico (Pega variações de "Tipo X – Cor XXXX – Página Y")
                        if re.search(r'.*Tipo.*Página.*', linha_limpa):
                            continue 
                        
                        # C) Lógica de Isolamento das Matérias do Concurso
                        if linha_limpa in materias_obrigatorias:
                            if prefixo_atual or conteudo_acumulado:
                                texto_completo_bloco = " ".join(conteudo_acumulado)
                                texto_limpo_bloco = " ".join(texto_completo_bloco.split())
                                if not prefixo_atual:
                                        linhas_corrigidas.append(texto_limpo_bloco)
                                else:
                                        linhas_corrigidas.append(f"{prefixo_atual} {texto_limpo_bloco}".strip())
                            
                            linhas_corrigidas.append(linha_limpa)
                            prefixo_atual = ""
                            conteudo_acumulado = []
                            continue

                        # D) Processamento das Questões e Alternativas estruturadas
                        se_inicio_bloco = re.match(r'^(\d+|\([A-E]\))', linha_limpa)

                        if se_inicio_bloco:
                            if prefixo_atual or conteudo_acumulado:
                                texto_completo_bloco = " ".join(conteudo_acumulado)
                                texto_limpo_bloco = " ".join(texto_completo_bloco.split())
                                
                                if not prefixo_atual:
                                        linhas_corrigidas.append(texto_limpo_bloco)
                                else:
                                        linhas_corrigidas.append(f"{prefixo_atual} {texto_limpo_bloco}".strip())
                            
                            prefixo_atual = se_inicio_bloco.group(1) 
                            resto_da_linha = linha_limpa[len(prefixo_atual):].strip()
                            conteudo_acumulado = [resto_da_linha] if resto_da_linha else []                                    
                        else:
                            conteudo_acumulado.append(linha_limpa)  

                    # Finalização da página
                    if prefixo_atual or conteudo_acumulado:
                        texto_completo_bloco = " ".join(conteudo_acumulado)
                        texto_limpo_bloco = " ".join(texto_completo_bloco.split())
                        if not prefixo_atual:
                            linhas_corrigidas.append(texto_limpo_bloco)
                        else:
                            linhas_corrigidas.append(f"{prefixo_atual} {texto_limpo_bloco}".strip())

                    texto_pag_limpo = "\n".join(linhas_corrigidas) + "\n"
                    texto_completo += texto_pag_limpo                                
                
                texto_acumulado_final += texto_completo
                arquivos_processados += 1

            except Exception as ex:
                callback_interface(None, prog, f"❌ Falha ao processar {nome_arq}: {str(ex)}\n")

        # Gravação do arquivo texto final consolidado
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

        ExtracaoService.extrair_materia(caminho_salvamento_txt, materia, callback_interface)            

    #Processo utilizando modo "layout"(mais complexo e com muitas falhas)
    #Renomeado para eventual utilização como referencia
    @staticmethod
    def _extrair_texto_limpo(caminho_pdf, materia, callback_interface):
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

        # Função auxiliar para limpar profundamente caracteres de controle ocultos (\x0c, etc.)
        def limpar_linha_profundo(txt):
            txt_limpo = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', txt)
            return txt_limpo.strip()        

        for i, nome_arq in enumerate(arquivos):
            prog = (i + 1) / total
            callback_interface(f"Analisando arquivo {i+1}/{total}: {nome_arq}...", prog, f"Analisando {nome_arq}...\n")
            caminho_origem = os.path.join(caminho_pdf, nome_arq)

            try:
                # ------------------------------------------------------------------
                # ETAPA 1: PRÉ-LEITURA DO DOCUMENTO COMPLETO PARA MAPEAMENTO DE LIXO
                # ------------------------------------------------------------------
                callback_interface(None, prog, f"🔍 Mapeando cabeçalhos e rodapés repetidos em {nome_arq}...\n")
                
                contagem_linhas_documento = {}

                maior_numero_caracteres = 0
                
                with open(caminho_origem, "rb") as f:
                    leitor = PdfReader(f)
                    for num_pag in range(len(leitor.pages)):
                        if num_pag == 0:
                            continue
                        texto_pag_bruto = leitor.pages[num_pag].extract_text(extraction_mode="layout")
                        if texto_pag_bruto:
                            for linha in texto_pag_bruto.splitlines()[1:-1]:
                                linha_limpa = limpar_linha_profundo(linha)

                                maior_numero_caracteres = max(maior_numero_caracteres, len(linha_limpa))

                                if maior_numero_caracteres>500:
                                    faz_qualquer_coisa = 1

                                # Mantemos o critério de tamanho mínimo de 10 caracteres
                                if len(linha_limpa) >= 10:
                                    contagem_linhas_documento[linha_limpa] = contagem_linhas_documento.get(linha_limpa, 0) + 1

                # Filtro para ignorar alternativas (A)..(E) de entrarem no lixo
                padrao_alternativa = re.compile(r'^\s*\([A-E]\)')

                padrao_rodape_variavel = re.compile(r'Tipo.*Pág', re.IGNORECASE)
                
                # Cria o conjunto de linhas que se repetem 3 ou mais vezes no PDF completo
                MIN_REP = 3
                linhas_lixo_documento = {
                    linha for linha, qtd in contagem_linhas_documento.items()
                    if qtd >= MIN_REP and not padrao_alternativa.match(linha)
                    or padrao_rodape_variavel.search(linha)
                }            
            
                # ------------------------------------------------------------------
                # ETAPA 2: FLUXO DE LEITURA REAL E PROCESSAMENTO POR PÁGINA
                # ------------------------------------------------------------------
                texto_completo_prova = ""
                
                with open(caminho_origem, "rb") as f:                    
                    leitor = PdfReader(f)
                    for num_pag in range(len(leitor.pages)):
                        if num_pag == 0:
                            continue

                        texto_pag = leitor.pages[num_pag].extract_text(extraction_mode="layout")
                        if texto_pag:
                            # Filtra as linhas repetidas (lixo) desta página ANTES da unificação
                            linhas_pagina_filtradas = []
                            for linha in texto_pag.splitlines()[1:-1]:
                                if limpar_linha_profundo(linha) in linhas_lixo_documento:
                                    continue # Ignora/Remove a linha repetida (cabeçalho, rodapé, etc.)
                                
                                linhas_pagina_filtradas.append(linha)
                            
                            # Reconstroi o texto da página limpo para a unificação de colunas
                            texto_pag_limpo = "\n".join(linhas_pagina_filtradas)

                            metade_pagina = maior_numero_caracteres / 2
                            
                            # Agora sim, unifica com o layout livre de interferências de cabeçalho/rodapé
                            texto_completo_prova += ExtracaoService.unificar_colunas(texto_pag_limpo, metade_pagina)

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

        ExtracaoService.extrair_materia(caminho_salvamento_txt, materia,callback_interface)            

    @staticmethod
    def unificar_colunas(texto_pagina, metade_pagina):

        #Metade da página com uma margem de segurança (-5)
        divisao_coluna = metade_pagina - 5

        coluna_esquerda = ""
        coluna_direita =  ""

        linhas = texto_pagina.splitlines()

        VALOR_MINIMO_ESPACOS = 5

        for linha in linhas:

            inicia_deslocada = bool(re.match(f'^ {{{{ {divisao_coluna},}}}}', linha))

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
    def extrair_materia(caminho_txt_consolidado, materia_inicial, callback_interface):

        """
        Lê o arquivo de texto consolidado, localiza TODOS os blocos de texto associados 
        à materia_inicial (várias provas), concatena-os em ordem e gera um arquivo texto final único.
        """
        import os
        import re

        if not os.path.exists(caminho_txt_consolidado):
            callback_interface("Arquivo consolidado não encontrado.", 1.0, f"❌ Erro: {caminho_txt_consolidado} não existe.\n")
            return

        callback_interface(f"Analisando documento em busca de blocos de '{materia_inicial}'...", 0.1, "Iniciando varredura multimapas...\n")

        # Lista de possíveis matérias finais para servir de limite/corte (Estrito Case Sensitive)
        lista_materias_possiveis = [
            "Língua Portuguesa", "Língua Portuguesa",
            "Legislação", "Legislação",
            "Raciocínio Lógico", "Raciocínio Lógico",
            "Informática", "Informática",
            "Analista de Tecnologia", "Analista de Tecnologia",
            "Direito", "Direito",
            "Conhecimentos Específicos", "Conhecimentos Específicos",
            "Matemática", "Matemática",
            "Língua Inglesa", "Língua Inglesa",
            "História", "História",
            "Geografia","Geografia"
        ]

        try:
            # 1. Carrega o conteúdo completo do TXT consolidado
            with open(caminho_txt_consolidado, "r", encoding="utf-8") as f:
                texto_completo = f.read()

            # Padrão para identificar o início da matéria (Exige linha isolada)
            termo_inicio_esc = re.escape(materia_inicial)
            padrao_inicio = fr"^\s*{termo_inicio_esc}\s*$"
            
            # Encontra todas as ocorrências de início da matéria ao longo do arquivo completo
            matches_inicio = list(re.finditer(padrao_inicio, texto_completo, re.MULTILINE))
            
            if not matches_inicio:
                callback_interface(f"Matéria '{materia_inicial}' não encontrada.", 1.0, f"⚠️ Aviso: Nenhuma ocorrência de '{materia_inicial}' foi localizada.\n")
                return

            # Constrói a Regex de corte com o limite de no máximo 1 palavra complementar
            materias_corte = [m for m in lista_materias_possiveis if m.lower() != materia_inicial.lower()]
            padrao_fim = r"^\s*(" + "|".join([re.escape(m) for m in materias_corte]) + r")(?:\s+[^\s]+)?\s*$"

            texto_acumulado_materia = ""
            total_blocos = len(matches_inicio)
            
            callback_interface(None, 0.3, f"🔍 Encontrado(s) {total_blocos} bloco(s) de '{materia_inicial}'. Isolando conteúdos...\n")

            # 2. Varre cada uma das ocorrências encontradas
            for idx, match_atual in enumerate(matches_inicio):
                ponto_inicio_conteudo = match_atual.end()
                
                # O escopo de busca vai desde o fim do título atual até o início do próximo bloco da mesma matéria (se houver)
                if idx + 1 < total_blocos:
                    ponto_limite_busca = matches_inicio[idx + 1].start()
                    sub_texto_busca = texto_completo[ponto_inicio_conteudo:ponto_limite_busca]
                else:
                    sub_texto_busca = texto_completo[ponto_inicio_conteudo:]

                # 3. Procura o marcador de término (outra matéria) dentro deste pedaço isolado
                fim_match = re.search(padrao_fim, sub_texto_busca, re.MULTILINE)
                
                if fim_match:
                    # Se achou outra matéria, corta o texto logo antes dela começar
                    bloco_isolado = sub_texto_busca[:fim_match.start()]
                else:
                    # Se não achou outra matéria (ex: fim do arquivo ou redação limpa), pega o sub_texto inteiro
                    bloco_isolado = sub_texto_busca

                # Adiciona o bloco limpo ao acumulador da matéria correspondente
                texto_acumulado_materia += bloco_isolado.strip() + "\n\n"

            # --- SANITIZAÇÃO GERAL DE QUEBRAS DE LINHA SOBRANTES ---
            texto_final_limpo = re.sub(r'(\n\s*){3,}', '\n\n', texto_acumulado_materia).strip()

            if not texto_final_limpo:
                callback_interface("Conteúdo vazio.", 1.0, f"⚠️ Nenhum conteúdo útil foi extraído dos {total_blocos} blocos.\n")
                return

            # 4. Gravação do arquivo texto final específico desta matéria
            pasta_origem = os.path.dirname(caminho_txt_consolidado)
            nome_materia_limpo = materia_inicial.replace(' ', '_').lower()
            nome_arquivo_txt = f"extracao_final_{nome_materia_limpo}.txt"
            caminho_salvamento_txt = os.path.join(pasta_origem, nome_arquivo_txt)
            
            with open(caminho_salvamento_txt, "w", encoding="utf-8") as f_txt:
                f_txt.write(texto_final_limpo)
            
            callback_interface(
                "Extração Multi-Bloco Concluída!", 
                1.0, 
                f"\n=== EXTRAÇÃO FINALIZADA ===\nConsolidados {total_blocos} bloco(s) de '{materia_inicial}' com sucesso!\n➡️ Gerado em: {caminho_salvamento_txt}\n"
            )

        except Exception as ex:
            callback_interface("Erro na extração.", 1.0, f"❌ Falha crítica ao isolar múltiplos blocos: {str(ex)}\n")

    @staticmethod
    def extrair_questoes_json(caminho_arquivo, arquivo_json_saida):
        # Lendo o arquivo original de texto
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            conteudo = f.read()

        # Dividir em linhas removendo espaços em branco extras nas extremidades
        linhas = [linha.strip() for i, linha in enumerate(conteudo.split("\n"))]

        dados_questoes = []
        total_linhas = len(linhas)
        i = 0

        while i < total_linhas:
            # 1 - Identifica o início das respostas pela linha iniciada por "(A)"
            if linhas[i].startswith("(A)"):
                idx_A = i

                # Extração temporária das alternativas (A) até (E) para a variável local
                respostas_temporarias = []
                idx_busca_alts = idx_A

                while idx_busca_alts < total_linhas:
                    linha_alt = linhas[idx_busca_alts]
                    match_alt = re.match(r"^\(([A-E])\)\s*(.*)", linha_alt)

                    if match_alt:
                        letra = match_alt.group(1)
                        texto_alternativa = match_alt.group(2).strip()

                        # Monta o objeto individual de cada alternativa
                        respostas_temporarias.append(
                            {
                                "texto": texto_alternativa,
                                "eh_correta": 0,  # Fixo como 0 conforme o layout desejado
                            }
                        )

                        # Quando localiza o término da estrutura em (E), para a busca de alternativas
                        if letra == "E":
                            break
                    idx_busca_alts += 1

                # 2 - A partir da letra "(A)" identificada (idx_A), verifica o conteúdo imediatamente anterior
                idx_busca_enunciado = idx_A - 1
                linhas_enunciado = []
                idx_numero = -1
                texto_restante_da_linha_do_numero = ""

                while idx_busca_enunciado >= 0:
                    linha_atual = linhas[idx_busca_enunciado]

                    match_linha_iniciada_por_num = re.match(r"^(\d+)\s*(.*)$", linha_atual)

                    # Localiza a linha que inicia com o número da questão (ex: "1", "10", etc.)
                    if match_linha_iniciada_por_num:
                        idx_numero = idx_busca_enunciado
                        texto_restante_da_linha_do_numero = match_linha_iniciada_por_num.group(2).strip()
                        break
                    
                    # Insere no início para preservar a ordem correta de leitura
                    if linha_atual:
                        linhas_enunciado.insert(0, linha_atual)

                    idx_busca_enunciado -= 1

                # Se a linha que disparou o início do enunciado continha texto ao lado do número,
                # esse texto é incluído no início do enunciado (sem o número).
                if texto_restante_da_linha_do_numero:
                    linhas_enunciado.insert(0, texto_restante_da_linha_do_numero)                    

                # Une as linhas do enunciado de forma limpa retirando espaçamentos nulos
                enunciado_extraido = " ".join(linhas_enunciado).strip()

                # 3 - A partir da linha identificada com o número do enunciado (idx_numero), verifica o conteúdo anterior
                texto_referencia_extraido = ""

                if idx_numero > 0:
                    idx_busca_ref = idx_numero - 1
                    linhas_ref = []

                    # Se o conteúdo imediatamente anterior for uma linha começando com "(E)", não tem texto de referência
                    if linhas[idx_busca_ref].startswith("(E)"):
                        texto_referencia_extraido = ""
                    else:
                        # Se houver conteúdo anterior, considera até encontrar o "(E)" acima ou o início do arquivo
                        while idx_busca_ref >= 0:
                            linha_ref_atual = linhas[idx_busca_ref]
                            if linha_ref_atual.startswith("(E)"):
                                break

                            if linha_ref_atual:
                                linhas_ref.insert(0, linha_ref_atual)                            

                            idx_busca_ref -= 1

                        # Une o texto de referência respeitando as quebras de linha nativas
                        texto_referencia_extraido = "\n".join(linhas_ref).strip()

                # Adiciona a questão processada à lista final de dados
                dados_questoes.append(
                    {
                        "enunciado": enunciado_extraido,
                        "texto_referencia": texto_referencia_extraido,
                        "respostas": respostas_temporarias,
                    }
                )

                # Avança o ponteiro principal para continuar a varredura após o bloco dessa questão
                i = idx_busca_alts + 1
                continue

            i += 1

        # Formatação final do layout JSON completo exigido
        layout_final = {
            "entidade": "Questao",
            "materia": "MATÉRIA IMPORTADA",
            "ementa": "EMENTA IMPORTADA",
            "dados": dados_questoes,
        }

        # Gravação do arquivo .json estruturado no destino informado pelo parâmetro
        with open(arquivo_json_saida, "w", encoding="utf-8") as f_out:
            json.dump(layout_final, f_out, ensure_ascii=False, indent=2)

    @staticmethod
    def limpa_repeticoes(texto, min_len=7, min_rep=3):
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