import time
import requests
from bs4 import BeautifulSoup
from repository.concurso_repo import ConcursoRepository

class ScraperService:
    @staticmethod
    def executar_coleta(max_paginas, callback_interface):
        base_url = "https://conhecimento.fgv.br"
        url_concursos = f"{base_url}/concursos#tab-text-129-content"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        novos_links = 0

        ConcursoRepository.limpar_banco()

        for pagina in range(0, max_paginas):
            progresso = (pagina + 1) / max_paginas
            callback_interface(f"Lendo página {pagina + 1} de {max_paginas}...", progresso)
            
            try:
                resposta = requests.get(url_concursos, params={"page": pagina}, headers=headers, timeout=10)
                if resposta.status_code != 200:
                    break
                
                soup = BeautifulSoup(resposta.text, "html.parser")
                view_content = soup.select_one(".view-concursos-realizados .view-content")
                if not view_content:
                    break
                
                for link in view_content.find_all("a"):
                    href = link.get("href")
                    titulo = link.get_text(strip=True)
                    if href:
                        titulo_lower = titulo.lower()
                        if "concurso público" not in titulo_lower:
                            continue
                        
                        url_completa = base_url + href if href.startswith("/") else href
                        foi_salvo = ConcursoRepository.salvar_link(url=url_completa, titulo=titulo)
                        
                        msg = f"[NOVO] {titulo}\n🔗 {url_completa}\n\n" if foi_salvo else f"[JÁ EXISTE] {titulo}\n\n"
                        if foi_salvo: 
                            novos_links += 1
                        callback_interface(None, None, msg)
                time.sleep(1.0)
            except Exception as e:
                callback_interface(f"Erro de conexão: {e}", 1.0, f">> Erro fatal: {e}\n")
                break

        callback_interface(f"Fim. {novos_links} novos concursos salvos.", 1.0, "=== COLETA FINALIZADA ===\n")