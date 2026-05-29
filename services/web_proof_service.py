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

        # Lista para armazenar os concursos que não tiveram nenhuma prova localizada
        concursos_sem_prova = []

        # Padrão Regex Expandido e Flexível
        padrao_prova_objetiva = re.compile(r"Provas?(\s+(Escrita\s+)?Objetiva)?", re.IGNORECASE)

        #Situações possíveis:
        #Provas
        #Prova
        #Provas - 15/10/2012
        #Prova Objetiva
        #Prova Escrita Objetiva
        #Provas Escritas Objetivas - 2018           

        for i, concurso in enumerate(concursos):
            porcentagem = (i + 1) / total_concursos
            callback_interface(f"Verificando {i+1}/{total_concursos} ({concurso.titulo[:25]}...)", porcentagem)

            # Flag interna para verificar se o concurso atual possui alguma prova na página
            encontrou_prova_neste_concurso = False

            try:
                resposta = requests.get(concurso.url, headers=headers, timeout=10)
                if resposta.status_code != 200:
                    # Se der erro de conexão/status, consideramos que nenhuma prova foi extraída dele
                    concursos_sem_prova.append((concurso.titulo, concurso.url))
                    continue

                soup = BeautifulSoup(resposta.text, "lxml")
                tabela = soup.select_one("table.table")                
                if not tabela:
                    concursos_sem_prova.append((concurso.titulo, concurso.url))
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

                        if linhas_texto and padrao_prova_objetiva.search(linhas_texto[0]):
                            nivel_atual = ""
                            cargo_atual = ""

                            for elemento in celula.find_all(recursive=True):
                                if elemento.name == "p":
                                    if elemento.find("a"): 
                                        continue
                                    txt_p = " ".join(elemento.get_text(strip=True).split())
                                    
                                    if not txt_p or padrao_prova_objetiva.search(txt_p): 
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
                                        # Marcar que a estrutura continha links de arquivos válidos
                                        encontrou_prova_neste_concurso = True
                                        
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
                
                # Se passou pela tabela inteira e a flag continuou False, adiciona ao relatório
                if not encontrou_prova_neste_concurso:
                    concursos_sem_prova.append((concurso.titulo, concurso.url))

                time.sleep(1.2)
            except Exception as e:
                concursos_sem_prova.append((concurso.titulo, concurso.url))
                callback_interface(None, None, f"⚠️ Erro ao acessar {concurso.url}: {e}\n")
                continue

        # == GERAÇÃO DO RELATÓRIO TXT ==
        txt_relatorio = ""
        if concursos_sem_prova:
            try:
                with open("concursos_sem_provas.txt", "w", encoding="utf-8") as f:
                    f.write("=== CONCURSOS SEM PROVAS ENCONTRADAS ===\n")
                    f.write(f"Gerado em: {time.strftime('%d/%m/%Y %H:%M:%S')}\n")
                    f.write(f"Total de concursos sem prova: {len(concursos_sem_prova)}\n")
                    f.write("-" * 50 + "\n\n")
                    for titulo, url in concursos_sem_prova:
                        f.write(f"🏆 Concurso: {titulo}\n")
                        f.write(f"🔗 Link: {url}\n")
                        f.write("-" * 50 + "\n")
                txt_relatorio = f"📋 Relatório gerado com sucesso: 'concursos_sem_provas.txt' ({len(concursos_sem_prova)} listados)\n"
            except Exception as error_file:
                txt_relatorio = f"⚠️ Falha ao salvar arquivo txt de relatório: {error_file}\n"
        else:
            txt_relatorio = "🎉 Excelente! Todos os concursos analisados possuíam provas cadastradas.\n"

        fim_txt = f"\n=== VARREDURA WEB CONCLUÍDA ===\nInéditas: {total_provas_descobertas} | Já existentes: {total_provas_ja_existentes}\n{txt_relatorio}"
        callback_interface("Varredura de Provas Concluída!", 1.0, fim_txt)