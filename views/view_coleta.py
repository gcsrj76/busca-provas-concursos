import threading
import tkinter as tk
import customtkinter as ctk
from services.scraper_service import ScraperService

class ViewColeta(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.lbl_titulo = ctk.CTkLabel(self, text="🚀 Coletar Dados de Concursos (FGV)", font=("Arial", 18, "bold"))
        self.lbl_titulo.pack(pady=15)

        # --- FRAME DE PARAMETRIZAÇÃO ---
        self.frame_input = ctk.CTkFrame(self)
        self.frame_input.pack(padx=20, pady=5, fill="x")

        # Configuração da Página Inicial
        self.lbl_inicio = ctk.CTkLabel(self.frame_input, text="Página Inicial:")
        self.lbl_inicio.pack(side="left", padx=(15, 5), pady=10)

        self.txt_pag_inicio = ctk.CTkEntry(self.frame_input, width=50)
        self.txt_pag_inicio.insert(0, "1")
        self.txt_pag_inicio.pack(side="left", padx=5, pady=10)

        # Configuração da Página Final
        self.lbl_fim = ctk.CTkLabel(self.frame_input, text="Página Final:")
        self.lbl_fim.pack(side="left", padx=(15, 5), pady=10)

        self.txt_pag_fim = ctk.CTkEntry(self.frame_input, width=50)
        self.txt_pag_fim.insert(0, "1")
        self.txt_pag_fim.pack(side="left", padx=5, pady=10)

        # Botão de Ação alinhado à direita
        self.btn_iniciar = ctk.CTkButton(self.frame_input, text="Iniciar Coleta", command=self.disparar_coleta, fg_color="#1c7ed6")
        self.btn_iniciar.pack(side="right", padx=15, pady=10)

        # --- ÁREA DE LOGS ---
        self.txt_log = ctk.CTkTextbox(self, width=700, height=450)
        self.txt_log.pack(padx=20, pady=15, fill="both", expand=True)

    def disparar_coleta(self):
        try:
            pag_inicial = int(self.txt_pag_inicio.get())
            pag_final = int(self.txt_pag_fim.get())
            
            if pag_inicial < 0 or pag_final < 0:
                raise ValueError("As páginas devem ser valores positivos.")
                
        except ValueError:
            self.txt_log.delete("1.0", tk.END)
            self.txt_log.insert(tk.END, "⚠️ Erro: Insira números válidos e maiores que zero para as páginas inicial e final!\n")
            return

        self.btn_iniciar.configure(state="disabled")
        self.txt_log.delete("1.0", tk.END)
        self.master.master.atualizar_status(f"Iniciando varredura da página {pag_inicial} até {pag_final}...", 0)

        # Dispara a Thread passando as duas variáveis coletadas da interface gráfica
        threading.Thread(
            target=ScraperService.executar_coleta, 
            args=(pag_inicial, pag_final, self.callback_thread), 
            daemon=True
        ).start()

    def callback_thread(self, status_msg, progresso, log_msg=None):
        if status_msg is not None:
            self.master.master.atualizar_status(status_msg, progresso)
        if log_msg:
            self.txt_log.insert(tk.END, log_msg)
            self.txt_log.see(tk.END)
        if progresso == 1.0:
            self.btn_iniciar.configure(state="normal")