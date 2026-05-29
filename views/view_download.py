import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from services.download_service import DownloadService
from repository.concurso_repo import ConcursoRepository

class ViewDownload(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        # Evento de controle de sincronização da Thread de download
        self.evento_pausa = threading.Event()
        self.evento_pausa.set()  # Inicia no estado "Não Pausado" (permitindo a passagem)
        self.download_em_andamento = False

        # CORREÇÃO: Removida a barra invertida antes de "bold"
        self.lbl_titulo = ctk.CTkLabel(self, text="📥 Baixar Provas / PDFs da Web", font=("Arial", 18, "bold"))
        self.lbl_titulo.pack(pady=15)

        self.frame_dir = ctk.CTkFrame(self)
        self.frame_dir.pack(padx=20, pady=5, fill="x")

        self.lbl_pasta = ctk.CTkLabel(self.frame_dir, text="Pasta de Origem/Salvar PDFs:")
        self.lbl_pasta.pack(side="left", padx=10, pady=10)

        self.txt_pasta = ctk.CTkEntry(self.frame_dir, width=220)
        self.txt_pasta.pack(side="left", padx=5, pady=10, fill="x", expand=True)

        self.btn_procurar = ctk.CTkButton(self.frame_dir, text="Procurar...", width=90, command=self.selecionar_pasta)
        self.btn_procurar.pack(side="left", padx=5, pady=10)

        self.btn_download = ctk.CTkButton(self.frame_dir, text="Baixar Lote", width=100, command=self.disparar_download)
        self.btn_download.pack(side="left", padx=5, pady=10)

        # --- NOVO BOTÃO DE PAUSAR / CONTINUAR ---
        self.btn_pausa = ctk.CTkButton(
            self.frame_dir, 
            text="Pausar", 
            width=100, 
            fg_color="#D97706", 
            hover_color="#B45309", 
            command=self.alternar_pausa,
            state="disabled" # Começa desativado pois não há download rodando
        )
        self.btn_pausa.pack(side="left", padx=5, pady=10)

        self.lbl_status = ctk.CTkLabel(self, text="Status: Aguardando comando...", font=("Arial", 12))
        self.lbl_status.pack(anchor="w", padx=25, pady=5)

        self.progress_bar = ctk.CTkProgressBar(self, width=700)
        self.progress_bar.set(0)
        self.progress_bar.pack(padx=20, pady=5, fill="x")

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

    def alternar_pausa(self):
        if not self.download_em_andamento:
            return

        if self.evento_pausa.is_set():
            # Está rodando, vamos pausar
            self.evento_pausa.clear() # Limpa a flag, forçando o wait() do serviço a travar
            self.btn_pausa.configure(text="Continuar", fg_color="#059669", hover_color="#047857")
            self.txt_log.insert(tk.END, "⏸️ [PAUSADO] O processo será congelado após concluir a requisição atual...\n")
            self.txt_log.see(tk.END)
        else:
            # Está pausado, vamos continuar
            self.evento_pausa.set() # Ativa a flag, liberando o wait() para rodar
            self.btn_pausa.configure(text="Pausar", fg_color="#D97706", hover_color="#B45309")
            self.txt_log.insert(tk.END, "▶️ [RETOMADO] Continuando downloads...\n")
            self.txt_log.see(tk.END)

    def disparar_download(self):
        pasta = self.txt_pasta.get().strip()
        if not pasta:
            # CORREÇÃO: Removida a barra invertida dupla antes do 'n'
            self.txt_log.insert(tk.END, "⚠️ Indique uma pasta local primeiro.\n")
            return

        self.btn_download.configure(state="disabled")
        self.btn_pausa.configure(state="normal") # Ativa o botão de pausar
        # CORREÇÃO: Removidas as barras invertidas de "1.0"
        self.txt_log.delete("1.0", tk.END)
        
        self.download_em_andamento = True
        self.evento_pausa.set() # Garante que inicia despausado
        self.btn_pausa.configure(text="Pausar", fg_color="#D97706", hover_color="#B45309")
        
        threading.Thread(
            target=DownloadService.executar_downloads, 
            args=(pasta, self.callback_thread, self.evento_pausa), 
            daemon=True
        ).start()

    def callback_thread(self, status_msg, progresso, log_msg=None):
        if status_msg is not None:
            self.lbl_status.configure(text=f"Status: {status_msg}")
        if progresso is not None:
            self.progress_bar.set(progresso)
        if log_msg is not None:
            self.txt_log.insert(tk.END, log_msg)
            self.txt_log.see(tk.END)

        # Se a mensagem final de término chegar, reseta os botões
        if status_msg == "Downloads finalizados!":
            self.btn_download.configure(state="normal")
            self.btn_pausa.configure(state="disabled", text="Pausar", fg_color="#D97706")
            self.download_em_andamento = False