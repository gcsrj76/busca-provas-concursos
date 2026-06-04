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

    @staticmethod
    def executar_extracao_manual(caminho_pdf, materia_inicial, callback_interface):
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
            "História", "História"
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

                # 1. Encontra onde começa a matéria desejada (materia_inicial) - Strict Case
                termo_inicio_esc = re.escape(materia_inicial)
                inicio_match = re.search(fr"{termo_inicio_esc}", texto_completo_prova)
                
                if not inicio_match:
                    callback_interface(None, prog, f"⚠️ Aviso: Matéria '{materia_inicial}' não encontrada em {nome_arq}.\n")
                    continue

                # Descarta o termo correspondente à matéria inicial e remove espaços/quebras iniciais
                texto_escopo = texto_completo_prova[inicio_match.end():].lstrip()
                
                # 2. Constrói dinamicamente a Regex de parada com as matérias que NÃO são a inicial
                materias_corte = [m for m in lista_materias_possiveis if m != materia_inicial]
                
                # ALTERAÇÃO CRUCIAL AQUI:
                # [ \t]{2,} -> Exige que a palavra seja precedida por pelo menos 2 espaços ou tabs (indica início de coluna)
                # Opcionalmente aceita o início de uma nova linha pura (\n\s*)
                # (.*)      -> Engole o resto da linha (ex: " Educacional") protegendo o Case Sensitive do início do termo
                padrao_fim = r"(?:\n\s*|[ \t]{2,})(" + "|".join([re.escape(m) for m in materias_corte]) + r")(.*)"                
                
                # Execução estrita (SEM re.IGNORECASE) para proteger os blocos relevantes
                fim_match = re.search(padrao_fim, texto_escopo)
                
                if fim_match:
                    # Corta o texto exatamente no ponto onde o espaçamento da nova matéria começou
                    texto_escopo = texto_escopo[:fim_match.start()]

                # --- SANITIZAÇÃO DE LINHAS EM BRANCO (NÍVEL DE BLOCO) ---
                texto_escopo_limpo = re.sub(r'(\n\s*){3,}', '\n\n', texto_escopo)

                # 3. Alimenta o acumulador de blocos
                texto_acumulado_final += texto_escopo_limpo.strip() + "\n\n"
                
                arquivos_processados += 1
                callback_interface(None, prog, f"✅ Bloco de '{materia_inicial}' extraído com sucesso de {nome_arq}.\n")

            except Exception as ex:
                callback_interface(None, prog, f"❌ Falha ao processar {nome_arq}: {str(ex)}\n")

        # 4. Gravação do arquivo texto final com todo o conteúdo concatenado e revisado
        if arquivos_processados > 0:
            try:
                nome_arquivo_txt = f"extracao_acumulada_{materia_inicial.replace(' ', '_').lower()}.txt"
                caminho_salvamento_txt = os.path.join(caminho_pdf, nome_arquivo_txt)

                # Remove automaticamente qualquer linha/frase idêntica de tamanho >= 10 que se repita 4 ou mais vezes
                callback_interface(None, 0.95, "🧹 Executando varredura algorítmica de remoção de trechos repetidos...\n")

                texto_acumulado_final = re.sub(r'(\n\s*){3,}', '\n\n', texto_acumulado_final)                
                texto_acumulado_final = GeminiService.remover_trechos_repetidos_otimizado(texto_acumulado_final, min_len=10, min_rep=4)                
                
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
    def executar_extracao_pdf(caminho_pdf, callback_interface):
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
                            texto_completo_prova += GeminiService.reorganizar_duas_colunas(texto_pag)

                # 3. Alimenta o acumulador de blocos
                texto_acumulado_final += texto_completo_prova
                
                arquivos_processados += 1

            except Exception as ex:
                callback_interface(None, prog, f"❌ Falha ao processar {nome_arq}: {str(ex)}\n")

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
    def reorganizar_duas_colunas(texto_pagina):

        coluna_esquerda = ""
        coluna_direita =  ""

        linhas = texto_pagina.splitlines()

        for linha in linhas:

            inicia_deslocada = bool(re.match(r'^ {30,}', linha))

            encontrado = re.search(r' {5,}', linha.strip())

            if encontrado:

                texto_limpo = linha.strip()

                partes = re.split(r' {5,}', texto_limpo, maxsplit=1)

                if len(partes) == 2:
                    coluna_esquerda += partes[0].rstrip() + "\n"
                    coluna_direita += partes[1].lstrip() + "\n"
                else:
                    # segurança
                    if inicia_deslocada:
                        coluna_direita += texto_limpo + "\n"
                    else:
                        coluna_esquerda += texto_limpo + "\n"

            else:

                if inicia_deslocada:
                    coluna_direita += linha.strip() + "\n"
                else:
                    coluna_esquerda += linha.rstrip() + "\n"

        return coluna_esquerda + "\n" + coluna_direita

    """
    @staticmethod
    def reorganizar_duas_colunas(texto_pagina):

        linhas = texto_pagina.splitlines()

        maiores_blocos = []

        for linha in linhas:
            encontrados = re.findall(r' {5,}', linha)

            if encontrados:
                maiores_blocos.append(max(len(x) for x in encontrados))

        if not maiores_blocos:
            return texto_pagina

        limite = max(10, int(sum(maiores_blocos) / len(maiores_blocos) * 0.7))

        coluna_esquerda = []
        coluna_direita = []

        for linha in linhas:

            partes = re.split(rf' {{{limite},}}', linha, maxsplit=1)

            if len(partes) == 2:
                esq, dir = partes

                if esq.strip():
                    coluna_esquerda.append(esq.rstrip())

                if dir.strip():
                    coluna_direita.append(dir.rstrip())
            else:
                coluna_esquerda.append(linha.rstrip())

        return (
            "\n".join(coluna_esquerda)
            + "\n\n"
            + "\n".join(coluna_direita)
        )
    """        

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
                # Usa o método existente no seu GeminiService para quebrar a linha física em duas partes
                esq, direi = GeminiService.separar_colunas_se_houver(linha)
                
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
    def remover_trechos_repetidos_otimizado(texto, min_len=10, min_rep=4):
        """
        Garante que apenas LINHAS INTEIRAS repetidas (como cabeçalhos e rodapés)
        sejam removidas, protegendo a integridade das palavras e textos do documento.
        """
        if not texto:
            return ""

        linhas = texto.split("\n")
        contagem_linhas = {}
        
        # 1. Conta apenas linhas completas que tenham relevância de tamanho
        for linha in linhas:
            linha_limpa = linha.strip()
            if len(linha_limpa) >= min_len:
                contagem_linhas[linha_limpa] = contagem_linhas.get(linha_limpa, 0) + 1

        # 2. Identifica quais linhas limpas são lixo repetitivo (aparecem >= 4 vezes)
        linhas_lixo = {linha for linha, qtd in contagem_linhas.items() if qtd >= min_rep}

        if not linhas_lixo:
            return texto

        # 3. Reconstrói o texto filtrando e ignorando as linhas que batem com o lixo
        linhas_finais = []
        for linha in linhas:
            if linha.strip() in linhas_lixo:
                continue  # Remove a linha repetitiva inteira
            linhas_finais.append(linha)

        return "\n".join(linhas_finais)            
    
    """
    def _chamar_api_gemini(self, texto_prova: str) -> dict:

        #Método interno encapsulado que faz a chamada estruturada para a API do Gemini.
        #Retorna um dicionário contendo a lista de questões.

        prompt_sistema = (
            "Extraia pra mim, do texto bruto da prova, todas as questões (e respectivas respostas) apenas de Língua Portuguesa, num layout jayson."
        )

        try:
            if genai:
                client = genai.Client(api_key="<Aqui fica a chave da api>")

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
        
        #Lê os PDFs da pasta informada, aplica um pré-filtro dinâmico para economizar tokens,
        #envia o conteúdo relevante ao Gemini e salva o resultado estruturado no Banco de Dados.
        
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
    def executar_extracao_questoes(pasta_origem: str, callback_interface) -> None:
        
        #Método estático que processa uma pasta de PDFs, força a estrutura de JSON estrita,
        #mapeia textos de referência/base das questões e gera o arquivo consolidado.
        
        servico_ia = GeminiService()     

        if genai:
            client = genai.Client(api_key="<Aqui fica a chave da api>")

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
    """