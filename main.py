import threading
import time
import tkinter as tk
import re  # Importado para fazer a remoção de prefixo inteligente
from bs4 import BeautifulSoup
import customtkinter as ctk
from database import inicializar_banco
from repository import ConcursoRepository
import requests
# CORRIGIDO: Removido o ponto (.) para evitar o erro de pacote pai conhecido
from janela_provas import JanelaResultadosProvas

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class ScraperApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Coletor Avançado FGV - Pro")
        self.geometry("800x650")

        # Atributo para guardar a referência da janela secundária
        self.janela_provas = None

        # --- TÍTULO ---
        self.lbl_titulo = ctk.CTkLabel(
            self, text="Monitor de Concursos e Provas FGV", font=("Arial", 18, "bold")
        )
        self.lbl_titulo.pack(pady=15)

        # --- FRAME DE CONFIGURAÇÃO ---
        self.frame_config = ctk.CTkFrame(self)
        self.frame_config.pack(padx=20, pady=10, fill="x")

        self.lbl_paginas = ctk.CTkLabel(self.frame_config, text="Páginas para varrer:")
        self.lbl_paginas.pack(side="left", padx=10, pady=10)

        self.txt_paginas = ctk.CTkEntry(self.frame_config, width=60)
        self.txt_paginas.insert(0, "1")
        self.txt_paginas.pack(side="left", padx=5, pady=10)

        # --- CONTROLADORES DE AÇÃO ---
        self.frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_botoes.pack(pady=5)

        self.btn_iniciar = ctk.CTkButton(
            self.frame_botoes, text="1. Coletar Concursos", command=self.disparar_coleta
        )
        self.btn_iniciar.pack(side="left", padx=10)

        self.btn_verificar = ctk.CTkButton(
            self.frame_botoes,
            text="2. Verificar Provas Objetivas",
            command=self.disparar_verificacao,
            fg_color="#2b8a3e",
            hover_color="#237032",
        )
        self.btn_verificar.pack(side="left", padx=10)

        # --- STATUS E PROGRESSO ---
        self.lbl_status = ctk.CTkLabel(
            self, text="Status: Pronto.", font=("Arial", 11, "italic")
        )
        self.lbl_status.pack(pady=2)

        self.progresso = ctk.CTkProgressBar(self, width=500)
        self.progresso.set(0)
        self.progresso.pack(pady=5)

        # --- ÁREA DE TEXTO PRINCIPAL ---
        self.txt_resultados = ctk.CTkTextbox(self, width=750, height=380)
        self.txt_resultados.pack(padx=20, pady=10, fill="both", expand=True)

        # Carrega o histórico salvo no banco assim que a interface termina de abrir
        self.carregar_historico_banco()

    def carregar_historico_banco(self):
        concursos_salvos = ConcursoRepository.listar_todos()
        
        if concursos_salvos:
            self.txt_resultados.insert(tk.END, "=== HISTÓRICO DE CONCURSOS CARREGADO ===\n\n")
            for c in concursos_salvos:
                exibicao = f"🏛️ {c.titulo}\n🔗 {c.url}\n\n"
                self.txt_resultados.insert(tk.END, exibicao)
            
            self.lbl_status.configure(
                text=f"Status: Pronto. {len(concursos_salvos)} concursos carregados do histórico.",
                text_color=("black", "white")
            )
            self.txt_resultados.see("1.0")
        else:
            self.lbl_status.configure(text="Status: Banco de dados vazio. Pronto para iniciar primeira coleta.")

    def travar_botoes(self):
        self.btn_iniciar.configure(state="disabled")
        self.btn_verificar.configure(state="disabled")

    def liberar_botoes(self):
        self.btn_iniciar.configure(state="normal")
        self.btn_verificar.configure(state="normal")

    def atualizar_interface_safe(
        self, texto_status, valor_progresso, exibicao_texto=None, para_janela_provas=False
    ):
        self.lbl_status.configure(text=texto_status)
        self.progresso.set(valor_progresso)
        
        if exibicao_texto:
            if para_janela_provas and self.janela_provas and self.janela_provas.winfo_exists():
                self.janela_provas.adicionar_texto(exibicao_texto)
            else:
                self.txt_resultados.insert(tk.END, exibicao_texto)
                self.txt_resultados.see(tk.END)

    # --- LÓGICA DA ETAPA 1 (COLETA DE CONCURSOS WEB) ---
    def disparar_coleta(self):
        try:
            max_paginas = int(self.txt_paginas.get())
        except ValueError:
            self.lbl_status.configure(text="Erro! Digite um número válido.", text_color="red")
            return

        self.travar_botoes()
        self.txt_resultados.delete("1.0", tk.END)
        ConcursoRepository.limpar_banco()
        self.lbl_status.configure(text="Status: Base limpa. Iniciando nova coleta...")

        threading.Thread(
            target=self.executar_scraping, args=(max_paginas,), daemon=True
        ).start()

    def executar_scraping(self, max_paginas):
        base_url = "https://conhecimento.fgv.br"
        url_concursos = f"{base_url}/concursos#tab-text-129-content"
  
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        novos_links = 0

        for pagina in range(0, max_paginas):
            progresso_calc = (pagina + 1) / max_paginas
            status_msg = f"Lendo página {pagina + 1} de {max_paginas}..."
            self.after(0, self.atualizar_interface_safe, status_msg, progresso_calc)
            
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
                        # --- ABORDAGEM RESTRITIVA SEGURA CRITÉRIO CONCURSOS ---
                        titulo_lower = titulo.lower()
                        if "concurso público" not in titulo_lower:
                            continue
                        
                        url_completa = base_url + href if href.startswith("/") else href
                        foi_salvo = ConcursoRepository.salvar_link(url=url_completa, titulo=titulo)
                        msg = f"[NOVO] {titulo}\n🔗 {url_completa}\n\n" if foi_salvo else f"[JÁ EXISTE] {titulo}\n\n"
                        if foi_salvo: novos_links += 1
                        self.after(0, self.atualizar_interface_safe, status_msg, progresso_calc, msg)
                time.sleep(1.0)
            except Exception as e:
                self.after(0, self.atualizar_interface_safe, "Erro de conexão.", 1.0, f">> Erro: {e}\n")
                break

        self.after(0, self.atualizar_interface_safe, f"Fim. {novos_links} novos concursos salvos.", 1.0)
        self.after(0, self.liberar_botoes)

    # --- LÓGICA DA ETAPA 2 (VERIFICAÇÃO DE PROVAS) ---
    def disparar_verificacao(self):
        self.travar_botoes()

        if self.janela_provas is None or not self.janela_provas.winfo_exists():
            self.janela_provas = JanelaResultadosProvas(
                self, "=== INICIANDO VARREDURA DE PROVAS WEB (FGV) ===\n\n"
            )
        else:
            self.janela_provas.txt_provas.delete("1.0", tk.END)
            self.janela_provas.adicionar_texto("=== REINICIALIZANDO VARREDURA WEB (FGV) ===\n\n")
            self.janela_provas.lift()
            self.janela_provas.focus_force()

        threading.Thread(
            target=self.executar_verificacao_provas,
            daemon=True
        ).start()

