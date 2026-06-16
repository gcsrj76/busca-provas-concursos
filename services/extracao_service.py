import os
import time
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from database.connection import SessionLocal
from google import genai
from google.genai import types
import re
import json
from pypdf import PdfReader
from collections import Counter
import unicodedata
import uuid
from PIL import Image
import io
import fitz


class RespostaSchema(BaseModel):
    texto: str = Field(description="O texto descritivo da alternativa.")
    eh_correta: int = Field(description="1 se for a alternativa correta, 0 caso contrário.")

class QuestaoSchema(BaseModel):
    enunciado: str = Field(description="O enunciado ou pergunta da questão.")
    texto_referencia: Optional[str] = Field(        
        default="", 
        description="Texto de apoio, crônica, poesia ou aviso que antecede a questão..."
    )
    imagem: Optional[str] = Field(
        default="", 
        description="Nome do arquivo de imagem extraído associado ao enunciado (com extensão), ou vazio se não houver."
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

    @staticmethod
    def extrair_questoes_json(pasta_prova, pasta_gabarito, materia, tamanho_bloco, callback_interface):        
        """
        Orquestra o pipeline completo:
        1. Varre e ordena alfanumericamente os PDFs da pasta.
        2. Divide a lista de arquivos em blocos/lotes com base em 'tamanho_bloco'.
        3. Para cada bloco, executa a extração limpa e gera o log de depuração txt.
        4. Filtra a matéria selecionada do conteúdo concatenado do bloco.
        5. Estrutura os dados encontrados no formato padrão JSON.
        """

        nome_subpasta_materia = materia.replace(' ', '_').lower()

        # Local para armazenar os arquivos JSONs
        diretorio_saida_final = os.path.join(pasta_prova, "JSONs", nome_subpasta_materia)
        os.makedirs(diretorio_saida_final, exist_ok=True)

        # Local para armazenar as imagens extraídas das questões
        pasta_imagens = os.path.join(pasta_prova, "Imagens", nome_subpasta_materia)
        os.makedirs(pasta_imagens, exist_ok=True)        

        pasta_provas = os.path.join(pasta_prova, materia)

        if not os.path.exists(pasta_provas) or not os.path.exists(pasta_gabarito):
            callback_interface("Pastas 'Prova' e/ou 'Gabarito' não encontradas no local informado.", 1.0, "Processamento abortado: pasta não localizada.\n")
            return 

        # Captura e ordenação alfanumérica idêntica à original
        arquivos_brutos = [f for f in os.listdir(pasta_provas) if f.lower().endswith(".pdf")]
        arquivos_ordenados = sorted(
            arquivos_brutos, 
            key=lambda s: [int(texto) if texto.isdigit() else texto.lower() for texto in re.split(r'(\d+)', s)]
        )

        total_arquivos = len(arquivos_ordenados)
        if total_arquivos == 0:
            callback_interface("Nenhum PDF encontrado.", 1.0, "Processamento abortado: pasta vazia.\n")
            return

        # Divisão dos arquivos em grupos/lotes de tamanho fixo
        lotes_de_arquivos = [arquivos_ordenados[i:i + tamanho_bloco] for i in range(0, total_arquivos, tamanho_bloco)]
        total_lotes = len(lotes_de_arquivos)

        callback_interface(
            f"Preparando {total_lotes} bloco(s)", 0.0, 
            f"📦 Total de arquivos: {total_arquivos} | Divididos em {total_lotes} bloco(s) de tamanho máximo {tamanho_bloco}.\n\n"
        )

        for idx_lote, lote_atual in enumerate(lotes_de_arquivos):
            numero_bloco_incremental = idx_lote + 1
            progresso_atual = numero_bloco_incremental / total_lotes
            
            callback_interface(
                f"Processando bloco {numero_bloco_incremental}/{total_lotes}", 
                progresso_atual, 
                f"🚀 Iniciando Bloco {numero_bloco_incremental} -> Arquivos: {lote_atual}\n"
            )

            # --- PASSO 1: EXTRAÇÃO DO TEXTO LIMPO INTEGRADO (DO LOTE ATUAL) ---
            texto_limpo_lote = ExtracaoService._executar_texto_limpo_lote(pasta_provas, pasta_imagens, lote_atual, callback_interface)

            # Gravação do arquivo de depuração do Bloco de Texto Limpo (Controle/Depuração requisitado)
            nome_arq_depuracao_txt = f"depuracao_bloco_{numero_bloco_incremental:04d}.txt"
            caminho_depuracao_txt = os.path.join(diretorio_saida_final, nome_arq_depuracao_txt)
            
            with open(caminho_depuracao_txt, "w", encoding="utf-8") as f_depura:
                # 1. Cabeçalho inicial
                f_depura.write("=== ARQUIVOS TRATADOS NESTE INTERVALO ===\n")
                
                # 2. Varre o lote atual e escreve cada nome de arquivo em uma linha própria
                for nome_arquivo in lote_atual:
                    f_depura.write(f"- {nome_arquivo}\n")
                
                # 3. Linha divisória para separar o cabeçalho do conteúdo útil
                f_depura.write("=========================================\n\n")
                
                # 4. Escreve o texto limpo acumulado
                f_depura.write(texto_limpo_lote.strip())

            # --- PASSO 2: FILTRAGEM DA MATÉRIA DO LOTE ---
            texto_filtrado_materia = ExtracaoService._executar_filtragem_materia(texto_limpo_lote, materia, callback_interface)

            if not texto_filtrado_materia.strip():
                callback_interface(
                    None, progresso_atual, 
                    f"⚠️ Bloco {numero_bloco_incremental:04d}: Nenhum conteúdo de '{materia}' encontrado neste lote.\n"
                )
                continue

            # --- PASSO 3: MONTAGEM DO GABARITO PARA O JSON ---
            gabaritos = ExtracaoService._obter_gabaritos(lote_atual, pasta_provas, pasta_gabarito)

            # --- PASSO 4: ESTRUTURAÇÃO DO TEXTO DA MATÉRIA PARA JSON ---
            dados_questoes_estruturadas = ExtracaoService._converter_texto_para_estrutura_dados(texto_filtrado_materia, gabaritos)

            # Formatação do nome de saída exigido: <Matéria><Número incremental com 4 dígitos>.json
            nome_arquivo_json_final = f"{nome_subpasta_materia}_{numero_bloco_incremental:04d}.json"
            caminho_salvamento_json = os.path.join(diretorio_saida_final, nome_arquivo_json_final)

            layout_final = {
                "entidade": "Questao",
                "materia": materia.upper(),
                "ementa": f"BLOCO{numero_bloco_incremental:03d}",
                "dados": dados_questoes_estruturadas,
            }

            with open(caminho_salvamento_json, "w", encoding="utf-8") as f_out:
                json.dump(layout_final, f_out, ensure_ascii=False, indent=2)

            callback_interface(
                None, progresso_atual, 
                f"✅ Bloco {numero_bloco_incremental:04d} salvo com sucesso em:\n➡️ {caminho_salvamento_json}\n\n"
            )

        callback_interface("Processamento Concluído com Sucesso!", 1.0, "=== PIPELINE DE SUCESSO ABSOLUTO FINALIZADO ===\n")

    @staticmethod
    def _executar_texto_limpo_lote(pasta_pdf, pasta_imagens, lote_arquivos, callback_interface):
        """
        Lógica interna nativa que extrai o texto de um conjunto específico de arquivos (Lote),
        preservando os tratamentos contra cabeçalhos, rodapés e regras de recortes de linhas.
        Atualizada para reconhecer títulos dinâmicos/flexíveis de matérias e injetar tags de imagens.
        """
        # Garante que a pasta de destino das imagens exista em disco
        if pasta_imagens:
            os.makedirs(pasta_imagens, exist_ok=True)

        # Usamos os mesmos padrões da filtragem para detecção de quebra de escopo
        regras_materias = {
            "Língua Portuguesa": re.compile(r'\bLíngua\s+Portuguesa\b'),
            "Informática": re.compile(r'\bInformática\b'),
            "Analista de Tecnologia": re.compile(r'\bAnalista\s+de\s+Tecnologia\b'),
            "Conhecimentos Específicos": re.compile(r'\bConhecimentos\s+Específicos\b'),
            "Matemática": re.compile(r'\bMatemática\b'),
            "Língua Inglesa": re.compile(r'\bLíngua\s+Inglesa\b'),
            "História": re.compile(r'\bHistória\b'),
            "Geografia": re.compile(r'\bGeografia\b'),
            "Direito": re.compile(r'\bDireito\b(?:\s+[A-ZÀ-Úa-zà-ú]+)*'),
            "Raciocínio Lógico": re.compile(r'\bRaciocínio\s+Lógico\b(?:[-\s]*[A-ZÀ-Úa-zà-ú]+)*'),
            "Legislação": re.compile(r'\bLegislação\b(?:\s+[A-ZÀ-Úa-zà-ú]+)*')
        }
        
        texto_acumulado_lote = ""

        for nome_arq in lote_arquivos:
            caminho_origem = os.path.join(pasta_pdf, nome_arq)
            try:
                texto_completo_arquivo = ""
                leitor = PdfReader(caminho_origem)
                contador_linhas_globais = Counter()
                
                # Primeira passada rápida no PDF para mapear o que se repete entre as páginas
                for num_pag in range(len(leitor.pages)):
                    if num_pag < 2:
                        continue

                    texto_pag = leitor.pages[num_pag].extract_text(extraction_mode="plain")
                    if texto_pag:
                        for linha in texto_pag.splitlines():
                            linha_f = linha.strip()
                            
                            # Mantém a sua trava inteligente: alternativas nunca viram lixo
                            if linha_f and not re.match(r'^\([A-E]\)', linha_f):
                                contador_linhas_globais[linha_f] += 1
                
                linhas_repetidas_lixo = {linha for linha, qtd in contador_linhas_globais.items() if qtd > 2}
                
                # Segunda passada para o processamento e extração filtrada
                for num_pag in range(len(leitor.pages)):
                    if num_pag < 2:
                        continue

                    pagina_objeto = leitor.pages[num_pag]
                    texto_pag = pagina_objeto.extract_text(extraction_mode="plain")
                    if not texto_pag:
                        continue

                    linhas_com_conteudo = [l for l in texto_pag.splitlines() if l.strip()]
                    if len(linhas_com_conteudo) < 6: # Descarte de páginas sem corpo útil substancial
                        continue                                                                        
                    
                    linhas_corrigidas = []

                    # --- EXTRAÇÃO DE IMAGENS COM MAPEAMENTO POR QUESTÃO ---
                    # Usa PyMuPDF para extrair imagens e identificar a questão associada
                    mapeamento_imagens = ExtracaoService._extrair_imagens_com_pymupdf(
                        pagina_objeto, num_pag, caminho_origem, pasta_imagens
                    )

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
                       
                        if linha_limpa in linhas_repetidas_lixo:
                            continue
                            
                        if re.search(r'.*Tipo.*Página.*', linha_limpa):
                            continue 
                        
                        # MODIFICAÇÃO AQUI: Verifica se a linha casa com alguma das matérias (incluindo as flexíveis)
                        eh_linha_de_materia = any(regex.match(linha_limpa) for regex in regras_materias.values())
                        
                        if eh_linha_de_materia:
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

                        se_inicio_bloco = re.match(r'^(\d+|\([A-E]\))', linha_limpa)

                        if se_inicio_bloco:

                            novo_numero = None
                            if se_inicio_bloco.group(1).isdigit():
                                novo_numero = int(se_inicio_bloco.group(1))
                                if novo_numero in mapeamento_imagens:
                                    # Insere a tag da imagem ANTES do número da questão
                                    tag = f"[TAG_IMAGEM_QUESTAO:{novo_numero}:{mapeamento_imagens[novo_numero]}]"
                                    linhas_corrigidas.append(tag)

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

                    if prefixo_atual or conteudo_acumulado:
                        texto_completo_bloco = " ".join(conteudo_acumulado)
                        texto_limpo_bloco = " ".join(texto_completo_bloco.split())
                        if not prefixo_atual:
                            linhas_corrigidas.append(texto_limpo_bloco)
                        else:
                            linhas_corrigidas.append(f"{prefixo_atual} {texto_limpo_bloco}".strip())

                    texto_pag_limpo = "\n".join(linhas_corrigidas) + "\n"
                    texto_completo_arquivo += texto_pag_limpo                                
                
                texto_acumulado_lote += texto_completo_arquivo

            except Exception as ex:
                callback_interface(None, None, f"❌ Erro ao ler subconteúdo do arquivo {nome_arq}: {str(ex)}\n")

        return texto_acumulado_lote

    @staticmethod
    def _executar_filtragem_materia(texto_completo, materia_inicial, callback_interface):
        """
        Isola os blocos do texto cumulativo correspondentes à matéria informada.
        Utiliza regras rígidas de isolamento (\b) para termos exatos e permite
        variações sequenciais para Direito, Raciocínio Lógico e Legislação.
        """
        # Mapeamento idêntico de regras para garantir que os limites de corte (fim) sejam precisos
        regras_materias = {
            "Língua Portuguesa": r'\bLíngua\s+Portuguesa\b',
            "Informática": r'\bInformática\b',
            "Analista de Tecnologia": r'\bAnalista\s+de\s+Tecnologia\b',
            "Conhecimentos Específicos": r'\bConhecimentos\s+Específicos\b',
            "Matemática": r'\bMatemática\b',
            "Língua Inglesa": r'\bLíngua\s+Inglesa\b',
            "História": r'\bHistória\b',
            "Geografia": r'\bGeografia\b',
            "Direito": r'\bDireito\b(?:\s+[A-ZÀ-Úa-zà-ú]+)*',
            "Raciocínio Lógico": r'\bRaciocínio\s+Lógico\b(?:[-\s]*[A-ZÀ-Úa-zà-ú]+)*',
            "Legislação": r'\bLegislação\b(?:\s+[A-ZÀ-Úa-zà-ú]+)*'
        }

        # 1. Determina a Regex de INÍCIO para a matéria selecionada
        if materia_inicial in regras_materias:
            # Força que a linha contenha apenas o padrão da matéria (com suas tolerâncias se for o caso)
            padrao_inicio = fr"^\s*{regras_materias[materia_inicial]}\s*$"
        else:
            padrao_inicio = fr"^\s*\b{reft(re.escape(materia_inicial))}\b\s*$"

        matches_inicio = list(re.finditer(padrao_inicio, texto_completo, re.MULTILINE | re.IGNORECASE))
        
        if not matches_inicio:
            return ""

        # 2. Determina as Regex de FIM (todas as OUTRAS matérias que servem como ponto de corte)
        materias_corte_padroes = [
            padrao for nome, padrao in regras_materias.items() 
            if nome.lower() != materia_inicial.lower()
        ]
        
        # Junta todas as outras matérias em um "OR" comercial (ex: (?:^Informática$|^Direito.*$))
        padrao_fim = r"^\s*(?:" + "|".join(materias_corte_padroes) + r")\s*$"

        texto_acumulado_materia = ""
        total_blocos = len(matches_inicio)

        for idx, match_atual in enumerate(matches_inicio):
            ponto_inicio_conteudo = match_atual.end()
            
            if idx + 1 < total_blocos:
                ponto_limite_busca = matches_inicio[idx + 1].start()
                sub_texto_busca = texto_completo[ponto_inicio_conteudo:ponto_limite_busca]
            else:
                sub_texto_busca = texto_completo[ponto_inicio_conteudo:]

            # Procura se alguma outra matéria surgiu no meio do caminho para cortar o bloco
            fim_match = re.search(padrao_fim, sub_texto_busca, re.MULTILINE | re.IGNORECASE)
            
            if fim_match:
                bloco_isolado = sub_texto_busca[:fim_match.start()]
            else:
                bloco_isolado = sub_texto_busca

            texto_acumulado_materia += bloco_isolado.strip() + "\n\n"

        texto_final_limpo = re.sub(r'(\n\s*){3,}', '\n\n', texto_acumulado_materia).strip()
        return texto_final_limpo

    @staticmethod
    def _converter_texto_para_estrutura_dados(conteudo_texto, gabaritos):
        """
        Interpreta o texto mapeado da matéria e converte na árvore estrutural
        de dicionários (Enunciado, Referência, Respostas A-E).
        Identifica a quebra de blocos quando a numeração da questão diminui
        e extrai a resposta correta correlacionando com a lista de gabaritos estruturados.
        """
        linhas = [linha.strip() for linha in conteudo_texto.split("\n")]
        dados_questoes = []
        total_linhas = len(linhas)
        i = 0

        # Controle de Blocos / Gabaritos estruturados
        indice_gabarito_atual = 0
        numero_questao_anterior = -1
        mapeamento_gabarito_vigente = {}

        # Função auxiliar interna para transformar a string "1;A\n2;B" em um dicionário rápido {1: "A", 2: "B"}
        def _parse_gabarito_string(txt_gabarito):
            mapa = {}
            for l in txt_gabarito.strip().split("\n"):
                if ";" in l:
                    partes = l.split(";")
                    if partes[0].isdigit():
                        mapa[int(partes[0])] = partes[1].strip().upper()
            return mapa

        # Inicializa o mapa do primeiro gabarito, se existir na lista
        if gabaritos and indice_gabarito_atual < len(gabaritos):
            mapeamento_gabarito_vigente = _parse_gabarito_string(gabaritos[indice_gabarito_atual])

        while i < total_linhas:
            if linhas[i].startswith("(A)"):
                idx_A = i
                respostas_temporarias = []
                idx_busca_alts = idx_A

                while idx_busca_alts < total_linhas:
                    linha_alt = linhas[idx_busca_alts]
                    match_alt = re.match(r"^\(([A-E])\)\s*(.*)", linha_alt)

                    if match_alt:
                        letra = match_alt.group(1)
                        texto_alternativa = match_alt.group(2).strip()

                        respostas_temporarias.append({
                            "texto": texto_alternativa,
                            "eh_correta": 0,
                        })

                        if letra == "E":
                            break
                    idx_busca_alts += 1

                idx_busca_enunciado = idx_A - 1
                linhas_enunciado = []
                idx_numero = -1
                texto_restante_da_linha_do_numero = ""

                while idx_busca_enunciado >= 0:
                    linha_atual = linhas[idx_busca_enunciado]
                    match_linha_iniciada_por_num = re.match(r"^(\d+)\s*(.*)$", linha_atual)

                    if match_linha_iniciada_por_num:
                        idx_numero = idx_busca_enunciado
                        texto_restante_da_linha_do_numero = match_linha_iniciada_por_num.group(2).strip()
                        break
                    
                    if linha_atual:
                        linhas_enunciado.insert(0, linha_atual)

                    idx_busca_enunciado -= 1

                if texto_restante_da_linha_do_numero:
                    linhas_enunciado.insert(0, texto_restante_da_linha_do_numero)                    

                enunciado_extraido = " ".join(linhas_enunciado).strip()
                texto_referencia_extraido = ""

                # --- AJUSTE DE ORDEM: Primeiro extraímos o texto de referência ---
                if idx_numero > 0:
                    idx_busca_ref = idx_numero - 1
                    linhas_ref = []

                    if linhas[idx_busca_ref].startswith("(E)"):
                        texto_referencia_extraido = ""
                    else:
                        while idx_busca_ref >= 0:
                            linha_ref_atual = linhas[idx_busca_ref]
                            if linha_ref_atual.startswith("(E)"):
                                break

                            if linha_ref_atual:
                                linhas_ref.insert(0, linha_ref_atual)                                

                            idx_busca_ref -= 1

                        texto_referencia_extraido = "\n".join(linhas_ref).strip()

                # --- CONTROLE DE MUDANÇA DE BLOCO E VINCULAÇÃO DO SEU GABARITO ---
                numero_questao_atual = None
                if idx_numero != -1:
                    linha_num_quest = linhas[idx_numero]
                    match_num = re.match(r"^(\d+)", linha_num_quest)
                    if match_num:
                        numero_questao_atual = int(match_num.group(1))

                        # 1. Detecta se o número diminuiu (Queda detectada -> Mudança de Bloco de Prova)
                        if numero_questao_anterior != -1 and numero_questao_atual < numero_questao_anterior:
                            indice_gabarito_atual += 1
                            # Avança para o próximo mapa de gabarito da lista
                            if gabaritos and indice_gabarito_atual < len(gabaritos):
                                mapeamento_gabarito_vigente = _parse_gabarito_string(gabaritos[indice_gabarito_atual])
                            else:
                                mapeamento_gabarito_vigente = {}

                        # Atualiza o histórico de numeração
                        numero_questao_anterior = numero_questao_atual

                        # 2. Busca direta no dicionário do gabarito corrente
                        if numero_questao_atual in mapeamento_gabarito_vigente:
                            letra_correta = mapeamento_gabarito_vigente[numero_questao_atual]
                            
                            # Mapeia a letra para o índice correspondente no array do JSON (0 a 4)
                            de_letra_para_indice = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
                            if letra_correta in de_letra_para_indice:
                                idx_correto = de_letra_para_indice[letra_correta]
                                if idx_correto < len(respostas_temporarias):
                                    respostas_temporarias[idx_correto]["eh_correta"] = 1

                # --- BUSCA PELA TAG DE IMAGEM COM VERIFICAÇÃO DO NÚMERO DA QUESTÃO ---
                imagem_associada = ""
                
                # Função auxiliar para extrair imagem da tag com validação do número
                def _extrair_imagem_da_tag(texto, numero_questao):
                    # Padrão para tags com número: [TAG_IMAGEM_QUESTAO:numero:nome_arquivo]
                    match_tag_com_numero = re.search(r"\[TAG_IMAGEM_QUESTAO:(\d+):(.*?)\]", texto)
                    if match_tag_com_numero:
                        numero_da_tag = int(match_tag_com_numero.group(1))
                        nome_arquivo = match_tag_com_numero.group(2)
                        # Verifica se o número da tag coincide com o número da questão atual
                        if numero_questao is not None and numero_da_tag == numero_questao:
                            return nome_arquivo, re.sub(r"\[TAG_IMAGEM_QUESTAO:\d+:.*?\]", "", texto)
                        # Se não coincide, mantém a tag para outra questão
                        return None, texto
                    
                    # Fallback: tag sem número (formato antigo)
                    match_tag_sem_numero = re.search(r"\[TAG_IMAGEM_QUESTAO:(.*?)\]", texto)
                    if match_tag_sem_numero:
                        nome_arquivo = match_tag_sem_numero.group(1)
                        # Verifica se o nome não contém ":" (para não confundir com o novo formato)
                        if ":" not in nome_arquivo:
                            texto_limpo = re.sub(r"\[TAG_IMAGEM_QUESTAO:.*?\]", "", texto)
                            return nome_arquivo, texto_limpo
                    
                    return None, texto
                
                # Procura no enunciado
                imagem_extraida, enunciado_extraido = _extrair_imagem_da_tag(
                    enunciado_extraido, numero_questao_atual
                )
                if imagem_extraida:
                    imagem_associada = imagem_extraida
                
                # Se não achou no enunciado, verifica no texto de referência
                if not imagem_associada and texto_referencia_extraido:
                    imagem_extraida, texto_referencia_extraido = _extrair_imagem_da_tag(
                        texto_referencia_extraido, numero_questao_atual
                    )
                    if imagem_extraida:
                        imagem_associada = imagem_extraida

                # Adiciona a estrutura finalizada incluindo o campo 'imagem'
                dados_questoes.append({
                    "enunciado": enunciado_extraido,
                    "texto_referencia": texto_referencia_extraido,
                    "respostas": respostas_temporarias,
                    "imagem": imagem_associada
                })

                i = idx_busca_alts + 1
                continue

            i += 1

        return dados_questoes    
    @staticmethod
    def _obter_gabaritos(lista_arquivos_provas, pasta_localizacao_provas, pasta_localizacao_gabaritos):
        """
        Para cada arquivo de prova, identifica o prefixo numérico, localiza os gabaritos 
        correspondentes na pasta de gabaritos, realiza a leitura/extração de cada um e 
        retorna uma listagem acumulada com o texto retornado por todos eles.
        """
        listagem_acumulada_textos = []

        # 1. Mapeia todos os arquivos da pasta de gabaritos uma única vez para otimizar o disco
        try:
            todos_gabaritos_pasta = [
                f for f in os.listdir(pasta_localizacao_gabaritos) 
                if f.lower().endswith(".pdf")
            ]
        except Exception:
            todos_gabaritos_pasta = []

        # 2. Itera sobre a lista de arquivos de prova fornecida
        for arquivo_prova in lista_arquivos_provas:
            # Captura o prefixo numérico inicial (ex: '010004')
            match = re.match(r'^(\d+)', arquivo_prova)
            if not match:
                continue
                
            prefixo_prova = match.group(1)
            
            # 3. Filtra os gabaritos da pasta que possuem o mesmo prefixo
            gabaritos_vinculados = [
                gab for gab in todos_gabaritos_pasta 
                if gab.startswith(prefixo_prova)
            ]            
            
            # Executa a rotina de extração passando o caminho do arquivo
            texto_extraido = ExtracaoService._extrair_respostas(arquivo_prova, gabaritos_vinculados, pasta_localizacao_gabaritos)
                
            listagem_acumulada_textos.append(texto_extraido)

        # Retorna a listagem contendo cada um dos retornos obtidos
        return listagem_acumulada_textos
    
    @staticmethod
    def _extrair_respostas(arquivo_prova, gabaritos_vinculados, pasta_localizacao_gabaritos):

        melhor_score_global = 0
        melhor_texto = ""

        for arquivo_gabarito in gabaritos_vinculados:

            caminho = os.path.join(
                pasta_localizacao_gabaritos,
                arquivo_gabarito
            )

            texto_pdf = ExtracaoService.extrair_texto(caminho)

            titulo, posicao, score = \
                ExtracaoService._localizar_melhor_bloco(
                    texto_pdf,
                    arquivo_prova
                )

            if not titulo:
                continue

            if score > melhor_score_global:

                inicio = posicao

                proximo = re.search(
                    r'.*?-\s*TIPO\s+\d+',
                    texto_pdf[inicio + len(titulo):],
                    re.MULTILINE
                )

                if proximo:
                    fim = inicio + len(titulo) + proximo.start()
                else:
                    fim = len(texto_pdf)

                bloco = texto_pdf[inicio:fim]

                respostas = \
                    ExtracaoService._extrair_gabarito_do_bloco(
                        bloco
                    )

                melhor_score_global = score
                melhor_texto = respostas

        return melhor_texto

    @staticmethod
    def _normalizar(texto):

        texto = texto.lower()

        texto = ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )

        texto = re.sub(r'[^a-z0-9 ]', ' ', texto)

        texto = re.sub(r'\s+', ' ', texto)

        return texto.strip()    
    
    @staticmethod
    def _obter_termos_prova(nome_arquivo):

        nome = os.path.splitext(nome_arquivo)[0]

        partes = nome.split(" - ")

        # remove prefixo numérico
        if partes and partes[0].isdigit():
            partes.pop(0)

        # remove nome do órgão
        if len(partes) > 1:
            partes.pop(0)

        texto = " ".join(partes)

        texto = ExtracaoService._normalizar(texto)

        palavras = [
            p for p in texto.split()
            if len(p) > 2
        ]

        return palavras    
    
    @staticmethod
    def _calcular_score(titulo, termos_prova):

        titulo_norm = ExtracaoService._normalizar(titulo)

        score = 0

        for termo in termos_prova:

            if termo in titulo_norm:
                score += 1

        return score    
    
    @staticmethod
    def _localizar_melhor_bloco(texto_pdf, arquivo_prova):

        termos = ExtracaoService._obter_termos_prova(arquivo_prova)

        regex_titulo = re.compile(
            r'^(.*?)\s*-\s*TIPO\s+\d+',
            re.MULTILINE
        )

        melhor_score = 0
        melhor_titulo = None
        melhor_posicao = -1

        for match in regex_titulo.finditer(texto_pdf):

            titulo = match.group(0)

            score = ExtracaoService._calcular_score(
                titulo,
                termos
            )

            if score > melhor_score:

                melhor_score = score
                melhor_titulo = titulo
                melhor_posicao = match.start()

        return melhor_titulo, melhor_posicao, melhor_score    
    
    @staticmethod
    def _extrair_gabarito_do_bloco(texto_bloco):

        respostas = re.findall(
            r'\b[A-E]\b|\*',
            texto_bloco
        )

        if len(respostas) < 60:
            return ""

        respostas = respostas[:60]

        return "\n".join(
            f"{i+1};{resp}"
            for i, resp in enumerate(respostas)
        )    
    
    @staticmethod
    def extrair_texto(caminho_pdf):

        try:

            reader = PdfReader(caminho_pdf)

            texto = ""

            for pagina in reader.pages:

                conteudo = pagina.extract_text()

                if conteudo:
                    texto += conteudo + "\n"

            return texto

        except Exception as e:

            print(f"Erro ao ler PDF: {e}")
            return ""    


    @staticmethod
    def _extrair_imagens_com_pymupdf(pagina_pdf, pagina_num, pdf_path, diretorio_saida) -> dict:
        """
        Usa PyMuPDF para extrair imagens com coordenadas precisas e identificar
        a questão associada.
        """
        
        mapeamento = {}
        
        # Abre o PDF com PyMuPDF
        doc = fitz.open(pdf_path)
        pagina = doc[pagina_num]
        
        # Obtém todas as imagens da página
        imagens = pagina.get_images()
        
        for img_index, img_info in enumerate(imagens):
            try:
                # Extrai a imagem
                xref = img_info[0]  # número de referência da imagem
                base_imagem = doc.extract_image(xref)
                
                # Salva a imagem
                nome_arquivo = f"{uuid.uuid4().hex}.{base_imagem['ext']}"
                caminho_completo = os.path.join(diretorio_saida, nome_arquivo)
                with open(caminho_completo, "wb") as f:
                    f.write(base_imagem["image"])
                
                # Obtém a posição da imagem na página
                # As imagens podem aparecer em múltiplos lugares, pegamos o primeiro
                image_rects = pagina.get_image_rects(xref)
                if image_rects:
                    rect = image_rects[0]  # retângulo da imagem
                    y_posicao = rect.y0  # coordenada Y do topo da imagem
                    
                    # Busca o número da questão acima da imagem
                    # Extrai todo o texto da página com coordenadas
                    text_blocks = pagina.get_text("dict")["blocks"]
                    
                    # Procura por números de questões antes da posição Y da imagem
                    numero_questao = ExtracaoService._buscar_questao_acima(
                        text_blocks, y_posicao
                    )
                    
                    if numero_questao:
                        mapeamento[numero_questao] = nome_arquivo
                    else:
                        # Fallback: tenta identificar pelo contexto
                        mapeamento[None] = nome_arquivo
                else:
                    mapeamento[None] = nome_arquivo
                    
            except Exception as e:
                print(f"Aviso: Falha ao extrair imagem {img_index}: {e}")
        
        doc.close()
        return mapeamento

    @staticmethod
    def _buscar_questao_acima(text_blocks, y_posicao_imagem) -> Optional[int]:
        """
        Busca o número da questão mais próximo acima da posição Y da imagem.
        """
        numeros_questoes = []
        
        for block in text_blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        # Coordenada Y do texto
                        y_texto = span["bbox"][1]  # y0 (canto superior)
                        texto = span["text"].strip()
                        
                        # Verifica se o texto está acima da imagem (y menor)
                        if y_texto < y_posicao_imagem:
                            # Verifica se é um número de questão (linha começando com número)
                            match = re.match(r'^(\d+)', texto)
                            if match:
                                numeros_questoes.append({
                                    'numero': int(match.group(1)),
                                    'distancia': y_posicao_imagem - y_texto
                                })
        
        # Se encontrou números, pega o mais próximo (menor distância)
        if numeros_questoes:
            numeros_questoes.sort(key=lambda x: x['distancia'])
            return numeros_questoes[0]['numero']
        
        return None
  
    """
    @staticmethod
    def _extrair_imagens_da_pagina(pagina_pdf, diretorio_saida) -> dict:

       # Inspeciona os recursos visuais de uma página do pypdf, extrai as imagens
       # e as salva no diretório especificado.
       # Retorna um dicionário: {numero_questao: nome_arquivo} 
       # (se conseguir identificar) ou {None: nome_arquivo} (fallback).
    
        mapeamento = {}
        
        # Verifica se a página possui dicionário de recursos e XObjects
        if "/Resources" in pagina_pdf and "/XObject" in pagina_pdf["/Resources"]:
            x_object = pagina_pdf["/Resources"]["/XObject"].get_object()
            
            for obj_id in x_object:
                obj_atual = x_object[obj_id]
                
                # Verifica se o objeto interno é de fato uma imagem
                if obj_atual.get("/Subtype") == "/Image":
                    try:
                        # Obtém os dados binários já decodificados
                        dados_imagem = obj_atual.get_data()
                        
                        # Gera nome único
                        nome_arquivo = f"{uuid.uuid4().hex}.jpg"
                        caminho_completo = os.path.join(diretorio_saida, nome_arquivo)
                        
                        # Salva a imagem (usando o método adaptado anteriormente)
                        ExtracaoService._salvar_imagem(obj_atual, dados_imagem, caminho_completo)
                        
                        # Tenta identificar o número da questão associada
                        numero_questao = ExtracaoService._identificar_questao_acima_imagem(
                            pagina_pdf, obj_atual, obj_id
                        )
                        
                        if numero_questao:
                            mapeamento[numero_questao] = nome_arquivo
                        else:
                            mapeamento[None] = nome_arquivo  # fallback
                            
                    except Exception as e:
                        print(f"Aviso: Falha ao extrair objeto de imagem {obj_id}: {e}")
        
        return mapeamento        
    """