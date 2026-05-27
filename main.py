import threading
import time
import tkinter as tk
from bs4 import BeautifulSoup
import customtkinter as ctk
import requests

# Configuração visual do tema da interface
ctk.set_appearance_mode("System")  # Segue o tema do sistema (Dark ou Light)
ctk.set_default_color_theme("blue")  # Tema de cor dos botões


class ScraperApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        # Configurações da Janela Principal
        self.title("Coletor de Concursos FGV")
        self.geometry("700x550")
        self.minsize(600, 450)

        # --- TÍTULO ---
        self.lbl_titulo = ctk.CTkLabel(
            self, text="Rastreador de Concursos FGV", font=("Arial", 20, "bold")
        )
        self.lbl_titulo.pack(pady=15)

        # --- FRAME DE CONFIGURAÇÃO (Campos de entrada) ---
        self.frame_config = ctk.CTkFrame(self)
        self.frame_config.pack(padx=20, pady=10, fill="x")

        # Rótulo e Campo para quantidade de páginas
        self.lbl_paginas = ctk.CTkLabel(
            self.frame_config,
            text="Quantidade de páginas para varrer:",
            font=("Arial", 12),
        )
        self.lbl_paginas.pack(side="left", padx=10, pady=10)

        self.txt_paginas = ctk.CTkEntry(self.frame_config, width=60)
        self.txt_paginas.insert(0, "3")  # Valor padrão
        self.txt_paginas.pack(side="left", padx=5, pady=10)

        # --- BOTÃO DE INICIAR ---
        self.btn_iniciar = ctk.CTkButton(
            self, text="Iniciar Coleta", command=self.disparar_coleta
        )
        self.btn_iniciar.pack(pady=10)

        # --- BARRA DE PROGRESSO E STATUS ---
        self.lbl_status = ctk.CTkLabel(
            self,
            text="Status: Aguardando comando...",
            font=("Arial", 11, "italic"),
        )
        self.lbl_status.pack(pady=2)

        self.progresso = ctk.CTkProgressBar(self, width=400)
        self.progresso.set(0)
        self.progresso.pack(pady=5)

        # --- ÁREA DE TEXTO (RESULTADOS) ---
        self.txt_resultados = ctk.CTkTextbox(self, width=650, height=300)
        self.txt_resultados.pack(padx=20, pady=10, fill="both", expand=True)

    def disparar_coleta(self):
        """Dispara a raspagem em uma Thread separada para a interface não travar."""
        try:
            max_paginas = int(self.txt_paginas.get())
        except ValueError:
            self.lbl_status.configure(
                text="Status: Erro! Digite um número válido de páginas.",
                text_color="red",
            )
            return

        # Bloqueia o botão para evitar cliques duplos durante a execução
        self.btn_iniciar.configure(state="disabled")
        self.txt_resultados.delete("1.0", tk.END)

        # Criar uma Thread secundária
        thread = threading.Thread(
            target=self.executar_scraping, args=(max_paginas,)
        )
        thread.start()

    def executar_scraping(self, max_paginas):
        base_url = "https://conhecimento.fgv.br"
        url_concursos = f"{base_url}/concursos"
        lista_links_completa = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        for pagina in range(0, max_paginas):
            # Atualiza a interface (Progresso e Mensagem)
            progresso_atual = (pagina) / max_paginas
            self.progresso.set(progresso_atual)
            self.lbl_status.configure(
                text=f"Status: Coletando dados da página {pagina + 1} de {max_paginas}...",
                text_color=("black", "white"),
            )

            params = {"page": pagina}

            try:
                resposta = requests.get(
                    url_concursos, params=params, headers=headers, timeout=10
                )

                if resposta.status_code != 200:
                    self.txt_resultados.insert(
                        tk.END,
                        f">> Fim das páginas ou erro na pág {pagina+1} (Status {resposta.status_code})\n",
                    )
                    break

                soup = BeautifulSoup(resposta.text, "html.parser")
                view_content = soup.find("div", class_="view-content")

                if not view_content:
                    self.txt_resultados.insert(
                        tk.END,
                        f">> Nenhum conteúdo encontrado na página {pagina+1}.\n",
                    )
                    break

                links_da_pagina = view_content.find_all("a")

                if not links_da_pagina:
                    break

                for link in links_da_pagina:
                    href = link.get("href")
                    if href:
                        url_completa = (
                            base_url + href if href.startswith("/") else href
                        )

                        if url_completa not in lista_links_completa:
                            lista_links_completa.append(url_completa)
                            # Adiciona o link em tempo real na tela do usuário
                            self.txt_resultados.insert(
                                tk.END, f"{url_completa}\n"
                            )
                            self.txt_resultados.see(tk.END)

                time.sleep(1.2)

            except Exception as e:
                self.txt_resultados.insert(
                    tk.END, f">> Erro na página {pagina}: {e}\n"
                )
                break

        # Finalização da busca
        self.progresso.set(1)
        self.lbl_status.configure(
            text=f"Status: Concluído! {len(lista_links_completa)} links encontrados.",
            text_color="green",
        )
        self.btn_iniciar.configure(state="normal")


# Executa o aplicativo
if __name__ == "__main__":
    app = ScraperApp()
    app.mainloop()