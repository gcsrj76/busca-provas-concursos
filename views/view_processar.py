import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from services.pdf_search_service import PdfSearchService

class ViewProcessar(ctk.CTkFrame):
    """Tela focada exclusivamente na separação de arquivos por termos internos, livre de dados do banco."""
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.lbl_titulo = ctk.CTkLabel(self, text="⚙️ Processar PDFs Baixados (Provas, Editais e Gabaritos)", font=("Arial", 18, "bold"))
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

        # Botões de Ação posicionados na Linha 2 do Grid
        self.btn_filtrar = ctk.CTkButton(self.frame_grid, text="Separar PDFs por Tipo", fg_color="#2980b9", command=self.separar_pdf_tipo)
        self.btn_filtrar.grid(row=2, column=1, padx=5, pady=10, sticky="e")

        self.btn_filtrar_materias = ctk.CTkButton(self.frame_grid, text="Separar Provas por Matérias", fg_color="#e67e22", command=self.separar_prova_materia)
        self.btn_filtrar_materias.grid(row=2, column=2, padx=10, pady=10, sticky="we")

        self.frame_grid.columnconfigure(1, weight=1)

        self.txt_log = ctk.CTkTextbox(self, width=700, height=380)
        self.txt_log.pack(padx=20, pady=15, fill="both", expand=True)

    def escolher_pasta(self, widget):
        cam = filedialog.askdirectory()
        if cam:
            widget.delete(0, tk.END)
            widget.insert(0, cam)

    def bloquear_botoes(self):
        self.btn_filtrar.configure(state="disabled")
        self.btn_filtrar_materias.configure(state="disabled")
        self.txt_log.delete("1.0", tk.END)

    def liberar_botoes(self):
        self.btn_filtrar.configure(state="normal")
        self.btn_filtrar_materias.configure(state="normal")

    def separar_pdf_tipo(self):
        origem = self.txt_origem.get().strip()
        destino = self.txt_destino.get().strip()

        if not origem or not destino:
            self.txt_log.insert(tk.END, "⚠️ Os parâmetros de Origem e Destino são obrigatórios para a triagem FGV.\n")
            return

        self.bloquear_botoes()

        threading.Thread(
            target=PdfSearchService.separar_por_tipos, 
            args=(origem, destino, self.callback_thread), 
            daemon=True
        ).start()        

    def separar_prova_materia(self):
        origem = self.txt_origem.get().strip()

        if not origem:
            self.txt_log.insert(tk.END, "⚠️ A pasta de Origem é obrigatória para a separação por matérias.\n")
            return

        self.bloquear_botoes()

        # Executa a nova função injetando apenas a origem
        threading.Thread(
            target=PdfSearchService.separar_por_materias, 
            args=(origem, self.callback_thread), 
            daemon=True
        ).start()

    def callback_thread(self, status_msg, progresso, log_msg=None):
        if status_msg is not None:
            self.master.master.atualizar_status(status_msg, progresso)
        if log_msg:
            self.txt_log.insert(tk.END, log_msg)
            self.txt_log.see(tk.END)
        if progresso == 1.0:
            self.liberar_botoes()