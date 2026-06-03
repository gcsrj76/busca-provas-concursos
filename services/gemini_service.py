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
    def executar_extracao_manual(caminho_pdf, materia_inicial, callback_interface):
        """
        Varre os PDFs, identifica o bloco de texto entre a materia_inicial e a próxima matéria
        da lista de possíveis matérias da FGV, concatena tudo e gera um arquivo texto final.
        """
        import os
        import re
        from pypdf import PdfReader

        arquivos = [f for f in os.listdir(caminho_pdf) if f.lower().endswith(".pdf")]
        total = len(arquivos)

        if total == 0:
            callback_interface("Nenhum PDF encontrado na pasta de origem.", 1.0, "Processamento vazio.\n")
            return

        # Lista de possíveis matérias finais para servir de limite/corte
        lista_materias_possiveis = [
            "Língua Portuguesa", 
            "Legislação", 
            "Raciocínio Lógico", 
            "Informática", 
            "Analista de Tecnologia",
            "Direito",
            "Conhecimentos Específicos",
            "Matemática"
        ]

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
                        texto_pag = leitor.pages[num_pag].extract_text(extraction_mode="layout")
                        if texto_pag:
                            texto_completo_prova += texto_pag + "\n"

                # 1. Encontra onde começa a matéria desejada (materia_inicial)
                # Escapa caracteres especiais que possam vir no parâmetro para não quebrar a Regex
                termo_inicio_esc = re.escape(materia_inicial)
                inicio_match = re.search(fr"{termo_inicio_esc}", texto_completo_prova)
                
                if not inicio_match:
                    callback_interface(None, prog, f"⚠️ Aviso: Matéria '{materia_inicial}' não encontrada em {nome_arq}.\n")
                    continue

                # Isola o texto a partir do início da matéria solicitada
                texto_escopo = texto_completo_prova[inicio_match.start():]
                
                # 2. Constrói dinamicamente a Regex de parada com as matérias que NÃO são a inicial
                # Exemplo: Se o usuário pediu "Legislação", a lista de corte terá as outras
                materias_corte = [m for m in lista_materias_possiveis if m.lower() != materia_inicial.lower()]
                padrao_fim = r"\n\s*(" + "|".join([re.escape(m) for m in materias_corte]) + r")"
                
                fim_match = re.search(padrao_fim, texto_escopo)
                
                if fim_match:
                    # Corta o texto no ponto exato onde a próxima matéria começa
                    texto_escopo = texto_escopo[:fim_match.start()]

                # 3. Alimenta o acumulador de blocos, adicionando separadores claros de cabeçalho
                texto_acumulado_final += f"\n\n{'='*80}\n"
                texto_acumulado_final += f"FONTE: {nome_arq} | MATÉRIA EXTRÁIDA: {materia_inicial}\n"
                texto_acumulado_final += f"{'='*80}\n\n"
                texto_acumulado_final += texto_escopo.strip()
                
                arquivos_processados += 1
                callback_interface(None, prog, f"✅ Bloco de '{materia_inicial}' extraído com sucesso de {nome_arq}.\n")

            except Exception as ex:
                callback_interface(None, prog, f"❌ Falha ao processar {nome_arq}: {str(ex)}\n")

        # 4. Gravação do arquivo texto final com todo o conteúdo concatenado
        if arquivos_processados > 0:
            try:
                # O arquivo txt será gerado na mesma pasta onde estão os PDFs
                nome_arquivo_txt = f"extracao_acumulada_{materia_inicial.replace(' ', '_').lower()}.txt"
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

    @staticmethod
    def separar_colunas_se_houver(bloco_texto):
        """
        Se o bloco contiver linhas largas com grande espaçamento central,
        separa a coluna da esquerda (geralmente textos) da coluna da direita (questões).
        """
        linhas = bloco_texto.split('\n')
        coluna_esquerda = []
        coluna_direita = []
        
        for linha in linhas:
            if "   " in linha:
                # Divide a linha em duas metades aproximadas onde houver mais de 8 espaços vazios
                partes = re.split(r'\s{8,}', linha, maxsplit=1)
                if len(partes) == 2:
                    coluna_esquerda.append(partes[0])
                    coluna_direita.append(partes[1])
                    continue
            coluna_esquerda.append(linha)
        
        if len(coluna_direita) > len(linhas) * 0.3:
            return "\n".join(coluna_esquerda), "\n".join(coluna_direita)
        return bloco_texto, ""        

    @staticmethod
    def extrair_questoes_para_json_adequado(caminho_txt, caminho_json_saida):
        if not os.path.exists(caminho_txt):
            print("Arquivo de origem não encontrado.")
            return

        with open(caminho_txt, "r", encoding="utf-8") as f:
            conteudo = f.read()

        lista_dados_questoes = []

        # 1. Separar o arquivo em blocos por páginas ou por grandes cabeçalhos de FONTE para não misturar provas
        blocos_fontes = conteudo.split("================================================================================")
        
        for bloco_fonte in blocos_fontes:
            if not bloco_fonte.strip() or "FONTE:" in bloco_fonte:
                continue
                
            # Limpa ruídos clássicos de rodapé/cabeçalho antes de processar
            bloco_limpo = re.sub(r".*?\n", "", bloco_fonte)
            bloco_limpo = re.sub(r"FGV Projetos.*?\n", "", bloco_limpo)
            bloco_limpo = re.sub(r"Tipo \d – Cor .*?\n", "", bloco_limpo)

            # 2. Divide o texto identificando os números de questões isolados (ex: \n1\n ou \n2\n)
            padrao_divisao = r"\n\s*([1-9][0-9]?)\s*\n"
            partes = re.split(padrao_divisao, bloco_limpo)
            
            if len(partes) < 2:
                continue

            # O fragmento inicial antes da primeira questão geralmente armazena o Texto Base (coluna da esquerda)
            texto_contexto_atual = partes[0].strip()
            
            # Remove linhas que sejam apenas numéricas ou ruídos do contexto inicial
            texto_contexto_atual = "\n".join([l for l in texto_contexto_atual.split("\n") if not l.strip().isdigit()])

            # Percorre os fragmentos de 2 em 2 (Índice Ímpar = Número da Questão, Índice Par = Conteúdo)
            for idx in range(1, len(partes), 2):
                num_questao = partes[idx].strip()
                corpo_bloco = partes[idx+1] if idx+1 < len(partes) else ""
                
                # Se houver coluna dupla ativa, separa o conteúdo
                col_esq, col_dir = GeminiService.separar_colunas_se_houver(corpo_bloco)
                
                if col_dir.strip():
                    corpo_questao = col_dir
                    # Se a coluna da esquerda contiver um texto base novo, atualiza o contexto
                    if "Texto" in col_esq or "TEXTO" in col_esq:
                        texto_contexto_atual = col_esq.strip()
                else:
                    corpo_questao = col_esq

                # 3. Captura e isola as alternativas (A) até (E) de forma segura
                padrao_alternativas = r"(\([A-E]\))"
                fragmentos_alternativas = re.split(padrao_alternativas, corpo_questao)
                
                enunciado_cru = fragmentos_alternativas[0].strip()
                # Remove quebras de linha abruptas do enunciado transformando-o em texto corrido
                enunciado_limpo = re.sub(r'\s+', ' ', enunciado_cru).strip()
                
                lista_respostas = []
                
                # Processa os pares: Letra da alternativa -> Conteúdo
                for j in range(1, len(fragmentos_alternativas), 2):
                    letra = fragmentos_alternativas[j].strip()
                    texto_alt = fragmentos_alternativas[j+1].strip() if j+1 < len(fragmentos_alternativas) else ""
                    
                    # Garante que o texto da alternativa não capture o início da próxima ou ruídos de fim de bloco
                    texto_alt = re.split(r"\s*\([A-E]\)", texto_alt)[0]
                    # Se houver uma mudança de questão que vazou para cá, corta o excesso
                    texto_alt = re.split(r"\n\s*[1-9][0-9]?\s*\n", texto_alt)[0]
                    
                    texto_alt = re.sub(r'\s+', ' ', texto_alt).strip()
                    
                    if texto_alt:
                        lista_respostas.append({
                            "texto": f"{letra} {texto_alt}",
                            "eh_correta": 0
                        })

                # Verifica se o próprio enunciado cita que pertence a um texto específico
                texto_referencia_final = ""
                if "texto 1" in enunciado_limpo.lower() or "texto i " in enunciado_limpo.lower():
                    texto_referencia_final = texto_contexto_atual if "Texto 1" in texto_contexto_atual or "Texto I" in texto_contexto_atual else ""
                elif "texto 2" in enunciado_limpo.lower() or "texto ii" in enunciado_limpo.lower():
                    texto_referencia_final = texto_contexto_atual if "Texto 2" in texto_contexto_atual or "Texto II" in texto_contexto_atual else ""
                else:
                    # Se não houver menção explícita, associa o contexto acumulador caso ele pareça um texto de apoio
                    texto_referencia_final = texto_contexto_atual if ("Texto" in texto_contexto_atual or len(texto_contexto_atual) > 100) else ""

                # Ajusta quebras do texto de referência para ficar legível no JSON
                if texto_referencia_final:
                    texto_referencia_final = re.sub(r'[ \t]+', ' ', texto_referencia_final).strip()

                # Ignora blocos vazios gerados por quebras incorretas do parser
                if not enunciado_limpo or len(lista_respostas) < 2:
                    continue

                questao_dados = {
                    "enunciado": f"{num_questao}. {enunciado_limpo}",
                    "texto_referencia": texto_referencia_final if texto_referencia_final else None,
                    "respostas": lista_respostas
                }
                
                lista_dados_questoes.append(questao_dados)

        # Estrutura a raiz final do JSON em conformidade com o formato exigido
        json_final_estruturado = {
            "entidade": "Questao",
            "materia": "MATERIA IMPORTAÇÃO",
            "ementa": "EMENTA IMPORTAÇÃO",
            "dados": lista_dados_questoes
        }

        # Gravação final com tratamento de caracteres especiais e identação
        with open(caminho_json_saida, "w", encoding="utf-8") as f_json:
            json.dump(json_final_estruturado, f_json, ensure_ascii=False, indent=4)
            
        print(f"Sucesso! {len(lista_dados_questoes)} questões adequadas ao novo formato e salvas em: {caminho_json_saida}")