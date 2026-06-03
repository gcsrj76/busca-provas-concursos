import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from services.gemini_service import GeminiService
from services.pdf_search_service import PdfSearchService  # Importado para acessar a nova rotina
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
        
        # Campo para as restrições do Gemini / Termo Manual
        self.frame_restricoes = ctk.CTkFrame(self)
        self.frame_restricoes.pack(fill="x", padx=20, pady=10)
        
        self.label_restricao = ctk.CTkLabel(self.frame_restricoes, text="Filtro/Restrição de Busca (Matéria Inicial):")
        self.label_restricao.pack(padx=10, pady=(10, 2), anchor="w")
        
        self.entry_restricao = ctk.CTkEntry(self.frame_restricoes, placeholder_text="Ex: Língua Portuguesa")
        self.entry_restricao.pack(fill="x", padx=10, pady=(0, 15))
        self.entry_restricao.insert(0, "Língua Portuguesa") # Valor padrão confortável e exato para a capitulação
        
        # Monitoramento de Progresso e Logs
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=20, pady=15)
        self.progress_bar.set(0)
        
        self.txt_log = ctk.CTkTextbox(self, height=150)
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
        self.btn_disparar_manual.pack(fill="x", padx=20, pady=(5, 5))        

        # NOVO BOTÃO: Extrair JSON
        self.btn_extrair_json = ctk.CTkButton(
            self, text="Extrair JSON", 
            fg_color="#e67e22", hover_color="#d35400",
            command=self._iniciar_conversao_json_thread
        )
        self.btn_extrair_json.pack(fill="x", padx=20, pady=(5, 20))

    def _selecionar_pasta(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.entry_pasta.delete(0, tk.END)
            self.entry_pasta.insert(0, pasta)

    def _bloquear_componentes(self):
        self.btn_disparar_gemini.configure(state="disabled")
        self.btn_disparar_manual.configure(state="disabled")
        self.btn_extrair_json.configure(state="disabled")
        self.btn_procurar.configure(state="disabled")
        self.txt_log.delete("1.0", tk.END)

    def _liberar_componentes(self):
        self.btn_disparar_gemini.configure(state="normal")
        self.btn_disparar_manual.configure(state="normal")
        self.btn_extrair_json.configure(state="normal")
        self.btn_procurar.configure(state="normal")

    def _iniciar_extracao_gemini_thread(self):
        pasta = self.entry_pasta.get().strip()
        
        if not pasta:
            self._atualizar_interface("Erro: Selecione a pasta com os PDFs antes de continuar.", 0)
            return
            
        self._bloquear_componentes()
        
        threading.Thread(
            target=GeminiService.executar_extracao_questoes,
            args=(pasta, self._atualizar_interface_temp),
            daemon=True
        ).start()

    def _iniciar_extracao_manual_thread(self):
        pasta = self.entry_pasta.get().strip()
        restricao = self.entry_restricao.get().strip()
        
        if not pasta or not restricao:
            self._atualizar_interface("Erro: A pasta e a Matéria Inicial são obrigatórias.", 0)
            return
            
        self._bloquear_componentes()
        
        threading.Thread(
            target=GeminiService.executar_extracao_manual,
            args=(pasta, restricao, self._atualizar_interface),
            daemon=True
        ).start()

    def _iniciar_conversao_json_thread(self):
        """Abre caixa de diálogo para escolher o arquivo .txt gerado e roda a extração em JSON"""
        caminho_inicial = self.entry_pasta.get().strip()
        if not os.path.exists(caminho_inicial):
            caminho_inicial = os.path.expanduser("~")

        arquivo_txt = filedialog.askopenfilename(
            initialdir=caminho_inicial,
            title="Selecione o arquivo TXT gerado na extração manual",
            filetypes=[("Arquivos de Texto", "*.txt"), ("Todos os arquivos", "*.*")]
        )

        if not arquivo_txt:
            return

        # Define automaticamente o nome do arquivo JSON de saída no mesmo diretório
        diretorio_pai = os.path.dirname(arquivo_txt)
        arquivo_json_saida = os.path.join(diretorio_pai, "importacao_final.json")

        self._bloquear_componentes()
        self.progress_bar.set(0.5)
        self.txt_log.insert(tk.END, f"[Iniciando processamento do arquivo estruturado para JSON...]\n")

        # Função interna que rodará na Thread secundária
        def worker():
            try:
                GeminiService.extrair_questoes_para_json_adequado(arquivo_txt, arquivo_json_saida)
                # Sincroniza com a Main Thread para atualizar o sucesso
                self.after(0, self._atualizar_interface, "Conversão JSON Concluída!", 1.0, 
                           f"✅ Arquivo JSON gerado com absoluto sucesso!\nSalvo em: {arquivo_json_saida}\n")
            except Exception as ex:
                # CORREÇÃO: Extraímos a string do erro antes de despachar para o loop de eventos da interface
                erro_msg = str(ex)
                self.after(0, self._atualizar_interface, "Erro na conversão", 1.0, f"❌ Falha crítica: {erro_msg}\n")

        threading.Thread(target=worker, daemon=True).start()

    def _atualizar_interface_temp(self, mensagem, log_adicional=None):
        self.after(0, self._processar_atualizacao_temp, mensagem, log_adicional)

    def _processar_atualizacao_temp(self, mensagem, log_adicional):
        self.txt_log.insert(tk.END, f"[{mensagem}]\n")
        if log_adicional:
            self.txt_log.insert(tk.END, log_adicional)
        self.txt_log.see(tk.END)       

    def _atualizar_interface(self, mensagem, progresso, log_adicional=None):
        self.after(0, self._processar_atualizacao, mensagem, progresso, log_adicional)

    def _processar_atualizacao(self, mensagem, progresso, log_adicional):
        self.progress_bar.set(progresso)
        if mensagem:
            self.txt_log.insert(tk.END, f"[{mensagem}]\n")
        if log_adicional:
            self.txt_log.insert(tk.END, log_adicional)
        self.txt_log.see(tk.END)
        
        if progresso >= 1.0:
            self._liberar_componentes()