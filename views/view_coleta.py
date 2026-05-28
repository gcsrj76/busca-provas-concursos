import threading
import tkinter as tk
import customtkinter as ctk
from services.scraper_service import ScraperService

class ViewColeta(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.lbl_titulo = ctk.CTkLabel(self, text="🚀 Coletar Dados de Concursos (FGV)", font=("Arial", 18, "bold"))
        self.lbl_titulo.pack(pady=15)

        self.frame_input = ctk.CTkFrame(self)
        self.frame_input.pack(padx=20, pady=5, fill="x")

        self.lbl_pag = ctk.CTkLabel(self.frame_input, text="Páginas para varrer:")
        self.lbl_pag.pack(side="left", padx=10, pady=10)

        self.txt_paginas = ctk.CTkEntry(self.frame_input, width=60)
        self.txt_paginas.insert(0, "1")
        self.txt_paginas.pack(side="left", padx=5, pady=10)

        self.btn_iniciar = ctk.CTkButton(self.frame_input, text="Iniciar Coleta", command=self.disparar_coleta, fg_color="#1c7ed6")
        self.btn_iniciar.pack(side="right", padx=10, pady=10)

        self.txt_log = ctk.CTkTextbox(self, width=700, height=450)
        self.txt_log.pack(padx=20, pady=15, fill="both", expand=True)

    def disparar_coleta(self):
        try:
            max_pag = int(self.txt_paginas.get())
        except ValueError:
            self.txt_log.insert(tk.END, "Erro: Insira um número de páginas válido!\n")
            return

        self.btn_iniciar.configure(state="disabled")
        self.txt_log.delete("1.0", tk.END)
        self.master.master.atualizar_status("Iniciando varredura da lista de concursos FGV...", 0)

        threading.Thread(target=ScraperService.executar_coleta, args=(max_pag, self.callback_thread), daemon=True).start()

    def callback_thread(self, status_msg, progresso, log_msg=None):
        if status_msg is not None:
            self.master.master.atualizar_status(status_msg, progresso)
        if log_msg:
            self.txt_log.insert(tk.END, log_msg)
            self.txt_log.see(tk.END)
        if progresso == 1.0:
            self.btn_iniciar.configure(state="normal")