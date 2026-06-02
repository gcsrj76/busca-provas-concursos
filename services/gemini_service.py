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
class GeminiService:
    def __init__(self):
        """Inicializa o cliente do Gemini se a biblioteca e a chave estiverem disponíveis."""

    def _chamar_api_gemini(self, texto_prova: str) -> dict:
        """
        Método interno encapsulado que faz a chamada estruturada para a API do Gemini.
        Retorna um dicionário contendo a lista de questões.
        """
        prompt_sistema = (
            "Extraia pra mim, do texto bruto da prova, todas as questões (e respectivas respostas) apenas de Língua Portuguesa, num layout jayson."
        )

        try:
            if genai:
                client = genai.Client(api_key="AQ.Ab8RN6KQ3NkjG0pO9jhTjUT3-uBLJhJwVYsENNaJQU-_7cxr-A")

            if client:
                #response = client.models.generate_content(model="gemini-3.5-flash", contents=f"Texto bruto da prova:\n\n{texto_prova}." + prompt_sistema)
                response = client.models.generate_content(model="gemini-3.5-flash", contents="Quantos ossos existem no corpo humano?")                
            
            # O SDK do Gemini com response_schema já valida e retorna uma string JSON válida
            import json
            return json.loads(response.text)
        except Exception:
            # Em caso de falha na API ou JSON inválido, retorna uma estrutura vazia segura
            return {"questoes": []}

    @staticmethod
    def executar_extracao(pasta_origem: str, restricoes_busca: str, callback_interface) -> None:
        """
        Lê os PDFs da pasta informada, aplica um pré-filtro dinâmico para economizar tokens,
        envia o conteúdo relevante ao Gemini e salva o resultado estruturado no Banco de Dados.
        """
        # Inicializa o serviço para checar credenciais
        servico_ia = GeminiService()
        # Lista os arquivos PDF
        arquivos = [f for f in os.listdir(pasta_origem) if f.lower().endswith('.pdf')]
        if not arquivos:
            callback_interface("Nenhum arquivo PDF encontrado na pasta informada.", 1.0)
            return

        session = SessionLocal()
        
        try:
            for idx, arquivo in enumerate(arquivos):
                progresso_atual = idx / len(arquivos)
                caminho_completo = os.path.join(pasta_origem, arquivo)
                callback_interface(f"Lendo páginas locais de: {arquivo}...", progresso_atual)

                texto_filtrado = ""
                try:
                    reader = PdfReader(caminho_completo)
                    for num_pagina, pagina in enumerate(reader.pages):
                        texto_pagina = pagina.extract_text() or ""
                        
                        # Filtro local preliminar inteligente para economizar valiosos tokens do plano gratuito
                        #termo_chave = restricoes_busca.lower().split()[0] if restricoes_busca else "portuguesa"
                        #if termo_chave in texto_pagina.lower() or "questão" in texto_pagina.lower() or "questao" in texto_pagina.lower():
                        #    texto_filtrado += f"\n--- PÁGINA {num_pagina+1} ---\n" + texto_pagina

                    if texto_pagina.strip():
                        callback_interface(f"Gemini estruturando dados de {arquivo}...", progresso_atual)
                        
                        # Chama o método interno que lida com a IA
                        resultado = servico_ia._chamar_api_gemini(texto_filtrado)
                        
                        if "questoes" in resultado and resultado["questoes"]:
                            questoes_salvas = 0
                            for q in resultado["questoes"]:
                                dict_alternativas = {
                                    "A": q.get("alternativa_A"),
                                    "B": q.get("alternativa_B"),
                                    "C": q.get("alternativa_C"),
                                    "D": q.get("alternativa_D"),
                                    "E": q.get("alternativa_E")
                                }
                                
                                # Proteção contra o erro AttributeError capturando o tipo corretamente
                                alt_correta = q.get("alternativa_correta")
                                alt_correta_tratada = alt_correta.upper() if isinstance(alt_correta, str) else None
                                
                                nova_questao = QuestaoSimuladoModel(
                                    materia=restricoes_busca[:50],
                                    enunciado=q.get("enunciado"),
                                    alternativas=dict_alternativas,
                                    alternativa_correta=alt_correta_tratada
                                )
                                session.add(nova_questao)
                                questoes_salvas += 1
                            
                            session.commit()
                            callback_interface(f"Sucesso: {questoes_salvas} questões salvas de {arquivo}.", progresso_atual)
                        else:
                            callback_interface(f"Aviso: Nenhuma questão mapeada em {arquivo}.", progresso_atual)

                    else:
                        callback_interface(f"Ignorado: Conteúdo relevante não encontrado em {arquivo}.", progresso_atual)

                    # Intervalo de segurança de 5 segundos exigido pelo plano gratuito (Evita erro HTTP 429 - Too Many Requests)
                    time.sleep(5)

                except Exception as e:
                    session.rollback()
                    callback_interface(f"Falha ao processar {arquivo}: {str(e)}", progresso_atual)
                    time.sleep(2) # Pausa amigável antes do próximo arquivo se houver erro de rede

            callback_interface("Extração Inteligente com Gemini concluída!", 1.0)

        finally:
            session.close()

    @staticmethod
    def executar_extracao_manual(caminho_pdf, callback_interface):

        arquivos = [f for f in os.listdir(caminho_pdf) if f.lower().endswith(".pdf")]
        total = len(arquivos)

        if total == 0:
            callback_interface("Nenhum PDF encontrado na pasta de origem.", 1.0, "Processamento vazio.\n")
            return

        session = SessionLocal()

        try:
            for i, nome_arq in enumerate(arquivos):
                prog = (i + 1) / total
                callback_interface(f"Analisando arquivo {i+1}/{total}: {nome_arq}...", prog)
                caminho_origem = os.path.join(caminho_pdf, nome_arq)
                
                texto_completo_prova = ""
                try:
                    with open(caminho_origem, "rb") as f:                    
                        leitor = PdfReader(f)
                        for num_pag in range(len(leitor.pages)):
                            # ESSENCIAL: Usamos extraction_mode="layout" para ler duas colunas de forma correta e sem misturar textos horizontais
                            texto_pag = leitor.pages[num_pag].extract_text(extraction_mode="layout")
                            if texto_pag:
                                texto_completo_prova += texto_pag + "\n"

                    # 1. Filtra para pegar apenas a seção de Língua Portuguesa até o início de outra matéria
                    inicio_match = re.search(r"Língua\s+Portuguesa", texto_completo_prova, re.IGNORECASE)
                    if not inicio_match:
                        callback_interface(f"Aviso: Matéria não encontrada em {nome_arq}.", prog)
                        continue

                    texto_portugues = texto_completo_prova[inicio_match.start():]
                    
                    # Corta se achar termos de quebra padrão de outras matérias nas provas da FGV
                    fim_match = re.search(r"\n\s*(Legislação|Direito|Informática|Raciocínio|Conhecimentos\s+Específicos|Matemática)", texto_portugues, re.IGNORECASE)
                    if fim_match:
                        texto_portugues = texto_portugues[:fim_match.start()]

                    # 2. Divide o bloco de português nos marcadores numéricos de questões (ex: '\n 1 \n' ou '\n1\n')
                    padrao_questao = r"\n\s*([1-9][0-9]?)\s+(?=[A-ZÀ-Ú])"
                    partes = re.split(padrao_questao, texto_portugues)
                    
                    # Salva possíveis cabeçalhos / textos iniciais de apoio
                    texto_previo_ou_contexto = partes[0].strip()
                    questoes_salvas = 0

                    # Percorre os fragmentos (Índice Ímpar: Número da questão | Índice Par: Conteúdo da questão)
                    for idx_bloco in range(1, len(partes), 2):
                        num_questao = partes[idx_bloco].strip()
                        corpo_questao = partes[idx_bloco+1] if idx_bloco+1 < len(partes) else ""

                        # 3. Mapeia e fatia as alternativas (A) até (E), mesmo que fiquem juntas na mesma linha visual
                        padrao_alternativas = r"(\([A-E]\))"
                        fragmentos_alternativas = re.split(padrao_alternativas, corpo_questao)
                        
                        enunciado_cru = fragmentos_alternativas[0].strip()
                        # Limpa múltiplos tabs/espaços criados pelo layout em colunas
                        enunciado_limpo = re.sub(r'[ \t]+', ' ', enunciado_cru)

                        # Se houver um texto base herdado ou associado, concatena no enunciado
                        if texto_previo_ou_contexto and ("Atenção" in texto_previo_ou_contexto or "Texto" in texto_previo_ou_contexto):
                            enunciado_final = f"[{texto_previo_ou_contexto}]\n\n{enunciado_limpo}"
                        else:
                            enunciado_final = enunciado_limpo

                        dict_alternativas = {"A": "", "B": "", "C": "", "D": "", "E": ""}
                        
                        # Processa os pares de letra indicadora + texto da alternativa correspondente
                        for j in range(1, len(fragmentos_alternativas), 2):
                            letra = fragmentos_alternativas[j].replace("(", "").replace(")", "").strip()
                            texto_alt = fragmentos_alternativas[j+1].strip() if j+1 < len(fragmentos_alternativas) else ""
                            
                            # Evita que uma alternativa traga o pedaço de outra subsequente
                            texto_alt = re.split(r"\s*\([A-E]\)", texto_alt)[0]
                            texto_alt = re.sub(r'[ \t]+', ' ', texto_alt).strip()
                            
                            if letra in dict_alternativas:
                                dict_alternativas[letra] = texto_alt

                        # Atualiza o contexto se a questão atual contiver indicações de texto para as próximas
                        if "Atenção:" in corpo_questao or "Texto" in corpo_questao:
                            linhas = corpo_questao.split("\n")
                            texto_previo_ou_contexto = "\n".join([l for l in linhas if not any(alt in l for alt in ["(A)","(B)","(C)","(D)","(E)"])]).strip()

                        # 4. Gravação segura no Banco de Dados
                        nova_questao = QuestaoSimuladoModel(
                            materia="Língua Portuguesa",
                            enunciado=enunciado_final,
                            alternativas=dict_alternativas,
                            alternativa_correta=None  # Regex não detecta gabarito em cadernos comuns de prova; fica nulo
                        )
                        session.add(nova_questao)
                        questoes_salvas += 1

                    session.commit()
                    callback_interface(f"Sucesso: {questoes_salvas} questões manuais salvas de {nome_arq}.", prog)

                except Exception as ex:
                    session.rollback()
                    callback_interface(f"Falha ao processar manualmente {nome_arq}: {str(ex)}", prog)

            callback_interface("Extração por Código/Regex Concluída!", 1.0)

        finally:
            session.close()

    @staticmethod
    def executar_extracao_questoes(pasta_origem: str, callback_interface) -> None:
        """
        Método estático que processa uma pasta de PDFs, força a estrutura de JSON estrita,
        mapeia textos de referência/base das questões e gera o arquivo consolidado.
        """
        servico_ia = GeminiService()     

        if genai:
            client = genai.Client(api_key="AQ.Ab8RN6KQ3NkjG0pO9jhTjUT3-uBLJhJwVYsENNaJQU-_7cxr-A")

        # Inicializamos a estrutura mestre com os valores estritamente fixos que você solicitou
        json_consolidado = {
            "entidade": "Questao",
            "materia": "MATÉRIA IMPORTADA",
            "ementa": "EMENTA IMPORTADA",
            "dados": []
        }
        
        if not os.path.exists(pasta_origem):
            callback_interface(f"Erro: A pasta '{pasta_origem}' não existe.", 0.0)
            return

        arquivos_pdf = [f for f in os.listdir(pasta_origem) if f.lower().endswith('.pdf')]
        total_arquivos = len(arquivos_pdf)
        
        if not arquivos_pdf:
            callback_interface("Nenhum arquivo PDF encontrado.", 1.0)
            return
            
        callback_interface(f"Encontrado(s) {total_arquivos} arquivo(s).\n", 0.0)

        for idx, arquivo in enumerate(arquivos_pdf):
            progresso_atual = idx / total_arquivos
            caminho_completo = os.path.join(pasta_origem, arquivo)
            callback_interface(f"--- Processando: {arquivo} ---", progresso_atual)
            
            try:
                reader = PdfReader(caminho_completo)
                
                for index, pagina in enumerate(reader.pages):
                    texto_pagina = pagina.extract_text()
                    
                    if not texto_pagina.strip():
                        continue
                    
                    callback_interface(f"[{arquivo}] Analisando página {index + 1}...", progresso_atual)
                    
                    # Prompt ajustado cirurgicamente para o cenário da imagem (textos base + colunas)
                    prompt = (
                            "Você é um especialista em estruturação de dados de concursos públicos.\n"
                            "Sua tarefa é analisar o texto da página do PDF e extraia APENAS as questões de Língua Portuguesa.\n\n"
                            "REGRAS CRÍTICAS DE FILTRAGEM E EXTRAÇÃO:\n"
                            "1. FILTRO DE MATÉRIA: Extraia estritamente as questões pertencentes à disciplina de Língua Portuguesa "
                            "(interpretação de texto, gramática, sintaxe, etc.). Se na página houver uma transição de conteúdo e começarem "
                            "questões de outras matérias (como 'Legislação Educacional', 'Direito', 'Informática', 'Matemática', etc.), "
                            "IGNORE completamente essas questões de outras matérias. Elas NÃO devem entrar no JSON.\n"
                            "2. TEXTO DE REFERÊNCIA: Identifique se há textos de apoio ou avisos de escopo antes da questão "
                            "(ex: 'Atenção: o texto a seguir refere-se...'). Se houver, capture esse texto base e insira no campo "
                            "'texto_referencia' de cada uma das questões correspondentes. Se a questão for isolada e não tiver texto base, "
                            "deixe o campo como uma string vazia (\"\").\n"
                            "3. ENUNCIADO E ALTERNATIVAS: Capture a pergunta na íntegra. Mapeie as opções de A a E na lista de 'respostas', "
                            "definindo 'eh_correta' como 1 no gabarito e 0 nas demais.\n"
                            "4. VALORES FIXOS: Mantenha os campos 'entidade', 'materia' e 'ementa' exatamente como definidos no schema, "
                            "sem alterá-los por causa do conteúdo da página."
                        )

                    if client:
                        response = client.models.generate_content(
                            model="gemini-3.5-flash",
                            contents=[prompt, texto_pagina],
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=EstruturaFinalSchema, # Garante os Literais fixos e o novo campo
                                temperature=0.1
                            ),
                        )                    
                    
                    resultado_pagina = json.loads(response.text)
                    questoes_encontradas = resultado_pagina.get("dados", [])
                    
                    if questoes_encontradas:
                        # Fazemos uma limpa adicional via código para garantir que strings nulas virem "" no texto_referencia
                        for q in questoes_encontradas:
                            if not q.get("texto_referencia"):
                                q["texto_referencia"] = ""
                                
                        json_consolidado["dados"].extend(questoes_encontradas)
                        callback_interface(f"[{arquivo}] +{len(questoes_encontradas)} questão(ões) obtida(s).", progresso_atual)
                    else:
                        callback_interface(f"[{arquivo}] Nenhuma questão mapeada na página {index + 1}.", progresso_atual)
                        
            except Exception as e:
                callback_interface(f"Erro no arquivo {arquivo}: {str(e)}", progresso_atual)
                continue

        # Salvamento final consolidado
        nome_arquivo_final = "questoes_extraidas_consolidado.json"
        try:
            with open(nome_arquivo_final, "w", encoding="utf-8") as f:
                json.dump(json_consolidado, f, ensure_ascii=False, indent=2)
            callback_interface(f"\nSucesso! Arquivo '{nome_arquivo_final}' gerado.", 1.0)
        except Exception as e:
            callback_interface(f"Erro ao salvar arquivo: {str(e)}", 1.0)