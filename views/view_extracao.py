import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from services.extracao_service import ExtracaoService
from services.pdf_search_service import PdfSearchService  
import os

class ViewExtracao(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        # Título da Tela
        self.label_titulo = ctk.CTkLabel(
            self, text="Extrair Questões das Provas", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label_titulo.pack(pady=(20, 10), padx=20, anchor="w")
        
        # --- CARD/FRAME PARA SELEÇÃO DA PASTA DOS PDFS ---
        self.frame_inputs = ctk.CTkFrame(self)
        self.frame_inputs.pack(fill="x", padx=20, pady=5)
        
        self.label_pasta = ctk.CTkLabel(self.frame_inputs, text="Diretório dos PDFs Provas:")
        self.label_pasta.pack(padx=10, pady=(10, 2), anchor="w")

        self.entry_pasta_prova = ctk.CTkEntry(self.frame_inputs, placeholder_text="Selecione a pasta onde estão os arquivos PDFs...")
        self.entry_pasta_prova.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=(0, 15))
        
        caminho_prova = os.path.join(os.path.expanduser("~"), "Área de trabalho","Concursos","PDFs POR MATÉRIAS")        
        self.entry_pasta_prova.insert(0, caminho_prova)
       
        self.btn_procurar = ctk.CTkButton(self.frame_inputs, text="Procurar", width=100, command=self._selecionar_pasta)
        self.btn_procurar.pack(side="right", padx=(5, 10), pady=(0, 15))
        
        # --- NOVO: CARD/FRAME PARA SELEÇÃO DA PASTA DOS GABARITOS ---
        self.frame_inputs_gabarito = ctk.CTkFrame(self)
        self.frame_inputs_gabarito.pack(fill="x", padx=20, pady=5)
        
        self.label_pasta_gabarito = ctk.CTkLabel(self.frame_inputs_gabarito, text="Diretório para leitura dos Arquivos de Gabaritos:")
        self.label_pasta_gabarito.pack(padx=10, pady=(10, 2), anchor="w")

        self.entry_pasta_gabarito = ctk.CTkEntry(self.frame_inputs_gabarito, placeholder_text="Selecione a pasta onde os arquivos JSONs serão salvos...")
        self.entry_pasta_gabarito.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=(0, 15))
        
        # Inicializa o campo de Gabaritos com o mesmo caminho padrão por conveniência
        caminho_gabarito = os.path.join(os.path.expanduser("~"), "Área de trabalho","Concursos","PDFs FGV","Gabarito")  
        self.entry_pasta_gabarito.insert(0, caminho_gabarito)
        
        self.btn_procurar_gabarito = ctk.CTkButton(self.frame_inputs_gabarito, text="Procurar", width=100, command=self._selecionar_pasta_gabarito)
        self.btn_procurar_gabarito.pack(side="right", padx=(5, 10), pady=(0, 15))
        
        # --- CAMPO PARA AS RESTRIÇÕES DO GEMINI / TERMO MANUAL ---
        self.frame_restricoes = ctk.CTkFrame(self)
        self.frame_restricoes.pack(fill="x", padx=20, pady=10)
        
        # Sub-frame da Esquerda (Combobox de Matéria)
        self.sub_frame_materia = ctk.CTkFrame(self.frame_restricoes, fg_color="transparent")
        self.sub_frame_materia.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        
        self.label_restricao = ctk.CTkLabel(self.sub_frame_materia, text="Filtro/Restrição de Busca (Matéria Inicial):")
        self.label_restricao.pack(anchor="w", pady=(0, 2))
        
        opcoes_materias = [
            "Língua Portuguesa", 
            "Legislação", 
            "Raciocínio Lógico", 
            "Informática", 
            "Analista de Tecnologia", 
            "Conhecimentos Específicos",
            "Noções de Informática" 
        ]
        
        self.entry_restricao = ctk.CTkComboBox(self.sub_frame_materia, values=opcoes_materias)
        self.entry_restricao.pack(fill="x", pady=(0, 5))
        self.entry_restricao.set("Língua Portuguesa")
        
        # Sub-frame da Direita (Número de Blocos)
        self.sub_frame_blocos = ctk.CTkFrame(self.frame_restricoes, fg_color="transparent")
        self.sub_frame_blocos.pack(side="right", padx=10, pady=10)
        
        self.label_blocos = ctk.CTkLabel(self.sub_frame_blocos, text="Número de Blocos:")
        self.label_blocos.pack(anchor="w", pady=(0, 2))
        
        self.entry_blocos = ctk.CTkEntry(self.sub_frame_blocos, placeholder_text="Ex: 5", width=120)
        self.entry_blocos.pack(fill="x", pady=(0, 5))
        
        # Monitoramento de Progresso e Logs
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=20, pady=15)
        self.progress_bar.set(0)
        
        self.txt_log = ctk.CTkTextbox(self, height=150)
        self.txt_log.pack(fill="both", expand=True, padx=20, pady=10)
        
        # BOTÃO ÚNICO ATIVO
        self.btn_extrair_json = ctk.CTkButton(
            self, text="Extrair JSON", 
            fg_color="#e67e22", hover_color="#d35400",
            command=self._extrair_json_thread
        )
        self.btn_extrair_json.pack(fill="x", padx=20, pady=(5, 20))

    def _selecionar_pasta(self):
        pasta = filedialog.askdirectory(initialdir=self.entry_pasta_prova.get().strip())
        if pasta:
            self.entry_pasta_prova.delete(0, tk.END)
            self.entry_pasta_prova.insert(0, pasta)

    def _selecionar_pasta_gabarito(self):
        pasta = filedialog.askdirectory(initialdir=self.entry_pasta_gabarito.get().strip())
        if pasta:
            self.entry_pasta_gabarito.delete(0, tk.END)
            self.entry_pasta_gabarito.insert(0, pasta)

    def _bloquear_componentes(self):
        self.btn_extrair_json.configure(state="disabled")
        self.btn_procurar.configure(state="disabled")
        self.btn_procurar_gabarito.configure(state="disabled")
        self.entry_pasta_gabarito.configure(state="disabled")
        self.entry_restricao.configure(state="disabled")
        self.entry_blocos.configure(state="disabled")
        self.txt_log.delete("1.0", tk.END)

    def _liberar_componentes(self):
        self.btn_extrair_json.configure(state="normal")
        self.btn_procurar.configure(state="normal")
        self.btn_procurar_gabarito.configure(state="normal")
        self.entry_pasta_gabarito.configure(state="normal")
        self.entry_restricao.configure(state="normal")
        self.entry_blocos.configure(state="normal")

    def _extrair_json_thread(self):
        pasta_prova = self.entry_pasta_prova.get().strip()
        pasta_gabarito = self.entry_pasta_gabarito.get().strip()
        materia = self.entry_restricao.get().strip()
        blocos_str = self.entry_blocos.get().strip()
        
        if not pasta_prova or not pasta_gabarito or not materia:
            self._atualizar_interface("Erro: A pasta de provas, de gabaritos e a Matéria Inicial são obrigatórias.", 0)
            return     

        # Validação do tamanho do lote/bloco (padrão 1 caso o usuário não defina)
        try:
            tamanho_bloco = int(blocos_str) if blocos_str else 1
            if tamanho_bloco <= 0:
                tamanho_bloco = 1
        except ValueError:
            tamanho_bloco = 1

        self._bloquear_componentes()
        self.progress_bar.set(0.0)
        self.txt_log.insert(tk.END, f"[Iniciando pipeline de processamento e conversão estruturada...]\n")

        def worker():
            try:
                ExtracaoService.extrair_questoes_json(pasta_prova, pasta_gabarito, materia, tamanho_bloco, self._atualizar_interface)
            except Exception as ex:
                erro_msg = str(ex)
                self.after(0, self._atualizar_interface, "Erro no processamento", 1.0, f"❌ Falha crítica: {erro_msg}\n")

        threading.Thread(target=worker, daemon=True).start()

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