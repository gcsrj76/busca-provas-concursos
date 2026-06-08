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

        # LISTA ULTRA-RESTRITA: Apenas termos que são comprovadamente lixo exclusivo
        palavras_ignorar = [
            # Seus termos originais validados
            "Resultado", "Comunicado", "Retificação", "Prova Oral", 
            "Prova Prática", "Convocação", "Cronograma", "Aviso", 
            "Portaria", "Liminar", "Prova Discursiva",
            
            # Novos termos de burocracia pura extraídos do seu TXT
            "heteroidentificação", "autodeclaração", "sessão pública", 
            "julgamento dos recursos", "tutorial", "sub judice", "decisão judicial", 
            "cumprimento de sentença", "homologação", "eliminação de candidato", 
            "desistência de candidato", "formulário", "avaliação médica", 
            "exame médico", "atendimento especial", "resolução administrativa", 
            "expediente da presidência", "banca examinadora",
            
            # Termos compostos seguros (evitam bloquear palavras soltas legítimas)
            "Relação de candidatos", "Relação dos candidatos", "Relação de inscritos", "Relação nominal"
        ]
        
        # O Regex busca pelas fronteiras exatas da palavra (\b) ignorando maiúsculas/minúsculas
        padrao_ignorar = re.compile(r'\b(' + '|'.join(map(re.escape, palavras_ignorar)) + r')\b', re.IGNORECASE)

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
                
                titulo_concurso = " ".join(concurso.titulo.split())
                padrao_prefixo = r"^concurso p[úu]blico\s+(para\s+(o|a|os|as)?\s+|para\s+)?"
                titulo_concurso = re.sub(padrao_prefixo, "", titulo_concurso, flags=re.IGNORECASE).strip()

                if titulo_concurso:
                    titulo_concurso = titulo_concurso[0].upper() + titulo_concurso[1:]

                blocos_publicacao = soup.select(".field--name-field-concurso-arquivos .field__item .paragraph--type--texto-data")
                
                if not blocos_publicacao:
                    conteudo_corpo = soup.select_one(".field--name-field-concurso-arquivos, .field--name-body")
                    if conteudo_corpo:
                        blocos_publicacao = conteudo_corpo.find_all(["p", "td"])
                    else:
                        blocos_publicacao = []

                contexto_nivel1 = ""  
                contexto_nivel2 = ""  

                for item_bloco in blocos_publicacao:
                    paragrafos = item_bloco.find_all("p") if item_bloco.name not in ["p", "td"] else [item_bloco]
                    
                    for p_tag in paragrafos:
                        texto_linha = " ".join(p_tag.get_text(strip=True).split()).strip(" -:")
                        if not texto_linha:
                            continue

                        classes = p_tag.get("class", [])
                        link_ancora = p_tag.find("a")

                        if not link_ancora:
                            if "Indent1" in classes:
                                contexto_nivel2 = texto_linha
                            elif "Indent2" not in classes:
                                contexto_nivel1 = texto_linha
                                contexto_nivel2 = ""  
                            continue

                        href_arq = link_ancora.get("href")
                        if not href_arq or href_arq.startswith("#"):
                            continue

                        href_lower = href_arq.lower()
                        if "login.aspx" in href_lower or "form.aspx" in href_lower:
                            continue
                            
                        if not (href_lower.endswith('.pdf') or '.pdf?' in href_lower or 'sites/default/files' in href_lower):
                            continue

                        txt_link = " ".join(link_ancora.get_text(strip=True).split()).strip(" -:")
                        
                        if len(txt_link) > 100 or any(ignorar in txt_link.lower() for ignorar in ["clique aqui", "página inicial", "voltar", "inscrição", "inscreva-se"]):
                            continue

                        if "Indent1" not in classes and "Indent2" not in classes:
                            contexto_nivel1 = ""
                            contexto_nivel2 = ""
                        elif "Indent1" in classes and len(txt_link) > 12:
                            contexto_nivel2 = txt_link

                        encontrou_prova_neste_concurso = True
                        url_arq_completa = "https://conhecimento.fgv.br" + href_arq if href_arq.startswith("/") else href_arq

                        # == CONSTRUÇÃO DA ÁRVORE DA DESCRIÇÃO ==
                        partes_nome = [titulo_concurso]

                        if contexto_nivel1 and contexto_nivel1.lower() != titulo_concurso.lower():
                            if contexto_nivel1.lower() not in txt_link.lower():
                                partes_nome.append(contexto_nivel1)

                        if contexto_nivel2 and contexto_nivel2.lower() != contexto_nivel1.lower():
                            if contexto_nivel2.lower() not in txt_link.lower():
                                partes_nome.append(contexto_nivel2)

                        if txt_link and txt_link.lower() != contexto_nivel2.lower() and txt_link.lower() != contexto_nivel1.lower():
                            if txt_link.isdigit():
                                partes_nome.append(f"Tipo {txt_link}")
                            else:
                                partes_nome.append(txt_link)

                        descricao_completa = " - ".join(partes_nome)

                        # === FILTRAGEM PRECISA ===
                        if padrao_ignorar.search(descricao_completa):
                            continue

                        # Persistência no banco de dados
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
            txt_relatorio = "🎉 Excelente! Todos os concursos analisados possuiu provas e gabaritos cadastrados.\n"

        fim_txt = f"\n=== VARREDURA WEB CONCLUÍDA ===\nInéditas: {total_provas_descobertas} | Já existentes: {total_provas_ja_existentes}\n{txt_relatorio}"
        callback_interface("Varredura de Provas Concluída!", 1.0, fim_txt)