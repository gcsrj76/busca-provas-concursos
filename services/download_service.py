import os
import time
import requests
import io
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from pypdf import PdfReader
from repository.concurso_repo import ConcursoRepository




class DownloadService:
    @staticmethod
    def executar_downloads(pasta_destino, callback_interface, evento_pausa=None):

        # Utilizar apenas quando for necessário limpar marcações indevidas ou feitas em teste
        # ConcursoRepository.resetar_status_downloads()

        if not os.path.exists(pasta_destino):
            os.makedirs(pasta_destino, exist_ok=True)

        # Busca no repositório apenas os registros com status pendente
        arquivos_para_baixar = ConcursoRepository.obter_arquivos_pendentes()

        total_arquivos = len(arquivos_para_baixar)
        if total_arquivos == 0:
            callback_interface("Todos os arquivos já foram baixados ou não há registros.", 1.0, "Fim.\n")
            return

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        baixados = 0
        ignorados = 0

        for i, arq in enumerate(arquivos_para_baixar):
            # --- CONTROLE DE PAUSA ---
            if evento_pausa is not None:
                evento_pausa.wait()

            progresso = (i + 1) / total_arquivos            
            callback_interface(f"Processando {i+1}/{total_arquivos}...", progresso)

            desc_lower = arq.descricao.lower()
            subpasta_nome = ""

            # 1. Verificação Sequencial por Nome (Hierarquia Padrão)
            if "edital" in desc_lower:
                subpasta_nome = "Edital"
            elif "gabarito" in desc_lower:
                subpasta_nome = "Gabarito"
            elif "prova" in desc_lower:
                subpasta_nome = "Prova"
            
            # 2. Se não bateu pelo nome, faz download preventivo para analisar o conteúdo do PDF
            if not subpasta_nome:
                try:
                    resposta_analise = requests.get(
                        arq.url_arquivo, 
                        headers=headers, 
                        timeout=15, 
                        verify=False, 
                        allow_redirects=True
                    )
                    
                    if resposta_analise.status_code == 200:
                        # Abre o PDF diretamente da memória (Bytes)
                        pdf_em_memoria = io.BytesIO(resposta_analise.content)
                        leitor_pdf = PdfReader(pdf_em_memoria)
                        
                        # Garante que o PDF possui páginas antes de inspecionar
                        if len(leitor_pdf.pages) > 0:
                            primeira_pagina = leitor_pdf.pages[0]
                            texto_primeira_pag = primeira_pagina.extract_text() or ""
                            
                            # --- SITUAÇÃO 1: TODOS os termos obrigatórios presentes ---
                            termos_situacao_1 = ["SUA PROVA", "TEMPO", "NÃO SERÁ PERMITIDO", "INFORMAÇÕES GERAIS"]
                            validou_situacao_1 = all(termo in texto_primeira_pag for termo in termos_situacao_1)
                            
                            # --- SITUAÇÃO 2: Pelo menos UM dos termos possíveis presente ---
                            termos_situacao_2 = ["Informações Gerais", "Prova Escrita Objetiva", "Prova Escrita", "Prova Objetiva"]
                            validou_situacao_2 = any(termo in texto_primeira_pag for termo in termos_situacao_2)
                            
                            if validou_situacao_1 or validou_situacao_2:
                                subpasta_nome = "Prova"
                                
                                # Como já temos o conteúdo baixado com sucesso, vamos reaproveitá-lo 
                                # salvando diretamente no fluxo atual para economizar banda e tempo.
                                conteudo_pdf_validado = resposta_analise.content
                            else:
                                ignorados += 1
                                continue
                        else:
                            ignorados += 1
                            continue
                    else:
                        callback_interface(None, None, f"❌ [FALHA NA ANÁLISE - STATUS {resposta_analise.status_code}] {arq.descricao}\n")
                        continue
                except Exception as erro_pdf:
                    callback_interface(None, None, f"⚠️ [ERRO AO ANALISAR PDF] {arq.descricao}: {erro_pdf}\n")
                    continue
            else:
                # Se caiu aqui, o arquivo foi identificado previamente pelo nome. 
                # Definimos a variável como None para que o script faça o download normal no bloco 4.
                conteudo_pdf_validado = None

            # 3. Composição do Nome do Arquivo utilizando o Concurso Pai
            concurso_pai = getattr(arq, 'concurso', None)
            num_pagina = concurso_pai.pagina_coleta if concurso_pai else 0
            num_ordem = concurso_pai.ordem_coleta if concurso_pai else 0

            nome_limpo = "".join([c for c in arq.descricao if c.isalnum() or c in (" ", "-", "_")]).rstrip()
            nome_arquivo = f"{num_pagina:02d}{num_ordem:04d} - {nome_limpo}.pdf"
            caminho_completo = os.path.join(pasta_destino, subpasta_nome, nome_arquivo)
            
            # Garante que a subpasta alvo existe
            os.makedirs(os.path.dirname(caminho_completo), exist_ok=True)
            
            # 4. Execução/Escrita do Download
            try:
                # Se o arquivo foi validado por análise interna, o conteúdo já está na memória
                if conteudo_pdf_validado is not None:
                    with open(caminho_completo, "wb") as f:
                        f.write(conteudo_pdf_validado)
                    ConcursoRepository.atualizar_status_download(arq.id, True)
                    callback_interface(None, None, f"📥 [{subpasta_nome.upper()} - VIA CONTEÚDO] {nome_arquivo}\n")
                    baixados += 1
                else:
                    # Download tradicional (Edital, Gabarito ou Prova identificados pelo nome)
                    resposta = requests.get(
                        arq.url_arquivo, 
                        headers=headers, 
                        timeout=15, 
                        verify=False, 
                        allow_redirects=True
                    )
                    
                    if resposta.status_code == 200:
                        with open(caminho_completo, "wb") as f:
                            f.write(resposta.content)
                        
                        ConcursoRepository.atualizar_status_download(arq.id, True)
                        callback_interface(None, None, f"📥 [{subpasta_nome.upper()}] {nome_arquivo}\n")
                        baixados += 1
                    else:
                        callback_interface(None, None, f"❌ [ERRO {resposta.status_code}] {nome_arquivo}\n")
                
                time.sleep(0.5)
            except Exception as e:
                callback_interface(None, None, f"⚠️ [FALHA] {nome_arquivo}: {e}\n")

        resumo_final = (
            f"\n=== DOWNLOADS TERMINADOS ===\n"
            f"Sucesso: {baixados}\n"
            f"Ignorados (sem correspondência): {ignorados}\n"
            f"Total analisado: {total_arquivos}\n"
        )
        callback_interface("Downloads finalizados!", 1.0, resumo_final)