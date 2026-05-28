import os
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from pypdf import PdfReader


class JanelaResultadosProvas(ctk.CTkToplevel):
    """Janela secundária que recebe a lista da FGV e estende com busca em PDFs locais."""

    def __init__(self, parent, texto_inicial=""):
        super().__init__(parent)
        self.parent = parent
        
        self.title("Resultados da Verificação de Provas e Busca Local")
        self.geometry("750x600")
        
        # Garante foco na frente da tela principal
        self.lift()
        self.focus_force()
        
        # --- COMPONENTES DE SELEÇÃO DE PASTA ---
        self.frame_busca = ctk.CTkFrame(self)
        self.frame_busca.pack(padx=20, pady=10, fill="x")

        self.lbl_pasta = ctk.CTkLabel(self.frame_busca, text="Pasta dos PDFs locais:")
        self.lbl_pasta.pack(side="left", padx=10, pady=5)

        self.txt_pasta = ctk.CTkEntry(
            self.frame_busca, placeholder_text="Selecione a pasta onde os PDFs estão salvos..."
        )
        self.txt_pasta.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        self.btn_procurar = ctk.CTkButton(
            self.frame_busca, text="Procurar...", width=90, command=self._selecionar_pasta
        )
        self.btn_procurar.pack(side="left", padx=10, pady=5)

        # --- COMPONENTES DO TERMO DE BUSCA ---
        self.frame_termo = ctk.CTkFrame(self)
        self.frame_termo.pack(padx=20, pady=5, fill="x")

        self.lbl_termo = ctk.CTkLabel(self.frame_termo, text="Termo para pesquisar:")
        self.lbl_termo.pack(side="left", padx=10, pady=5)

        self.txt_termo = ctk.CTkEntry(
            self.frame_termo, placeholder_text="Ex: Prova Objetiva / Direito Administrativo..."
        )
        self.txt_termo.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        # --- BOTÃO DE AÇÃO ---
        self.frame_acoes = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_acoes.pack(padx=20, pady=5, fill="x")

        self.btn_processar = ctk.CTkButton(
            self.frame_acoes,
            text="🚀 Iniciar Processamento de PDFs Locais",
            command=self._ao_clicar_processar,
            fg_color="#2b8a3e",
            hover_color="#237032",
        )
        self.btn_processar.pack(fill="x", pady=5)

        # --- ÁREA DE TEXTO / LOGS ---
        self.txt_provas = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.txt_provas.pack(padx=20, pady=10, fill="both", expand=True)
        
        if texto_inicial:
            self.txt_provas.insert(tk.END, texto_inicial)
            self.txt_provas.see(tk.END)

    def _selecionar_pasta(self):
        """Abre o diálogo nativo do sistema operacional para escolher uma pasta."""
        pasta_selecionada = filedialog.askdirectory()
        if pasta_selecionada:
            self.txt_pasta.delete(0, tk.END)
            self.txt_pasta.insert(0, os.path.normpath(pasta_selecionada))

    def _ao_clicar_processar(self):
        """Envia os dados capturados para o App principal processar em Thread."""
        pasta = self.txt_pasta.get()
        termo = self.txt_termo.get()
        
        if hasattr(self.parent, "iniciar_processamento_arquivos"):
            self.parent.iniciar_processamento_arquivos(pasta, termo)

    def executar_busca_local(self, caminho_pasta, termo_busca):
        """Lógica executada via Thread para ler e varrer o conteúdo interno dos PDFs."""
        termo_busca = termo_busca.lower().strip()

        if not os.path.exists(caminho_pasta):
            self.after(0, self.adicionar_texto, "\n❌ Erro: Diretório informado não existe.\n")
            self.after(0, lambda: self.btn_processar.configure(state="normal"))
            return

        arquivos = [f for f in os.listdir(caminho_pasta) if f.lower().endswith(".pdf")]

        if not arquivos:
            self.after(0, self.adicionar_texto, "\n⚠️ Nenhum arquivo .pdf encontrado na pasta selecionada.\n")
            self.after(0, lambda: self.btn_processar.configure(state="normal"))
            return

        self.after(0, self.adicionar_texto, f"\n=== INICIANDO BUSCA LOCAL EM {len(arquivos)} PDFs ===\n")

        for nome_arquivo in arquivos:
            caminho_completo = os.path.join(caminho_pasta, nome_arquivo)
            try:
                reader = PdfReader(caminho_completo)
                for num_pagina, pagina in enumerate(reader.pages, start=1):
                    texto = pagina.extract_text()
                    if texto and (not termo_busca or termo_busca in texto.lower()):
                        msg = f"🔍 Encontrado em: {nome_arquivo} -> Página {num_pagina}\n"
                        self.after(0, self.adicionar_texto, msg)
            except Exception as e:
                self.after(0, self.adicionar_texto, f"⚠️ Falha ao ler o arquivo {nome_arquivo}: {e}\n")

        self.after(0, self.adicionar_texto, "\n=== FIM DO PROCESSAMENTO LOCAL ===\n")
        self.after(0, lambda: self.btn_processar.configure(state="normal"))

    def adicionar_texto(self, texto):
        """Injeta mensagens na caixa de texto de logs da janela secundária."""
        self.txt_provas.insert(tk.END, texto)
        self.txt_provas.see(tk.END)