import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from services.pdf_search_service import PdfSearchService

class ViewProcessar(ctk.CTkFrame):
    """Tela focada exclusivamente na separação de arquivos por termos internos, livre de dados do banco."""
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.lbl_titulo = ctk.CTkLabel(self, text="⚙️ Processar Provas / PDFs Locais", font=("Arial", 18, "bold"))
        self.lbl_titulo.pack(pady=15)

        self.frame_grid = ctk.CTkFrame(self)
        self.frame_grid.pack(padx=20, pady=5, fill="x")

        # Config de Inputs
        ctk.CTkLabel(self.frame_grid, text="Pasta PDFs (Origem):").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.txt_origem = ctk.CTkEntry(self.frame_grid, width=380)
        self.txt_origem.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        ctk.CTkButton(self.frame_grid, text="Procurar...", width=90, command=lambda: self.escolher_pasta(self.txt_origem)).grid(row=0, column=2, padx=10, pady=5)

        ctk.CTkLabel(self.frame_grid, text="Pasta Destino (Filtro):").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.txt_destino = ctk.CTkEntry(self.frame_grid, width=380)
        self.txt_destino.grid(row=1, column=1, padx=5, pady=5, sticky="we")
        ctk.CTkButton(self.frame_grid, text="Procurar...", width=90, command=lambda: self.escolher_pasta(self.txt_destino)).grid(row=1, column=2, padx=10, pady=5)

        ctk.CTkLabel(self.frame_grid, text="Termo p/ buscar:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.txt_termo = ctk.CTkEntry(self.frame_grid, width=380)
        self.txt_termo.insert(0, "Decreto-Lei nº 220/75")
        self.txt_termo.grid(row=2, column=1, padx=5, pady=5, sticky="we")

        self.btn_filtrar = ctk.CTkButton(self.frame_grid, text="Separar PDFs", fg_color="#e67e22", command=self.disparar_filtro)
        self.btn_filtrar.grid(row=2, column=2, padx=10, pady=5, sticky="we")

        self.frame_grid.columnconfigure(1, weight=1)

        self.txt_log = ctk.CTkTextbox(self, width=700, height=380)
        self.txt_log.pack(padx=20, pady=15, fill="both", expand=True)

    def escolher_pasta(self, widget):
        cam = filedialog.askdirectory()
        if cam:
            widget.delete(0, tk.END)
            widget.insert(0, cam)

    def disparar_filtro(self):
        origem = self.txt_origem.get().strip()
        destino = self.txt_destino.get().strip()
        termo = self.txt_termo.get().strip()

        if not origem or not destino or not termo:
            self.txt_log.insert(tk.END, "⚠️ Todos os parâmetros visuais são obrigatórios.\n")
            return

        self.btn_filtrar.configure(state="disabled")
        self.txt_log.delete("1.0", tk.END)

        threading.Thread(target=PdfSearchService.buscar_e_separar, args=(origem, destino, termo, self.callback_thread), daemon=True).start()

    def callback_thread(self, status_msg, progresso, log_msg=None):
        if status_msg is not None:
            self.master.master.atualizar_status(status_msg, progresso)
        if log_msg:
            self.txt_log.insert(tk.END, log_msg)
            self.txt_log.see(tk.END)
        if progresso == 1.0:
            self.btn_filtrar.configure(state="normal")