import time
import re
import requests
from bs4 import BeautifulSoup
from repository.concurso_repo import ConcursoRepository

class WebProofService:
    @staticmethod
    def varrer_pdfs_web(callback_interface):
        concursos = ConcursoRepository.listar_todos()
        total_concursos = len(concursos)

        if total_concursos == 0:
            callback_interface("Banco de dados vazio! Realize a coleta primeiro.", 0, "Nenhum concurso localizado.\n")
            return

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        total_provas_descobertas = 0
        total_provas_ja_existentes = 0
        concursos_sem_prova = []

        for i, concurso in enumerate(concursos):
            porcentagem = (i + 1) / total_concursos
            callback_interface(f"Verificando {i+1}/{total_concursos} ({concurso.titulo[:25]}...)", porcentagem)

            encontrou_prova_neste_concurso = False

            try:
                resposta = requests.get(concurso.url, headers=headers, timeout=10)
                if resposta.status_code != 200:
                    concursos_sem_prova.append((concurso.titulo, concurso.url))
                    continue

                soup = BeautifulSoup(resposta.text, "lxml")
                
                # Normalização do título do concurso para a composição da descrição
                titulo_concurso = " ".join(concurso.titulo.split())
                padrao_prefixo = r"^concurso p[úu]blico\s+(para\s+(o|a|os|as)?\s+|para\s+)?"
                titulo_concurso = re.sub(padrao_prefixo, "", titulo_concurso, flags=re.IGNORECASE).strip()

                if titulo_concurso:
                    titulo_concurso = titulo_concurso[0].upper() + titulo_concurso[1:]

                # Localiza todos os blocos de itens/arquivos baseados na estrutura real do HTML (Drupal)
                blocos_publicacao = soup.select(".field--name-field-concurso-arquivos .field__item .paragraph--type--texto-data")
                
                # Fallback caso a estrutura mude ou venha de tabelas antigas
                if not blocos_publicacao:
                    blocos_publicacao = soup.find_all("tr")

                for bloco in blocos_publicacao:
                    # Captura todo o texto estrutural do bloco para identificar se trata-se de Prova/Gabarito/Caderno
                    texto_completo_bloco = " ".join(bloco.get_text(" ", strip=True).split())
                    
                    # Filtro amplo: Processa o bloco se houver indício de provas, cadernos ou gabaritos
                    if not any(termo in texto_completo_bloco.lower() for termo in ["prova", "gabarito", "caderno", "tipo"]):
                        continue

                    # Extrai o texto limpo do parágrafo indicador (Hierarquia/Cargo/Turno)
                    # Ele serve como o contexto que antecede os links de "Tipo X"
                    paragrafo_texto = bloco.find("p")
                    contexto_hierarquia = ""
                    if paragrafo_texto:
                        # Remove os textos dos links internos para pegar apenas o título mãe da linha
                        clone_p = BeautifulSoup(str(paragrafo_texto), "lxml")
                        for a_tag in clone_p.find_all("a"):
                            a_tag.decompose()
                        contexto_hierarquia = " ".join(clone_p.get_text(" ", strip=True).split()).strip(" -:")

                    # Se não achou texto no <p> purificado, usa o começo do bloco como cabeçalho explicativo
                    if not contexto_hierarquia and texto_completo_bloco:
                        contexto_hierarquia = texto_completo_bloco.split("Tipo")[0].strip(" -:")

                    # Encontra todos os links de download válidos dentro deste bloco específico
                    links_do_bloco = bloco.find_all("a")
                    for ancora in links_do_bloco:
                        href_arq = ancora.get("href")
                        if not href_arq or href_arq.startswith("#"):
                            continue
                        
                        txt_link = " ".join(ancora.get_text(strip=True).split())
                        
                        # Evita links institucionais ou de navegação comuns mapeados por engano
                        if any(ignorar in txt_link.lower() for ignorar in ["inscrição", "página inicial", "voltar"]):
                            continue

                        encontrou_prova_neste_concurso = True
                        url_arq_completa = "https://conhecimento.fgv.br" + href_arq if href_arq.startswith("/") else href_arq
                        
                        # Construção precisa da árvore de nomes: [Concurso] - [Hierarquia/Turno/Cargo] - [Tipo/Link]
                        partes_nome = [titulo_concurso]
                        
                        if contexto_hierarquia and contexto_hierarquia.lower() != titulo_concurso.lower():
                            partes_nome.append(contexto_hierarquia)
                            
                        if txt_link and txt_link.lower() != contexto_hierarquia.lower():
                            # Se o link for apenas o número do Tipo, deixamos explícito para clareza
                            if txt_link.isdigit():
                                partes_nome.append(f"Tipo {txt_link}")
                            else:
                                partes_nome.append(txt_link)

                        # Garante a união limpa sem termos duplicados adjacentes
                        descricao_completa = " - ".join(partes_nome)
                        
                        # Executa o salvamento na tabela 'arquivos' via relacionamento existente
                        foi_salvo = ConcursoRepository.salvar_arquivo_prova(concurso.id, descricao_completa, url_arq_completa)

                        if foi_salvo:
                            total_provas_descobertas += 1
                            print_msg = f"✨ [DOC NOVO] {descricao_completa}\n🔗 {url_arq_completa}\n\n"
                        else:
                            total_provas_ja_existentes += 1
                            print_msg = f"📚 [HISTÓRICO BASE] {descricao_completa}\n\n"
                        
                        callback_interface(None, None, print_msg)
                            
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
                    f.write("=== CONCURSOS SEM ARQUIVOS DE PROVAS ENCONTRADOS ===\n")
                    f.write(f"Gerado em: {time.strftime('%d/%m/%Y %H:%M:%S')}\n")
                    f.write(f"Total de concursos sem registros capturados: {len(concursos_sem_prova)}\n")
                    f.write("-" * 50 + "\n\n")
                    for titulo, url in concursos_sem_prova:
                        f.write(f"🏆 Concurso: {titulo}\n")
                        f.write(f"🔗 Link: {url}\n")
                        f.write("-" * 50 + "\n")
                txt_relatorio = f"📋 Relatório gerado com sucesso: 'concursos_sem_provas.txt' ({len(concursos_sem_prova)} listados)\n"
            except Exception as error_file:
                txt_relatorio = f"⚠️ Falha ao salvar arquivo txt de relatório: {error_file}\n"
        else:
            txt_relatorio = "🎉 Excelente! Todos os concursos analisados possuíam provas e gabaritos cadastrados.\n"

        fim_txt = f"\n=== VARREDURA WEB CONCLUÍDA ===\nInéditas: {total_provas_descobertas} | Já existentes: {total_provas_ja_existentes}\n{txt_relatorio}"
        callback_interface("Varredura de Provas Concluída!", 1.0, fim_txt)