import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from services.pdf_search_service import PdfSearchService
import os

class ViewProcessar(ctk.CTkFrame):
    """Tela focada exclusivamente na separação de arquivos por termos internos, livre de dados do banco."""
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.lbl_titulo = ctk.CTkLabel(self, text="⚙️ Processar PDFs Baixados (Provas, Editais e Gabaritos)", font=("Arial", 18, "bold"))
        self.lbl_titulo.pack(pady=15)

        # Mudamos o pack para não esticar totalmente (fill="x" removido) e centralizar os elementos agrupados
        self.frame_grid = ctk.CTkFrame(self)
        self.frame_grid.pack(padx=20, pady=5)

        # Config de Inputs - Aumentamos levemente o width para 450 para compensar o espaço que sobrou
        ctk.CTkLabel(self.frame_grid, text="Pasta PDFs (Origem):").grid(row=0, column=0, padx=(15, 5), pady=10, sticky="w")
        self.entry_pasta_origem = ctk.CTkEntry(self.frame_grid, width=450)
        self.entry_pasta_origem.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        
        caminho_pdf_baixados = os.path.join(os.path.expanduser("~"), "Área de trabalho","Concursos","PDFs FGV")        
        self.entry_pasta_origem.insert(0, caminho_pdf_baixados)
        
        # Botão Procurar da Origem colocado colado na caixa de texto
        self.btn_procurar_origem = ctk.CTkButton(self.frame_grid, text="Procurar...", width=90, command=lambda: self.escolher_pasta(self.entry_pasta_origem))
        self.btn_procurar_origem.grid(row=0, column=2, padx=(5, 15), pady=10)        

        ctk.CTkLabel(self.frame_grid, text="Pasta Destino (Filtro):").grid(row=1, column=0, padx=(15, 5), pady=10, sticky="w")
        self.entry_pasta_destino = ctk.CTkEntry(self.frame_grid, width=450)
        self.entry_pasta_destino.grid(row=1, column=1, padx=5, pady=10, sticky="w")
        
        caminho_pdf_destino = os.path.join(os.path.expanduser("~"), "Área de trabalho","Concursos","PDFs FGV")        
        self.entry_pasta_destino.insert(0, caminho_pdf_destino)
        
        # Botão Procurar do Destino colocado colado na caixa de texto
        self.btn_procurar_destino = ctk.CTkButton(self.frame_grid, text="Procurar...", width=90, command=lambda: self.escolher_pasta(self.entry_pasta_destino))
        self.btn_procurar_destino.grid(row=1, column=2, padx=(5, 15), pady=10)        

        # --- CONTAINER DE BOTÕES DE AÇÃO ---
        # Para que os botões de ação fiquem organizados sem quebrar o alinhamento das colunas de cima,
        # usamos um sub-frame ocupando as colunas combinadas (columnspan)
        self.frame_botoes_acoes = ctk.CTkFrame(self.frame_grid, fg_color="transparent")
        self.frame_botoes_acoes.grid(row=2, column=0, columnspan=3, pady=(10, 15), padx=15, sticky="e")

        self.btn_filtrar = ctk.CTkButton(self.frame_botoes_acoes, text="Separar PDFs por Tipo", fg_color="#2980b9", command=self.separar_pdf_tipo)
        self.btn_filtrar.pack(side="left", padx=5)

        self.btn_filtrar_materias = ctk.CTkButton(self.frame_botoes_acoes, text="Separar Provas por Matérias", fg_color="#e67e22", command=self.separar_prova_materia)
        self.btn_filtrar_materias.pack(side="left", padx=5)

        # REMOVIDO: self.frame_grid.columnconfigure(1, weight=1) para evitar o afastamento automático

        self.txt_log = ctk.CTkTextbox(self, width=700, height=380)
        self.txt_log.pack(padx=20, pady=15, fill="both", expand=True)

    def escolher_pasta(self, widget):
        pasta = filedialog.askdirectory(initialdir=widget.get().strip())
        if pasta:
            widget.delete(0, tk.END)
            widget.insert(0, pasta)

    def bloquear_botoes(self):
        self.btn_filtrar.configure(state="disabled")
        self.btn_filtrar_materias.configure(state="disabled")
        self.txt_log.delete("1.0", tk.END)

    def liberar_botoes(self):
        self.btn_filtrar.configure(state="normal")
        self.btn_filtrar_materias.configure(state="normal")

    def separar_pdf_tipo(self):
        origem = self.entry_pasta_origem.get().strip()
        destino = self.entry_pasta_destino.get().strip()

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
        origem = self.entry_pasta_origem.get().strip()
        destino = self.entry_pasta_destino.get().strip()

        if not origem:
            self.txt_log.insert(tk.END, "⚠️ A pasta de Origem é obrigatória para a separação por matérias.\n")
            return

        self.bloquear_botoes()

        threading.Thread(
            target=PdfSearchService.separar_por_materias, 
            args=(origem, destino, self.callback_thread), 
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