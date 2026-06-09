import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from services.download_service import DownloadService
from repository.concurso_repo import ConcursoRepository
import os

class ViewDownload(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        # Evento de controle de sincronização da Thread de download
        self.evento_pausa = threading.Event()
        self.evento_pausa.set()  
        self.download_em_andamento = False

        # Título da Tela
        self.lbl_titulo = ctk.CTkLabel(
            self, text="📥 Baixar Provas / PDFs da Web", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.lbl_titulo.pack(pady=(20, 10), padx=20, anchor="w")

        # --- CARD PRINCIPAL DE ENTRADAS ---
        self.frame_dir = ctk.CTkFrame(self)
        self.frame_dir.pack(padx=20, pady=10, fill="x")

        # Label reposicionado para o topo do card (Evita espremer a linha)
        self.lbl_pasta = ctk.CTkLabel(self.frame_dir, text="Pasta de Origem / Salvar PDFs:")
        self.lbl_pasta.pack(padx=15, pady=(15, 2), anchor="w")

        # Container horizontal exclusivo para os controles (Entry + Botões)
        self.frame_controles_linha = ctk.CTkFrame(self.frame_dir, fg_color="transparent")
        self.frame_controles_linha.pack(fill="x", padx=10, pady=(0, 15))

        self.entry_pasta = ctk.CTkEntry(
            self.frame_controles_linha, 
            placeholder_text="Selecione o diretório para download dos arquivos..."
        )
        self.entry_pasta.pack(side="left", fill="x", expand=True, padx=(5, 5))

        caminho_salvar_pdf = os.path.join(os.path.expanduser("~"), "Área de trabalho", "Concursos", "PDFs FGV")        
        self.entry_pasta.insert(0, caminho_salvar_pdf)

        # Bloco de Botões Alinhados à direita com tamanhos padronizados
        self.btn_procurar = ctk.CTkButton(self.frame_controles_linha, text="Procurar...", width=100, command=self.selecionar_pasta)
        self.btn_procurar.pack(side="left", padx=5)

        self.btn_download = ctk.CTkButton(self.frame_controles_linha, text="Baixar Lote", width=100, command=self.disparar_download)
        self.btn_download.pack(side="left", padx=5)

        self.btn_pausa = ctk.CTkButton(
            self.frame_controles_linha, 
            text="Pausar", 
            width=100, 
            fg_color="#D97706", 
            hover_color="#B45309", 
            command=self.alternar_pausa,
            state="disabled" 
        )
        self.btn_pausa.pack(side="left", padx=(5, 5))

        # --- MONITORAMENTO E LOGS ---
        self.lbl_status = ctk.CTkLabel(self, text="Status: Aguardando comando...", font=("Arial", 12))
        self.lbl_status.pack(anchor="w", padx=25, pady=(10, 2))

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(padx=20, pady=5, fill="x")

        self.lbl_qtd_links = ctk.CTkLabel(self, text="Links pendentes para baixar: 0", font=("Arial", 11, "italic"))
        self.lbl_qtd_links.pack(anchor="w", padx=25, pady=(0, 5))

        self.txt_log = ctk.CTkTextbox(self, height=200)
        self.txt_log.pack(padx=20, pady=10, fill="both", expand=True)

        self.atualizar_contador_links()

    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(initialdir=self.entry_pasta.get().strip())
        if pasta:
            self.entry_pasta.delete(0, tk.END)
            self.entry_pasta.insert(0, pasta)

    def atualizar_contador_links(self):
        qtd = ConcursoRepository.contar_arquivos_provas()
        self.lbl_qtd_links.configure(text=f"Total de links de provas catalogados na base de dados: {qtd} arquivos.")

    def alternar_pausa(self):
        if not self.download_em_andamento:
            return

        if self.evento_pausa.is_set():
            self.evento_pausa.clear() 
            self.btn_pausa.configure(text="Continuar", fg_color="#059669", hover_color="#047857")
            self.txt_log.insert(tk.END, "⏸️ [PAUSADO] O processo será congelado após concluir a requisição atual...\n")
            self.txt_log.see(tk.END)
        else:
            self.evento_pausa.set() 
            self.btn_pausa.configure(text="Pausar", fg_color="#D97706", hover_color="#B45309")
            self.txt_log.insert(tk.END, "▶️ [RETOMADO] Continuando downloads...\n")
            self.txt_log.see(tk.END)

    def disparar_download(self):
        pasta = self.entry_pasta.get().strip()
        if not pasta:
            self.txt_log.insert(tk.END, "⚠️ Indique uma pasta local primeiro.\n")
            return

        self.btn_download.configure(state="disabled")
        self.btn_pausa.configure(state="normal") 
        self.txt_log.delete("1.0", tk.END)
        
        self.download_em_andamento = True
        self.evento_pausa.set() 
        self.btn_pausa.configure(text="Pausar", fg_color="#D97706", hover_color="#B45309")
        
        threading.Thread(
            target=DownloadService.executar_downloads, 
            args=(pasta, self.callback_thread, self.evento_pausa), 
            daemon=True
        ).start()

    def callback_thread(self, status_msg, progresso, log_msg=None):
        if status_msg is not None:
            self.lbl_status.configure(text=f"Status: {status_msg}")
        if progresso is not None:
            self.progress_bar.set(progresso)
        if log_msg is not None:
            self.txt_log.insert(tk.END, log_msg)
            self.txt_log.see(tk.END)

        if status_msg == "Downloads finalizados!":
            self.btn_download.configure(state="normal")
            self.btn_pausa.configure(state="disabled", text="Pausar", fg_color="#D97706")
            self.download_em_andamento = False