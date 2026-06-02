import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from services.gemini_service import GeminiService
import os

class ViewExtracao(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        # Título da Tela
        self.label_titulo = ctk.CTkLabel(
            self, text="Extração Inteligente (Gemini API)", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label_titulo.pack(pady=(20, 10), padx=20, anchor="w")
        
        # Card/Frame para Seleção da Pasta
        self.frame_inputs = ctk.CTkFrame(self)
        self.frame_inputs.pack(fill="x", padx=20, pady=10)
        
        self.label_pasta = ctk.CTkLabel(self.frame_inputs, text="Diretório dos PDFs de Provas:")
        self.label_pasta.pack(padx=10, pady=(10, 2), anchor="w")

        self.entry_pasta = ctk.CTkEntry(self.frame_inputs, placeholder_text="Selecione a pasta onde estão os arquivos PDFs...")
        self.entry_pasta.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=(0, 15))
        
        caminho_linux = os.path.join(os.path.expanduser("~"), "Downloads", "selecionadas")
        self.entry_pasta.insert(0, caminho_linux)
       
        self.btn_procurar = ctk.CTkButton(self.frame_inputs, text="Procurar", width=100, command=self._selecionar_pasta)
        self.btn_procurar.pack(side="right", padx=(5, 10), pady=(0, 15))
        
        # Campo para as restrições do Gemini
        self.frame_restricoes = ctk.CTkFrame(self)
        self.frame_restricoes.pack(fill="x", padx=20, pady=10)
        
        self.label_restricao = ctk.CTkLabel(self.frame_restricoes, text="Filtro/Restrição de Busca para o Gemini:")
        self.label_restricao.pack(padx=10, pady=(10, 2), anchor="w")
        
        self.entry_restricao = ctk.CTkEntry(self.frame_restricoes, placeholder_text="Ex: Copiar apenas as questões de Língua Portuguesa")
        self.entry_restricao.pack(fill="x", padx=10, pady=(0, 15))
        self.entry_restricao.insert(0, "Copiar apenas as questões de Língua Portuguesa") # Valor padrão confortável
        
        # Monitoramento de Progresso e Logs
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=20, pady=15)
        self.progress_bar.set(0)
        
        self.txt_log = ctk.CTkTextbox(self, height=200)
        self.txt_log.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Botão de Execução - Gemini
        self.btn_disparar_gemini = ctk.CTkButton(
            self, text="Iniciar Processamento Gemini", 
            fg_color="#2c3e50", hover_color="#34495e",
            command=self._iniciar_extracao_gemini_thread
        )
        self.btn_disparar_gemini.pack(fill="x", padx=20, pady=(10, 5))

        # Botão de Execução - Manual
        self.btn_disparar_manual = ctk.CTkButton(
            self, text="Iniciar Processamento Manual", 
            fg_color="#2c3e50", hover_color="#34495e",
            command=self._iniciar_extracao_manual_thread
        )
        self.btn_disparar_manual.pack(fill="x", padx=20, pady=(5, 20))        

    def _selecionar_pasta(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.entry_pasta.delete(0, tk.END)
            self.entry_pasta.insert(0, pasta)

    def _iniciar_extracao_gemini_thread(self):
        pasta = self.entry_pasta.get().strip()
        restricao = self.entry_restricao.get().strip()
        
        if not pasta:
            self._atualizar_interface("Erro: Selecione a pasta com os PDFs antes de continuar.", 0)
            return
            
        self.btn_disparar_gemini.configure(state="disabled")
        self.btn_disparar_manual.configure(state="disabled")
        self.btn_procurar.configure(state="disabled")
        self.txt_log.delete("1.0", tk.END)
        
        # Dispara em uma Thread dedicada para manter a interface CustomTkinter fluida
        threading.Thread(
            target=GeminiService.executar_extracao_questoes,
            args=(pasta, self._atualizar_interface_temp),
            daemon=True
        ).start()

    def _iniciar_extracao_manual_thread(self):
        pasta = self.entry_pasta.get().strip()
        
        if not pasta:
            self._atualizar_interface("Erro: Selecione a pasta com os PDFs antes de continuar.", 0)
            return
            
        self.btn_disparar_gemini.configure(state="disabled")
        self.btn_disparar_manual.configure(state="disabled")
        self.btn_procurar.configure(state="disabled")
        self.txt_log.delete("1.0", tk.END)
        
        # Dispara passando apenas os 2 parâmetros esperados por executar_extracao_manual
        threading.Thread(
            target=GeminiService.executar_extracao_manual,
            args=(pasta, self._atualizar_interface),
            daemon=True
        ).start()

    def _atualizar_interface_temp(self, mensagem, log_adicional=None):
        # Garante a atualização segura dos componentes Tkinter a partir de outra Thread
        self.after(0, self._processar_atualizacao_temp, mensagem, log_adicional)

    def _processar_atualizacao_temp(self, mensagem, log_adicional):
        self.txt_log.insert(tk.END, f"[{mensagem}]\n")
        if log_adicional:
            self.txt_log.insert(tk.END, log_adicional)
        self.txt_log.see(tk.END)       

    def _atualizar_interface(self, mensagem, progresso, log_adicional=None):
        # Garante a atualização segura dos componentes Tkinter a partir de outra Thread
        self.after(0, self._processar_atualizacao, mensagem, progresso, log_adicional)

    def _processar_atualizacao(self, mensagem, progresso, log_adicional):
        self.progress_bar.set(progresso)
        self.txt_log.insert(tk.END, f"[{mensagem}]\n")
        if log_adicional:
            self.txt_log.insert(tk.END, log_adicional)
        self.txt_log.see(tk.END)
        
        if progresso >= 1.0:
            self.btn_disparar_gemini.configure(state="normal")
            self.btn_disparar_manual.configure(state="normal")
            self.btn_procurar.configure(state="normal")