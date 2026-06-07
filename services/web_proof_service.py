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

                # Focamos estritamente nos blocos de arquivos do Drupal para evitar lixo e menus
                blocos_publicacao = soup.select(".field--name-field-concurso-arquivos .field__item .paragraph--type--texto-data")
                
                # Se a página não usar a estrutura de blocos nova, recorre ao contêiner geral (retrocompatibilidade)
                if not blocos_publicacao:
                    conteudo_corpo = soup.select_one(".field--name-field-concurso-arquivos, .field--name-body")
                    blocos_publicacao = conteudo_corpo.find_all("p") if conteudo_corpo else []

                # Variáveis de controle para rastreamento da árvore hierárquica
                contexto_nivel1 = ""  # Ex: Prova Objetiva
                contexto_nivel2 = ""  # Ex: Fiscal de Rendas - Manhã

                for item_bloco in blocos_publicacao:
                    # Garantimos que a varredura ocorra parágrafo por parágrafo de forma ordenada
                    paragrafos = item_bloco.find_all("p") if item_bloco.name != "p" else [item_bloco]
                    
                    for p_tag in paragrafos:
                        texto_linha = " ".join(p_tag.get_text(strip=True).split()).strip(" -:")
                        if not texto_linha:
                            continue

                        classes = p_tag.get("class", [])
                        link_ancora = p_tag.find("a")

                        # CASO 1: É uma linha de cabeçalho estrutural (Não possui link)
                        if not link_ancora:
                            if "Indent1" in classes:
                                contexto_nivel2 = texto_linha
                            elif "Indent2" not in classes:
                                contexto_nivel1 = texto_linha
                                contexto_nivel2 = ""  # Reseta o subcontexto ao mudar o bloco principal
                            continue

                        # CASO 2: A linha atual possui um link válido
                        href_arq = link_ancora.get("href")
                        if not href_arq or href_arq.startswith("#"):
                            continue

                        txt_link = " ".join(link_ancora.get_text(strip=True).split()).strip(" -:")
                        
                        # FILTRO DE SEGURANÇA CRÍTICO: Ignora links institucionais ou textos de instruções longos
                        if len(txt_link) > 45 or any(ignorar in txt_link.lower() for ignorar in ["clique aqui", "página inicial", "voltar", "inscrição"]):
                            continue

                        # Suporte a links na raiz que possuem texto descritivo próprio em vez de "Tipo X"
                        if "Indent1" in classes and len(txt_link) > 12:
                            contexto_nivel2 = txt_link
                        elif "Indent2" not in classes and "Indent1" not in classes and len(txt_link) > 12:
                            # Se for um link simples na raiz, limpa os contextos antigos para não herdar lixo anterior
                            contexto_nivel1 = ""
                            contexto_nivel2 = ""

                        encontrou_prova_neste_concurso = True
                        url_arq_completa = "https://conhecimento.fgv.br" + href_arq if href_arq.startswith("/") else href_arq

                        # == CONSTRUÇÃO DA ÁRVORE DA DESCRIÇÃO ==
                        partes_nome = [titulo_concurso]

                        if contexto_nivel1 and contexto_nivel1.lower() != titulo_concurso.lower():
                            partes_nome.append(contexto_nivel1)

                        if contexto_nivel2 and contexto_nivel2.lower() != contexto_nivel1.lower():
                            partes_nome.append(contexto_nivel2)

                        # Adiciona o texto do link se ele trouxer informação nova relevante (ex: Tipo 1)
                        if txt_link and txt_link.lower() != contexto_nivel2.lower() and txt_link.lower() != contexto_nivel1.lower():
                            if txt_link.isdigit():
                                partes_nome.append(f"Tipo {txt_link}")
                            else:
                                partes_nome.append(txt_link)

                        descricao_completa = " - ".join(partes_nome)

                        # Persistência no banco de dados utilizando a estrutura existente
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