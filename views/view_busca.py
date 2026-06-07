import threading
import tkinter as tk
import customtkinter as ctk
from services.web_proof_service import WebProofService
from repository.concurso_repo import ConcursoRepository

class ViewBusca(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.lbl_titulo = ctk.CTkLabel(self, text="🔍 Buscar Provas nos Concursos", font=("Arial", 18, "bold"))
        self.lbl_titulo.pack(pady=15)

        self.frame_info = ctk.CTkFrame(self)
        self.frame_info.pack(padx=20, pady=5, fill="x")

        self.lbl_status_base = ctk.CTkLabel(self.frame_info, text="Concursos disponíveis para varrer: 0")
        self.lbl_status_base.pack(side="left", padx=15, pady=10)

        self.btn_buscar = ctk.CTkButton(self.frame_info, text="Varrer Links de PDFs", command=self.disparar_busca_pdfs, fg_color="#2b8a3e")
        self.btn_buscar.pack(side="right", padx=15, pady=10)

        self.txt_log = ctk.CTkTextbox(self, width=700, height=450)
        self.txt_log.pack(padx=20, pady=15, fill="both", expand=True)
        
        self.atualizar_contagem()

    def atualizar_contagem(self):
        qtd = ConcursoRepository.contar_concursos()
        self.lbl_status_base.configure(text=f"Concursos disponíveis no banco: {qtd}")

    def disparar_busca_pdfs(self):
        self.btn_buscar.configure(state="disabled")
        self.txt_log.delete("1.0", tk.END)
        self.master.master.atualizar_status("Acessando tabelas internas da FGV...", 0)

        threading.Thread(target=WebProofService.varrer_pdfs_web, args=(self.callback_thread,), daemon=True).start()

    def callback_thread(self, status_msg, progresso, log_msg=None):
        if status_msg is not None:
            self.master.master.atualizar_status(status_msg, progresso)
        if log_msg:
            self.txt_log.insert(tk.END, log_msg)
            self.txt_log.see(tk.END)
        if progresso == 1.0:
            self.btn_buscar.configure(state="normal")