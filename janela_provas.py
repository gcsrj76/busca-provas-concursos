import os
import shutil  # Utilizado para copiar o arquivo caso o termo seja localizado
import threading
import time
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
import requests
from repository import ConcursoRepository

# Tenta importar o pypdf com fallback preventivo
try:
    import pypdf
except ImportError:
    pypdf = None


class JanelaResultadosProvas(ctk.CTkToplevel):
    """Janela separada para exibir os resultados e gerenciar os PDFs das provas."""

    def __init__(self, parent, texto_inicial=""):
        super().__init__(parent)
        self.parent = parent  # Referência do app principal

        self.title("Resultados da Verificação de Provas")
        self.geometry("780 shifted")
        self.geometry("780x700")

        # Garante foco na tela ao abrir
        self.lift()
        self.focus_force()

        # --- TÍTULO ---
        self.lbl_titulo = ctk.CTkLabel(
            self, text="Provas Objetivas Encontradas", font=("Arial", 16, "bold")
        )
        self.lbl_titulo.pack(pady=10)

        # --- FRAME DE CONTROLES DE DIRETÓRIO E PARÂMETROS ---
        self.frame_inputs = ctk.CTkFrame(self)
        self.frame_inputs.pack(padx=20, pady=5, fill="x")

        # 1. Entrada da Pasta de Origem/Downloads
        self.lbl_pasta = ctk.CTkLabel(self.frame_inputs, text="Pasta Destino/PDFs (Origem):")
        self.lbl_pasta.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.txt_pasta = ctk.CTkEntry(self.frame_inputs, width=420)
        self.txt_pasta.grid(row=0, column=1, padx=5, pady=5, sticky="we")

        self.btn_procurar = ctk.CTkButton(
            self.frame_inputs, text="Selecionar...", width=100, command=self.selecionar_pasta_origem
        )
        self.btn_procurar.grid(row=0, column=2, padx=10, pady=5)

        # 2. INCLUSÃO: Entrada da Pasta Destino para Provas Selecionadas (Filtradas)
        self.lbl_pasta_filtrados = ctk.CTkLabel(self.frame_inputs, text="Pasta Provas Selecionadas:")
        self.lbl_pasta_filtrados.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.txt_pasta_filtrados = ctk.CTkEntry(self.frame_inputs, width=420)
        self.txt_pasta_filtrados.grid(row=1, column=1, padx=5, pady=5, sticky="we")

        self.btn_procurar_filtrados = ctk.CTkButton(
            self.frame_inputs, text="Selecionar...", width=100, command=self.selecionar_pasta_filtrados
        )
        self.btn_procurar_filtrados.grid(row=1, column=2, padx=10, pady=5)

        # 3. Entrada do Termo de Busca
        self.lbl_termo = ctk.CTkLabel(self.frame_inputs, text="Termo p/ buscar nos PDFs:")
        self.lbl_termo.grid(row=2, column=0, padx=10, pady=5, sticky="w")

        self.txt_termo = ctk.CTkEntry(self.frame_inputs, width=420)
        self.txt_termo.insert(0, "Decreto-Lei nº 220/75")  # Exemplo padrão sugerido
        self.txt_termo.grid(row=2, column=1, padx=5, pady=5, sticky="we")

        # Configuração de redimensionamento da grid interna
        self.frame_inputs.columnconfigure(1, weight=1)

        # --- CONTROLADORES DE FLUXO ---
        self.frame_acoes = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_acoes.pack(pady=10)

        self.btn_download = ctk.CTkButton(
            self.frame_acoes, text="📥 Baixar PDFs Inéditos da Web", fg_color="#1c7ed6", hover_color="#1971c2", command=self.acionar_downloads
        )
        self.btn_download.pack(side="left", padx=10)

        self.btn_processar = ctk.CTkButton(
            self.frame_acoes, text="⚙️ Iniciar Processamento PDFs Locais", fg_color="#e67e22", hover_color="#d35400", command=self.acionar_processamento_local
        )
        self.btn_processar.pack(side="left", padx=10)

        # --- ÁREA DE LOG DE EXECUÇÃO ---
        self.txt_provas = ctk.CTkTextbox(self, width=720, height=400)
        self.txt_provas.pack(padx=20, pady=10, fill="both", expand=True)

        if texto_inicial:
            self.adicionar_texto(texto_inicial)

    def adicionar_texto(self, texto):
        self.txt_provas.insert(tk.END, texto)
        self.txt_provas.see(tk.END)

    def selecionar_pasta_origem(self):
        caminho = filedialog.askdirectory()
        if caminho:
            self.txt_pasta.delete(0, tk.END)
            self.txt_pasta.insert(0, caminho)

    def selecionar_pasta_filtrados(self):
        caminho = filedialog.askdirectory()
        if caminho:
            self.txt_pasta_filtrados.delete(0, tk.END)
            self.txt_pasta_filtrados.insert(0, caminho)

    def acionar_downloads(self):
        pasta_destino = self.txt_pasta.get().strip()
        if not pasta_destino:
            self.adicionar_texto("⚠️ Erro: Indique uma pasta de destino válida para salvar os downloads.\n")
            return
        
        self.btn_download.configure(state="disabled")
        self.parent.lbl_status.configure(text="Status: Baixando arquivos de prova...")
        
        threading.Thread(target=self.executar_fluxo_downloads, args=(pasta_destino,), daemon=True).start()

    def executar_fluxo_downloads(self, pasta_destino):
        if not os.path.exists(pasta_destino):
            os.makedirs(pasta_destino, exist_ok=True)

        concursos = ConcursoRepository.listar_todos()
        arquivos_para_baixar = []
        for c in concursos:
            for arq in c.arquivos:
                arquivos_para_baixar.append(arq)

        total_arquivos = len(arquivos_para_baixar)
        if total_arquivos == 0:
            self.adicionar_texto("Nenhum link de prova mapeado no banco de dados para download.\n")
            self.parent.after(0, lambda: self.btn_download.configure(state="normal"))
            return

        self.adicionar_texto(f"Iniciando download em lote de {total_arquivos} arquivos de prova...\n\n")
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        baixados_sucesso = 0

        for i, arq in enumerate(arquivos_para_baixar):
            nome_limpo = "".join([c for c in arq.descricao if c.isalnum() or c in (" ", "-", "_")]).rstrip()
            nome_arquivo = f"{nome_limpo}.pdf"
            caminho_completo = os.path.join(pasta_destino, nome_arquivo)

            if os.path.exists(caminho_completo):
                self.adicionar_texto(f"⏭️ [JÁ EXISTE LOCAL] {nome_arquivo}\n")
                baixados_sucesso += 1
                continue

            try:
                resposta = requests.get(arq.url_arquivo, headers=headers, timeout=15)
                if resposta.status_code == 200:
                    with open(caminho_completo, "wb") as f:
                        f.write(resposta.content)
                    self.adicionar_texto(f"📥 [DOWNLOAD COMPLETO] {nome_arquivo}\n")
                    baixados_sucesso += 1
                else:
                    self.adicionar_texto(f"❌ [ERRO {resposta.status_code}] Falha ao baixar: {nome_arquivo}\n")
                time.sleep(0.5)
            except Exception as e:
                self.adicionar_texto(f"⚠️ [FALHA DE CONEXÃO] Erro em {nome_arquivo}: {e}\n")

        self.adicionar_texto(f"\n=== DOWNLOADS CONCLUÍDOS ===\nSucesso: {baixados_sucesso} de {total_arquivos} arquivos salvos na pasta.\n\n")
        self.parent.after(0, lambda: self.btn_download.configure(state="normal"))
        self.parent.after(0, lambda: self.parent.lbl_status.configure(text="Status: Downloads de PDFs concluídos."))

    # --- FLUXO DE EXECUÇÃO LOCAL (PYPDF + COPIAR FILTRADOS) ---
    def acionar_processamento_local(self):
        pasta_origem = self.txt_pasta.get().strip()
        pasta_filtrados = self.txt_pasta_filtrados.get().strip()
        termo = self.txt_termo.get().strip()

        if not pypdf:
            self.adicionar_texto("❌ Erro: Biblioteca 'pypdf' não instalada! Instale via: pip install pypdf\n")
            return

        if not pasta_origem or not os.path.exists(pasta_origem):
            self.adicionar_texto("⚠️ Por favor, selecione uma pasta de origem válida.\n")
            return

        if not pasta_filtrados:
            self.adicionar_texto("⚠️ Por favor, selecione uma pasta de destino para as provas filtradas.\n")
            return

        if not termo:
            self.adicionar_texto("⚠️ Digite um termo de busca válido.\n")
            return

        self.btn_processar.configure(state="disabled")
        
        # Chama o processador local passando os parâmetros corretos por meio de Thread dedicada
        threading.Thread(
            target=self.executar_busca_local,
            args=(pasta_origem, pasta_filtrados, termo),
            daemon=True,
        ).start()

    def executar_busca_local(self, pasta_origem, pasta_filtrados, termo):
        """Varre os PDFs locais, extrai textos, busca o termo e copia os correspondentes."""
        self.adicionar_texto(f"=== INICIANDO VARREDURA LOCAL DE TEXTO ===\n")
        self.adicionar_texto(f"Busca ativa por: '{termo}'\n")
        self.adicionar_texto(f"Origem: {pasta_origem}\n")
        self.adicionar_texto(f"Destino Filtrados: {pasta_filtrados}\n\n")

        if not os.path.exists(pasta_filtrados):
            os.makedirs(pasta_filtrados, exist_ok=True)

        # Filtra os arquivos .pdf da pasta informada
        arquivos_diretorio = [f for f in os.listdir(pasta_origem) if f.lower().endswith(".pdf")]
        total_arquivos = len(arquivos_diretorio)

        if total_arquivos == 0:
            self.adicionar_texto("Nenhum arquivo PDF localizado na pasta de origem indicada.\n")
            self.parent.after(0, lambda: self.btn_processar.configure(state="normal"))
            return

        cont_localizados = 0
        termo_lower = termo.lower()

        for i, nome_arq in enumerate(arquivos_diretorio):
            caminho_pdf_origem = os.path.join(pasta_origem, nome_arq)
            encontrou_no_arquivo = False
            
            try:
                # Abre e processa as páginas do PDF com o pypdf
                with open(caminho_pdf_origem, "rb") as f:
                    leitor = pypdf.PdfReader(f)
                    total_paginas = len(leitor.pages)

                    for num_pag in range(total_paginas):
                        pagina = leitor.pages[num_pag]
                        texto_pagina = pagina.extract_text()
                        
                        if texto_pagina and termo_lower in texto_pagina.lower():
                            encontrou_no_arquivo = True
                            break  # Termo localizado, pula o resto das páginas deste PDF

                if encontrou_no_arquivo:
                    cont_localizados += 1
                    caminho_pdf_destino = os.path.join(pasta_filtrados, nome_arq)
                    
                    # Copia o arquivo localizado para a pasta de selecionados
                    shutil.copy2(caminho_pdf_origem, caminho_pdf_destino)
                    
                    self.adicionar_texto(f"🎯 [MATCH - COPIADO] {nome_arq}\n")
                else:
                    self.adicionar_texto(f"⏭️ [NÃO CONTÉM] {nome_arq}\n")

            except Exception as e:
                self.adicionar_texto(f"⚠️ [ERRO DE LEITURA] Falha ao processar arquivo {nome_arq}: {e}\n")

        self.adicionar_texto(f"\n=== PROCESSAMENTO CONCLUÍDO ===\n")
        self.adicionar_texto(f"Total de arquivos analisados: {total_arquivos}\n")
        self.adicionar_texto(f"Provas contendo o termo e copiadas: {cont_localizados}\n\n")
        
        self.parent.after(0, lambda: self.btn_processar.configure(state="normal"))
        self.parent.after(0, lambda: self.parent.lbl_status.configure(text="Status: Varredura de PDFs locais concluída."))