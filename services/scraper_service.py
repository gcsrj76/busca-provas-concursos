import time
import requests
from bs4 import BeautifulSoup
from repository.concurso_repo import ConcursoRepository

class ScraperService:
    @staticmethod
    def executar_coleta(pagina_inicial, pagina_final, callback_interface):
        base_url = "https://conhecimento.fgv.br"
        url_concursos = f"{base_url}/concursos#tab-text-129-content"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        novos_links = 0

        # Limpa o banco para uma nova rodada de coletas limpa
        ConcursoRepository.limpar_banco()

        # Garante a ordem correta caso o usuário digite invertido por engano
        inicio = min(pagina_inicial, pagina_final)
        fim = max(pagina_inicial, pagina_final)
        
        # O total de páginas a processar no intervalo selecionado
        total_paginas_intervalo = (fim - inicio) + 1

        # O loop do Python é exclusivo no fim, então somamos 1
        for indice_loop, pagina in enumerate(range(inicio, fim + 1)):
            # Calcula o progresso com base em quantas páginas deste bloco já foram lidas
            progresso = (indice_loop + 1) / total_paginas_intervalo
            callback_interface(f"Lendo página {pagina} de {fim}...", progresso)
            
            try:
                # Na paginação da FGV, a página 1 costuma ser mapeada como ?page=0 ou ?page=1 dependendo da sessão,
                # mas passar o número exato da página funciona perfeitamente pelo parâmetro.
                resposta = requests.get(url_concursos, params={"page": pagina}, headers=headers, timeout=10)
                if resposta.status_code != 200:
                    callback_interface(None, None, f"⚠️ Falha ao acessar página {pagina} (Status: {resposta.status_code})\n")
                    continue
                
                soup = BeautifulSoup(resposta.text, "html.parser")
                view_content = soup.select_one(".view-concursos-realizados .view-content")
                if not view_content:
                    callback_interface(None, None, f"ℹ️ Fim dos registros ou estrutura vazia na página {pagina}.\n")
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
                callback_interface(f"Erro de conexão na página {pagina}: {e}", progresso, f">> Erro na pág {pagina}: {e}\n")
                continue

        callback_interface(f"Fim. {novos_links} novos concursos salvos.", 1.0, f"=== COLETA FINALIZADA ===\nTotal de páginas analisadas: {total_paginas_intervalo}\n")