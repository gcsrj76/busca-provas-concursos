import os
import time
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from repository.concurso_repo import ConcursoRepository

class DownloadService:
    @staticmethod
    def executar_downloads(pasta_destino, callback_interface, evento_pausa=None):
        if not os.path.exists(pasta_destino):
            os.makedirs(pasta_destino, exist_ok=True)

        # OTIMIZAÇÃO: Busca no repositório apenas o que de fato precisa ser baixado
        arquivos_para_baixar = ConcursoRepository.obter_arquivos_pendentes()

        total_arquivos = len(arquivos_para_baixar)
        if total_arquivos == 0:
            callback_interface("Todos os arquivos já foram baixados ou não há registros.", 1.0, "Fim.\n")
            return

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        baixados = 0

        prefixo_numeral = 0

        for i, arq in enumerate(arquivos_para_baixar):
            # --- CONTROLE DE PAUSA ---
            if evento_pausa is not None:
                evento_pausa.wait()

            prefixo_numeral = prefixo_numeral + 1

            progresso = (i + 1) / total_arquivos            

            nome_limpo = "".join([c for c in arq.descricao if c.isalnum() or c in (" ", "-", "_")]).rstrip()
            nome_arquivo = f"{prefixo_numeral:04d} - {nome_limpo}.pdf"
            caminho_completo = os.path.join(pasta_destino, nome_arquivo)

            callback_interface(f"Baixando {i+1}/{total_arquivos}...", progresso)
            
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
                    
                    # Atualiza o banco marcando como baixado
                    ConcursoRepository.atualizar_status_download(arq.id, True)
                    callback_interface(None, None, f"📥 [BAIXADO] {nome_arquivo}\n")
                    baixados += 1
                else:
                    callback_interface(None, None, f"❌ [ERRO {resposta.status_code}] {nome_arquivo}\n")
                
                time.sleep(0.5)
            except Exception as e:
                callback_interface(None, None, f"⚠️ [FALHA] {nome_arquivo}: {e}\n")

        callback_interface("Downloads finalizados!", 1.0, f"\n=== DOWNLOADS TERMINADOS ===\nSucesso em {baixados} de {total_arquivos} pendentes.\n")