import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from services.download_service import DownloadService
from repository.concurso_repo import ConcursoRepository

class ViewDownload(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.lbl_titulo = ctk.CTkLabel(self, text="📥 Baixar Provas / PDFs da Web", font=("Arial", 18, "bold"))
        self.lbl_titulo.pack(pady=15)

        self.frame_dir = ctk.CTkFrame(self)
        self.frame_dir.pack(padx=20, pady=5, fill="x")

        self.lbl_pasta = ctk.CTkLabel(self.frame_dir, text="Pasta de Origem/Salvar PDFs:")
        self.lbl_pasta.pack(side="left", padx=10, pady=10)

        self.txt_pasta = ctk.CTkEntry(self.frame_dir, width=320)
        self.txt_pasta.pack(side="left", padx=5, pady=10, fill="x", expand=True)

        self.btn_procurar = ctk.CTkButton(self.frame_dir, text="Procurar...", width=90, command=self.selecionar_pasta)
        self.btn_procurar.pack(side="left", padx=5, pady=10)

        self.btn_download = ctk.CTkButton(self.frame_dir, text="Baixar Lote", width=100, fg_color="#1098ad", command=self.disparar_download)
        self.btn_download.pack(side="right", padx=10, pady=10)

        self.lbl_qtd_links = ctk.CTkLabel(self, text="Links pendentes para baixar: 0", font=("Arial", 11, "italic"))
        self.lbl_qtd_links.pack(anchor="w", padx=25)

        self.txt_log = ctk.CTkTextbox(self, width=700, height=420)
        self.txt_log.pack(padx=20, pady=10, fill="both", expand=True)

        self.atualizar_contador_links()

    def selecionar_pasta(self):
        cam = filedialog.askdirectory()
        if cam:
            self.txt_pasta.delete(0, tk.END)
            self.txt_pasta.insert(0, cam)

    def atualizar_contador_links(self):
        qtd = ConcursoRepository.contar_arquivos_provas()
        self.lbl_qtd_links.configure(text=f"Total de links de provas catalogados na base de dados: {qtd} arquivos.")

    def disparar_download(self):
        pasta = self.txt_pasta.get().strip()
        if not pasta:
            self.txt_log.insert(tk.END, "⚠️ Indique uma pasta local primeiro.\n")
            return

        self.btn_download.configure(state="disabled")
        self.txt_log.delete("1.0", tk.END)
        
        threading.Thread(target=DownloadService.executar_downloads, args=(pasta, self.callback_thread), daemon=True).start()

    def callback_thread(self, status_msg, progresso, log_msg=None):
        if status_msg is not None:
            self.master.master.atualizar_status(status_msg, progresso)
        if log_msg:
            self.txt_log.insert(tk.END, log_msg)
            self.txt_log.see(tk.END)
        if progresso == 1.0:
            self.btn_download.configure(state="normal")