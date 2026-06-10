import customtkinter as ctk
from views.view_home import ViewHome
from views.view_coleta import ViewColeta
from views.view_busca import ViewBusca
from views.view_download import ViewDownload
from views.view_processar import ViewProcessar
from views.view_extracao import ViewExtracao
from repository.concurso_repo import ConcursoRepository

class ScraperApp(ctk.CTk):
    """Atua como a Janela Principal unificada controlando as sub-views."""
    def __init__(self):
        super().__init__()

        ConcursoRepository.gerar_listagem_provisoria_descricoes()

        self.title("Monitor Avançado Corporativo - FGV Pro")
        self.geometry("980x700")

        # --- MENU LATERAL DE NAVEGAÇÃO ---
        self.frame_menu = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.frame_menu.pack(side="left", fill="y", ipadx=5)

        self.lbl_menu_titulo = ctk.CTkLabel(self.frame_menu, text="MENU NAV", font=("Arial", 14, "bold"))
        self.lbl_menu_titulo.pack(pady=20, padx=10)

        # Botões de controle de Abas
        self.criar_botao_menu("🏠 Início / Painel", lambda: self.mudar_tela("home"))
        self.criar_botao_menu("🚀 Coletar Dados", lambda: self.mudar_tela("coleta"))
        self.criar_botao_menu("🔍 Buscar PDFs", lambda: self.mudar_tela("busca"))
        self.criar_botao_menu("📥 Baixar PDFs", lambda: self.mudar_tela("download"))
        self.criar_botao_menu("⚙️ Processar PDFs", lambda: self.mudar_tela("processar"))
        # <--- 2. AJUSTE: Novo botão adicionado de forma independente no menu lateral
        self.criar_botao_menu("🤖 Extrair Questões", lambda: self.mudar_tela("extracao"))

        # --- BARRA INFERIOR DE STATUS ---
        self.frame_status = ctk.CTkFrame(self, height=35, corner_radius=0)
        self.frame_status.pack(side="bottom", fill="x")

        self.lbl_status = ctk.CTkLabel(self.frame_status, text="Status: Pronto.", font=("Arial", 11, "italic"))
        self.lbl_status.pack(side="left", padx=15, pady=5)

        self.barra_progresso = ctk.CTkProgressBar(self.frame_status, width=250)
        self.barra_progresso.set(0)
        self.barra_progresso.pack(side="right", padx=15, pady=10)

        # --- ÁREA CENTRAL DINÂMICA DE VISUALIZAÇÕES ---
        self.container_telas = ctk.CTkFrame(self, fg_color="transparent")
        self.container_telas.pack(side="right", fill="both", expand=True)

        # Inicializa o dicionário mapeando as classes instanciadas
        self.telas = {}
        self.instanciar_telas()
        
        # Exibe por padrão a tela inicial
        self.mudar_tela("home")

    def criar_botao_menu(self, texto, comando):
        btn = ctk.CTkButton(self.frame_menu, text=texto, anchor="w", fg_color="transparent", text_color=("black", "white"), hover_color=("gray70", "gray30"), command=comando)
        btn.pack(fill="x", padx=10, pady=5)

    def instanciar_telas(self):
        self.telas["home"] = ViewHome(self.container_telas)
        self.telas["coleta"] = ViewColeta(self.container_telas)
        self.telas["busca"] = ViewBusca(self.container_telas)
        self.telas["download"] = ViewDownload(self.container_telas)
        self.telas["processar"] = ViewProcessar(self.container_telas)
        # <--- 3. AJUSTE: Registra a nova View acoplada no mesmo container central
        self.telas["extracao"] = ViewExtracao(self.container_telas)

    def mudar_tela(self, chave_tela):
        # Oculta todas as views de uma vez só
        for t in self.telas.values():
            t.pack_forget()
        
        # Recarrega ou atualiza indicadores numéricos das telas dependentes do banco antes de abrir
        if chave_tela == "home":
            self.telas["home"].atualizar_dados_painel()
        elif chave_tela == "busca":
            self.telas["busca"].atualizar_contagem()
        elif chave_tela == "download":
            self.telas["download"].atualizar_contador_links()

        # Exibe a tela desejada
        self.telas[chave_tela].pack(fill="both", expand=True)

    def atualizar_status(self, mensagem, progresso=None):
        if mensagem:
            self.lbl_status.configure(text=f"Status: {mensagem}")
        if progresso is not None:
            self.barra_progresso.set(progresso)