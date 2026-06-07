import os
import time
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from repository.concurso_repo import ConcursoRepository

class DownloadService:
    @staticmethod
    def executar_downloads(pasta_destino, callback_interface, evento_pausa=None):

        #Utilizar apenas quando for necessário limpar marcações indevidas ou feitas em teste
        ConcursoRepository.resetar_status_downloads()

        if not os.path.exists(pasta_destino):
            os.makedirs(pasta_destino, exist_ok=True)

        # Busca no repositório apenas os registros com status pendente (carregados via joinedload)
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

            # 1. Verificação Sequencial da Hierarquia de Categorias
            if "edital" in desc_lower:
                subpasta_nome = "Edital"
            elif "gabarito" in desc_lower:
                subpasta_nome = "Gabarito"
            elif "prova" in desc_lower:
                subpasta_nome = "Prova"
            else:
                # Se não contiver nenhum dos 3 termos descritos, o arquivo é ignorado
                ignorados += 1
                continue

            # Cria a subpasta correspondente (Edital, Gabarito ou Prova) caso ela não exista
            caminho_subpasta = os.path.join(pasta_destino, subpasta_nome)
            if not os.path.exists(caminho_subpasta):
                os.makedirs(caminho_subpasta, exist_ok=True)

            # 2. Composição do Nome do Arquivo utilizando o Concurso Pai
            concurso_pai = getattr(arq, 'concurso', None)
            
            # Utiliza os campos mapeados no repositório: pagina_coleta e ordem_coleta
            num_pagina = concurso_pai.pagina_coleta if concurso_pai else 0
            num_ordem = concurso_pai.ordem_coleta if concurso_pai else 0

            nome_limpo = "".join([c for c in arq.descricao if c.isalnum() or c in (" ", "-", "_")]).rstrip()
            
            # Formatação solicitada: página (2 dígitos) + ordem (4 dígitos) + descrição + .pdf
            nome_arquivo = f"{num_pagina:02d}{num_ordem:04d} - {nome_limpo}.pdf"
            caminho_completo = os.path.join(caminho_subpasta, nome_arquivo)
            
            # 3. Execução estável do Download
            try:
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
                    
                    # Registra o sucesso na tabela de arquivos_provas marcando como baixado
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
   