#
#    def iniciar_processamento_arquivos(self, pasta, termo):
#        if not pasta:
#            self.janela_provas.adicionar_texto("⚠️ Por favor, selecione uma pasta antes de processar.\n")
#            return
#
#        self.janela_provas.btn_processar.configure(state="disabled")
#
#        threading.Thread(
#            target=self.janela_provas.executar_busca_local,
#            args=(pasta, termo),
#            daemon=True,
#        ).start()

    def executar_verificacao_provas(self):
        concursos = ConcursoRepository.listar_todos()
        total_concursos = len(concursos)

        if total_concursos == 0:
            self.after(
                0,
                self.atualizar_interface_safe,
                "Banco de dados vazio! Execute a Coleta primeiro.",
                0,
                "Nenhum concurso no banco para verificar.\n",
                True
            )
            self.after(0, self.liberar_botoes)
            return

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }
        total_provas_descobertas = 0
        total_provas_ja_existentes = 0

        for i, concurso in enumerate(concursos):
            porcentagem = (i + 1) / total_concursos
            msg_status = f"Verificando provas: {i+1}/{total_concursos} ({concurso.titulo[:30]}...)"
            self.after(0, self.atualizar_interface_safe, msg_status, porcentagem)

            try:
                resposta = requests.get(concurso.url, headers=headers, timeout=10)
                if resposta.status_code != 200:
                    continue

                soup = BeautifulSoup(resposta.text, "lxml")
                tabela = soup.select_one("table.table")                

                if not tabela:
                    continue

                # Normaliza o título do concurso removendo lixos de espaços e quebras
                titulo_concurso = " ".join(concurso.titulo.split())

                # --- CORREÇÃO DO PREFIXO COM REGEX (CASE INSENSITIVE) ---
                # Remove "Concurso Público para o/a/os/as" ou apenas "Concurso Público" independente de maiúsculas/minúsculas
                #padrao_prefixo = r"^concurso p[úu]blico para o[sa]?\s+|^concurso p[úu]blico para\s+|^concurso p[úu]blico\s+"
                #titulo_concurso = re.sub(padrao_prefixo, "", titulo_concurso, flags=re.IGNORECASE).strip()

                padrao_prefixo = r"^concurso p[úu]blico\s+(para\s+(o|a|os|as)?\s+|para\s+)?"
                titulo_concurso = re.sub(padrao_prefixo, "", titulo_concurso, flags=re.IGNORECASE).strip()                

                # Garante que a primeira letra remanescente fique em maiúscula para manter a elegância
                if titulo_concurso:
                    titulo_concurso = titulo_concurso[0].upper() + titulo_concurso[1:]

                linhas = tabela.find_all("tr")
                for linha in list(linhas):
                    celulas = linha.find_all("td")
                    for celula in celulas:
                        linhas_texto = [
                            t.strip() for t in celula.get_text("\n").split("\n") if t.strip()
                        ]

                        if linhas_texto and linhas_texto[0] == "Prova Objetiva":
                            
                            # MEMÓRIA EM CASCATA DA ESTRUTURA
                            nivel_atual = ""
                            cargo_atual = ""

                            # Varremos as tags filhas de bloco de forma linear para manter a ordem da página
                            for elemento in celula.find_all(recursive=True):
                                
                                # 1. Captura cabeçalhos de Nível ou Nome de Cargo em tags de texto isoladas
                                if elemento.name == "p":
                                    if elemento.find("a"):
                                        continue
                                        
                                    txt_p = " ".join(elemento.get_text(strip=True).split())
                                    
                                    if not txt_p or txt_p == "Prova Objetiva":
                                        continue
                                        
                                    if "Nível" in txt_p or "Escolaridade" in txt_p:
                                        nivel_atual = txt_p
                                        cargo_atual = ""  # Reseta o cargo pois mudou o nível de escolaridade
                                    else:
                                        cargo_atual = txt_p  # Define o novo cargo corrente

                                # 2. Processa os links das Provas propriamente ditas
                                elif elemento.name == "a":
                                    href_arq = elemento.get("href")
                                    txt_a = " ".join(elemento.get_text(strip=True).split())
                                    
                                    if href_arq:
                                        url_arq_completa = (
                                            "https://conhecimento.fgv.br" + href_arq 
                                            if href_arq.startswith("/") else href_arq
                                        )
                                        
                                        # Constrói sequencialmente a árvore de nomes
                                        partes_nome = [titulo_concurso]
                                        
                                        if nivel_atual:
                                            partes_nome.append(nivel_atual)
                                            
                                        if cargo_atual:
                                            partes_nome.append(cargo_atual)
                                            
                                        # Adiciona o texto do link (ex: "Tipo 1") se ele não for repetitivo
                                        if txt_a and txt_a not in cargo_atual and txt_a not in nivel_atual:
                                            partes_nome.append(txt_a)
                                            
                                        # Junta todas as partes usando o separador padrão
                                        descricao_completa = " - ".join(partes_nome)

                                        foi_salvo = ConcursoRepository.salvar_arquivo_prova(
                                            concurso_id=concurso.id,
                                            descricao=descricao_completa,
                                            url_arquivo=url_arq_completa,
                                        )

                                        if foi_salvo:
                                            total_provas_descobertas += 1
                                            print_msg = f"✨ [PROVA NOVA]\n📝 {descricao_completa}\n🔗 {url_arq_completa}\n\n"
                                        else:
                                            total_provas_ja_existentes += 1
                                            print_msg = f"📚 [HISTÓRICO BASE]\n📝 {descricao_completa}\n🔗 {url_arq_completa}\n\n"
                                        
                                        self.after(0, self.atualizar_interface_safe, msg_status, porcentagem, print_msg, True)
                                        
                time.sleep(1.2)

            except Exception as e:
                self.after(0, self.atualizar_interface_safe, msg_status, porcentagem, f"⚠️ Erro ao acessar {concurso.url}: {e}\n", True)
                continue

        msg_fim = f"Varredura de Provas Concluída! {total_provas_descobertas} novas inserções."
        fim_texto_bloco = (
            f"=== VARREDURA WEB FINALIZADA ===\n"
            f"Links inéditos salvos nesta rodada: {total_provas_descobertas}\n"
            f"Links reaproveitados da base: {total_provas_ja_existentes}\n\n"
            f"Pronto para processamento local.\n"
        )
        self.after(0, self.atualizar_interface_safe, msg_fim, 1.0, fim_texto_bloco, True)
        self.after(0, self.liberar_botoes)


if __name__ == "__main__":
    inicializar_banco()
    app = ScraperApp()
    app.mainloop()