import os
import time
from typing import List, Optional
from pydantic import BaseModel, Field

# Conexões e Modelos do seu projeto
from database.connection import SessionLocal
from database.models import QuestaoSimuladoModel

# Tentativa de importação do SDK do Gemini e do PyPDF
try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import pypdf
except ImportError:
    pypdf = None


# 1. Definição da estrutura de dados esperada (Pydantic) para garantir o JSON correto
class QuestaoSchema(BaseModel):
    enunciado: str = Field(description="O enunciado completo da questão de concurso.")
    alternativa_A: str = Field(description="Texto da alternativa A.")
    alternativa_B: str = Field(description="Texto da alternativa B.")
    alternativa_C: str = Field(description="Texto da alternativa C.")
    alternativa_D: str = Field(description="Texto da alternativa D.")
    alternativa_E: str = Field(description="Texto da alternativa E.")
    alternativa_correta: Optional[str] = Field(description="Apenas a letra correspondente à alternativa correta (A, B, C, D ou E). Se não houver, nulo.")

class ListaQuestoesSchema(BaseModel):
    questoes: List[QuestaoSchema]


# 2. Classe de Serviço Unificada
class GeminiService:
    def __init__(self):
        """Inicializa o cliente do Gemini se a biblioteca e a chave estiverem disponíveis."""
        self.client_disponivel = False
        self.model_name = "gemini-1.5-flash"  # Ideal para velocidade, estruturação e plano gratuito
        
        if genai:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self.client_disponivel = True

    def _chamar_api_gemini(self, texto_prova: str, restricoes_busca: str) -> dict:
        """
        Método interno encapsulado que faz a chamada estruturada para a API do Gemini.
        Retorna um dicionário contendo a lista de questões.
        """
        if not self.client_disponivel:
            return {"questoes": []}

        prompt_sistema = (
            "Você é um professor especialista em estruturar simulados e analisar provas de concursos públicos. "
            f"Sua tarefa estrita é analisar o texto bruto fornecido e extrair APENAS as questões que correspondam à matéria ou restrição: '{restricoes_busca}'. "
            "Ignore qualquer questão que pertença a outra matéria. Separe minuciosamente o enunciado das alternativas (A até E)."
        )

        try:
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(
                f"Texto bruto da prova:\n\n{texto_prova}",
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=ListaQuestoesSchema,
                    temperature=0.1  # Baixa temperatura para manter o modelo focado e factual
                ),
                system_instruction=prompt_sistema
            )
            
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
        # Validação do PyPDF
        if not pypdf:
            callback_interface("Erro: Instale o pypdf!", 1.0, "Execute: pip install pypdf\n")
            return

        # Inicializa o serviço para checar credenciais
        servico_ia = GeminiService()
        if not servico_ia.client_disponivel:
            callback_interface("Erro: Variável GEMINI_API_KEY não configurada ou biblioteca ausente.", 1.0)
            return

        # Lista os arquivos PDF
        arquivos = [f for f in os.listdir(pasta_origem) if f.lower().endswith('.pdf')]
        if not archivos:
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
                    reader = pypdf.PdfReader(caminho_completo)
                    for num_pagina, pagina in enumerate(reader.pages):
                        texto_pagina = pagina.extract_text() or ""
                        
                        # Filtro local preliminar inteligente para economizar valiosos tokens do plano gratuito
                        termo_chave = restricoes_busca.lower().split()[0] if restricoes_busca else "portuguesa"
                        if termo_chave in texto_pagina.lower() or "questão" in texto_pagina.lower() or "questao" in texto_pagina.lower():
                            texto_filtrado += f"\n--- PÁGINA {num_pagina+1} ---\n" + texto_pagina

                    if texto_filtrado.strip():
                        callback_interface(f"Gemini estruturando dados de {arquivo}...", progresso_atual)
                        
                        # Chama o método interno que lida com a IA
                        resultado = servico_ia._chamar_api_gemini(texto_filtrado, restricoes_busca)
                        
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