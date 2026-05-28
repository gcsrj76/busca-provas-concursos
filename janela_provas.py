import os
import threading
import time
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
import requests
# Certifique-se de importar o seu repositório para ler os links salvos
from repository import ConcursoRepository


class JanelaResultadosProvas(ctk.CTkToplevel):
    """Janela separada para exibir os resultados e gerenciar os PDFs das provas."""

    def __init__(self, parent, texto_inicial=""):
        super().__init__(parent)
        self.parent = parent  # Referência do app principal

        self.title("Resultados da Verificação de Provas")
        self.geometry("750x650")  # Aumentado levemente para acomodar os novos controles

        # Garante foco na tela ao abrir
        self.lift()
        self.focus_force()

        # --- TÍTULO ---
        self.lbl_titulo = ctk.CTkLabel(
            self, text="Provas Objetivas Encontradas", font=("Arial", 16, "bold")
        )
        self.lbl_titulo.pack(pady=10)

        # --- FRAME DE CONTROLES DE DIRETÓRIO E PARÂMETROS ---
        self.frame_inputs = ctk.CTkFrame(self)
        self.frame_inputs.pack(padx=20, pady=5, fill="x")

        # Entrada de Pasta
        self.lbl_pasta = ctk.CTkLabel(self.frame_inputs, text="Pasta Destino/PDFs:")
        self.lbl_pasta.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.txt_pasta = ctk.CTkEntry(self.frame_inputs, width=450)
        self.txt_pasta.insert(0, os.path.abspath("./downloads_provas"))
        self.txt_pasta.grid(row=0, column=1, padx=5, pady=5)

        self.btn_procurar = ctk.CTkButton(
            self.frame_inputs, text="Selecionar...", width=100, command=self.selecionar_pasta
        )
        self.btn_procurar.grid(row=0, column=2, padx=5, pady=5)

        # Entrada de Termo de Busca Local
        self.lbl_termo = ctk.CTkLabel(self.frame_inputs, text="Termo p/ buscar nos PDFs:")
        self.lbl_termo.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.txt_termo = ctk.CTkEntry(self.frame_inputs, width=450, placeholder_text="Ex: Direito Administrativo")
        self.txt_termo.grid(row=1, column=1, padx=5, pady=5, columnspan=2, sticky="w")

        # --- FRAME DOS BOTÕES DE AÇÃO ---
        self.frame_botoes_acao = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_botoes_acao.pack(padx=20, pady=5, fill="x")

        # NOVO BOTÃO: Download de PDFs (Fica acima do processamento)
        self.btn_download = ctk.CTkButton(
            self.frame_botoes_acao,
            text="📥 Downloads PDFs",
            command=self.disparar_download,
            fg_color="#1c7ed6",
            hover_color="#1a72c4",
            width=220
        )
        self.btn_download.pack(pady=3)

        # Botão: Iniciar Processamento Local
        self.btn_processar = ctk.CTkButton(
            self.frame_botoes_acao,
            text="⚙️ Iniciar Processamento de PDFs Locais",
            command=self.acionar_processamento_local,
            fg_color="#e67e22",
            hover_color="#d35400",
            width=220
        )
        self.btn_processar.pack(pady=3)

        # --- ÁREA DE TEXTO DOS LOGS ---
        self.txt_provas = ctk.CTkTextbox(self, width=700, height=350)
        self.txt_provas.pack(padx=20, pady=10, fill="both", expand=True)

        if texto_inicial:
            self.txt_provas.insert(tk.END, texto_inicial)
            self.txt_provas.see(tk.END)

    def adicionar_texto(self, texto):
        """Insere textos no console da janela secundária."""
        self.txt_provas.insert(tk.END, texto)
        self.txt_provas.see(tk.END)

    def selecionar_pasta(self):
        pasta_selecionada = filedialog.askdirectory()
        if pasta_selecionada:
            self.txt_pasta.delete(0, tk.END)
            self.txt_pasta.insert(0, pasta_selecionada)

    # --- FLUXO DE DOWNLOAD ASSÍNCRONO ---
    def disparar_download(self):
        pasta_destino = self.txt_pasta.get().strip()
        if not pasta_destino:
            self.adicionar_texto("⚠️ Erro: Informe uma pasta destino válida para os downloads.\n")
            return

        self.btn_download.configure(state="disabled")
        self.adicionar_texto("=== INICIANDO EXPORTAÇÃO E DOWNLOAD DOS LINKS DISPONÍVEIS ===\n")
        
        # Dispara a Thread para não travar o CustomTkinter durante os downloads de rede
        threading.Thread(target=self.executar_downloads_infra, args=(pasta_destino,), daemon=True).start()

    def executar_downloads_infra(self, pasta_destino):
        # Cria o diretório caso ele não exista fisicamente
        os.makedirs(pasta_destino, exist_ok=True)

        # Acessa todos os concursos para ler as provas correspondentes guardadas no banco
        concursos = ConcursoRepository.listar_todos()
        
        # Coleta todos os arquivos de prova vinculados aos concursos salvos
        arquivos_para_baixar = []
        for c in concursos:
            if hasattr(c, 'arquivos') and c.arquivos:
                for arq in c.arquivos:
                    arquivos_para_baixar.append(arq)

        total_arquivos = len(arquivos_para_baixar)

        if total_arquivos == 0:
            self.adicionar_texto("⚠️ Nenhum link de prova novo foi encontrado no banco de dados para baixar.\n")
            self.parent.after(0, lambda: self.btn_download.configure(state="normal"))
            return

        self.adicionar_texto(f"Encontrados {total_arquivos} arquivos mapeados. Iniciando downloads...\n\n")
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        baixados_sucesso = 0

        for idx, arquivo in enumerate(arquivos_para_baixar, start=1):
            msg_status = f"Baixando arquivo {idx} de {total_arquivos}..."
            # Atualiza o status na barra da tela principal usando o escalonador do ciclo principal
            self.parent.after(0, self.parent.lbl_status.configure, {"text": msg_status})

            url_alvo = arquivo.url_arquivo
            
            # Sanitiza o nome do arquivo limpando caracteres inválidos para o sistema operacional
            nome_limpo = "".join([c for c in arquivo.descricao if c.isalnum() or c in (" ", "-", "_")]).strip()
            nome_arquivo = f"{nome_limpo}.pdf".replace(" ", "_")
            caminho_salvamento = os.path.join(pasta_destino, nome_arquivo)

            # Verifica se o arquivo já foi baixado anteriormente para evitar download redundante
            if os.path.exists(caminho_salvamento):
                self.adicionar_texto(f"✅ [JÁ EXISTE LOCAL] {nome_arquivo}\n")
                baixados_sucesso += 1
                continue

            try:
                resposta = requests.get(url_alvo, headers=headers, timeout=25, stream=True)
                if resposta.status_code == 200:
                    with open(caminho_salvamento, "wb") as f:
                        for chunk in resposta.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    self.adicionar_texto(f"📥 [DOWNLOAD COMPLETO] {nome_arquivo}\n")
                    baixados_sucesso += 1
                else:
                    self.adicionar_texto(f"❌ [ERRO {resposta.status_code}] Falha ao baixar: {nome_arquivo}\n")
                
                time.sleep(0.5)  # Delay preventivo leve para evitar bloqueio do servidor da banca
            except Exception as e:
                self.adicionar_texto(f"⚠️ [FALHA DE CONEXÃO] Erro em {nome_arquivo}: {e}\n")

        self.adicionar_texto(f"\n=== DOWNLOADS CONCLUÍDOS ===\nSucesso: {baixados_sucesso} de {total_arquivos} arquivos salvos na pasta.\n\n")
        self.parent.after(0, lambda: self.btn_download.configure(state="normal"))
        self.parent.after(0, self.parent.lbl_status.configure, {"text": "Status: Downloads de PDFs concluídos."})

    # --- FLUXO DE EXECUÇÃO LOCAL (PYPDF) ---
    def acionar_processamento_local(self):
        pasta = self.txt_pasta.get().strip()
        termo = self.txt_termo.get().strip()
        # Repassa o comando com segurança para o core da aplicação principal gerenciar
        self.parent.iniciar_processamento_arquivos(pasta, termo)

    def executar_busca_local(self, pasta, termo):
        """Aqui você pode colar a rotina de varredura PyPDF que desenvolvemos anteriormente"""
        # Nota: Lembre-se que no fim desta rotina você deve reativar o botão:
        # self.parent.after(0, lambda: self.btn_processar.configure(state="normal"))
        pass