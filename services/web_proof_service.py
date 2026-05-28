import time
import re
import requests
from bs4 import BeautifulSoup
from repository.concurso_repo import ConcursoRepository

class WebProofService:
    @staticmethod
    def varrer_provas_web(callback_interface):
        concursos = ConcursoRepository.listar_todos()
        total_concursos = len(concursos)

        if total_concursos == 0:
            callback_interface("Banco de dados vazio! Realize a coleta primeiro.", 0, "Nenhum concurso localizado.\n")
            return

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        total_provas_descobertas = 0
        total_provas_ja_existentes = 0

        for i, concurso in enumerate(concursos):
            porcentagem = (i + 1) / total_concursos
            callback_interface(f"Verificando {i+1}/{total_concursos} ({concurso.titulo[:25]}...)", porcentagem)

            try:
                resposta = requests.get(concurso.url, headers=headers, timeout=10)
                if resposta.status_code != 200:
                    continue

                soup = BeautifulSoup(resposta.text, "lxml")
                tabela = soup.select_one("table.table")                
                if not tabela:
                    continue

                titulo_concurso = " ".join(concurso.titulo.split())
                padrao_prefixo = r"^concurso p[úu]blico\s+(para\s+(o|a|os|as)?\s+|para\s+)?"
                titulo_concurso = re.sub(padrao_prefixo, "", titulo_concurso, flags=re.IGNORECASE).strip()

                if titulo_concurso:
                    titulo_concurso = titulo_concurso[0].upper() + titulo_concurso[1:]

                linhas = tabela.find_all("tr")
                for linha in list(linhas):
                    celulas = linha.find_all("td")
                    for celula in celulas:
                        linhas_texto = [t.strip() for t in celula.get_text("\n").split("\n") if t.strip()]

                        if linhas_texto and linhas_texto[0] == "Prova Objetiva":
                            nivel_atual = ""
                            cargo_atual = ""

                            for elemento in celula.find_all(recursive=True):
                                if elemento.name == "p":
                                    if elemento.find("a"): 
                                        continue
                                    txt_p = " ".join(elemento.get_text(strip=True).split())
                                    if not txt_p or txt_p == "Prova Objetiva": 
                                        continue
                                    if "Nível" in txt_p or "Escolaridade" in txt_p:
                                        nivel_atual = txt_p
                                        cargo_atual = ""
                                    else:
                                        cargo_atual = txt_p

                                elif elemento.name == "a":
                                    href_arq = elemento.get("href")
                                    txt_a = " ".join(elemento.get_text(strip=True).split())
                                    if href_arq:
                                        url_arq_completa = "https://conhecimento.fgv.br" + href_arq if href_arq.startswith("/") else href_arq
                                        partes_nome = [titulo_concurso]
                                        if nivel_atual: 
                                            partes_nome.append(nivel_atual)
                                        if cargo_atual: 
                                            partes_nome.append(cargo_atual)
                                        if txt_a and txt_a not in cargo_atual and txt_a not in nivel_atual:
                                            partes_nome.append(txt_a)
                                            
                                        descricao_completa = " - ".join(partes_nome)
                                        foi_salvo = ConcursoRepository.salvar_arquivo_prova(concurso.id, descricao_completa, url_arq_completa)

                                        if foi_salvo:
                                            total_provas_descobertas += 1
                                            print_msg = f"✨ [PROVA NOVA] {descricao_completa}\n🔗 {url_arq_completa}\n\n"
                                        else:
                                            total_provas_ja_existentes += 1
                                            print_msg = f"📚 [HISTÓRICO BASE] {descricao_completa}\n\n"
                                        
                                        callback_interface(None, None, print_msg)
                time.sleep(1.2)
            except Exception as e:
                callback_interface(None, None, f"⚠️ Erro ao acessar {concurso.url}: {e}\n")
                continue

        fim_txt = f"\n=== VARREDURA WEB CONCLUÍDA ===\nInéditas: {total_provas_descobertas} | Já existentes: {total_provas_ja_existentes}\n"
        callback_interface("Varredura de Provas Concluída!", 1.0, fim_txt)