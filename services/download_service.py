import os
import time
import requests
from repository.concurso_repo import ConcursoRepository

class DownloadService:
    @staticmethod
    def executar_downloads(pasta_destino, callback_interface):
        if not os.path.exists(pasta_destino):
            os.makedirs(pasta_destino, exist_ok=True)

        concursos = ConcursoRepository.listar_todos()
        arquivos_para_baixar = []
        for c in concursos:
            for arq in c.arquivos:
                arquivos_para_baixar.append(arq)

        total_arquivos = len(arquivos_para_baixar)
        if total_arquivos == 0:
            callback_interface("Nenhum arquivo mapeado no banco para baixar.", 1.0, "Fim.\n")
            return

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        baixados = 0

        for i, arq in enumerate(arquivos_para_baixar):
            progresso = (i + 1) / total_arquivos
            nome_limpo = "".join([c for c in arq.descricao if c.isalnum() or c in (" ", "-", "_")]).rstrip()
            nome_arquivo = f"{nome_limpo}.pdf"
            caminho_completo = os.path.join(pasta_destino, nome_arquivo)

            callback_interface(f"Baixando {i+1}/{total_arquivos}...", progresso)

            # --- NOVA LÓGICA DE VERIFICAÇÃO ---
            # Verifica tanto no banco de dados quanto no arquivo físico
            if arq.baixado and os.path.exists(caminho_completo):
                callback_interface(None, None, f"skip: {nome_arquivo} (já consta como baixado no banco e local)\n")
                baixados += 1
                continue
            
            # Se sumiu da pasta local mas está no banco, ou vice-versa, tentará baixar de novo por segurança
            try:
                resposta = requests.get(arq.url_arquivo, headers=headers, timeout=15)
                if resposta.status_code == 200:
                    with open(caminho_completo, "wb") as f:
                        f.write(resposta.content)
                    
                    # --- ATUALIZAÇÃO NO BANCO ---
                    ConcursoRepository.atualizar_status_download(arq.id, True)
                    
                    callback_interface(None, None, f"📥 [BAIXADO] {nome_arquivo}\n")
                    baixados += 1
                else:
                    callback_interface(None, None, f"❌ [ERRO {resposta.status_code}] {nome_arquivo}\n")
                time.sleep(0.5)
            except Exception as e:
                callback_interface(None, None, f"⚠️ [FALHA] {nome_arquivo}: {e}\n")

        callback_interface("Downloads finalizados!", 1.0, f"\n=== DOWNLOADS TERMINADOS ===\nSucesso em {baixados} de {total_arquivos}.\n")