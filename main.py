import threading
import time
import tkinter as tk
from bs4 import BeautifulSoup
import customtkinter as ctk
# Importa a conexão e o repositório de dados
from database import inicializar_banco
from repository import ConcursoRepository
import requests

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class ScraperApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Coletor de Concursos FGV - Pro")
        self.geometry("750x600")

        # --- TÍTULO ---
        self.lbl_titulo = ctk.CTkLabel(
            self,
            text="Rastreador de Concursos FGV (Com Banco de Dados)",
            font=("Arial", 18, "bold"),
        )
        self.lbl_titulo.pack(pady=15)

        # --- FRAME DE CONFIGURAÇÃO ---
        self.frame_config = ctk.CTkFrame(self)
        self.frame_config.pack(padx=20, pady=10, fill="x")

        self.lbl_paginas = ctk.CTkLabel(
            self.frame_config, text="Páginas para varrer:"
        )
        self.lbl_paginas.pack(side="left", padx=10, pady=10)

        self.txt_paginas = ctk.CTkEntry(self.frame_config, width=60)
        self.txt_paginas.insert(0, "3")
        self.txt_paginas.pack(side="left", padx=5, pady=10)

        # --- BOTÃO DE INICIAR ---
        self.btn_iniciar = ctk.CTkButton(
            self, text="Iniciar Coleta", command=self.disparar_coleta
        )
        self.btn_iniciar.pack(pady=10)

        # --- STATUS E PROGRESSO ---
        self.lbl_status = ctk.CTkLabel(
            self, text="Status: Pronto.", font=("Arial", 11, "italic")
        )
        self.lbl_status.pack(pady=2)

        self.progresso = ctk.CTkProgressBar(self, width=400)
        self.progresso.set(0)
        self.progresso.pack(pady=5)

        # --- ÁREA DE TEXTO ---
        self.txt_resultados = ctk.CTkTextbox(self, width=700, height=350)
        self.txt_resultados.pack(padx=20, pady=10, fill="both", expand=True)

    def disparar_coleta(self):
        try:
            max_paginas = int(self.txt_paginas.get())
        except ValueError:
            self.lbl_status.configure(
                text="Erro! Digite um número válido.", text_color="red"
            )
            return

        self.btn_iniciar.configure(state="disabled")
        self.txt_resultados.delete("1.0", tk.END)

        thread = threading.Thread(
            target=self.executar_scraping, args=(max_paginas,), daemon=True
        )
        thread.start()

    def atualizar_interface_safe(self, texto_status, valor_progresso, exibicao_texto=None):
        """Metodo seguro para atualizar componentes visuais a partir de uma Thread."""
        self.lbl_status.configure(text=texto_status)
        self.progresso.set(valor_progresso)
        if exibicao_texto:
            self.txt_resultados.insert(tk.END, exibicao_texto)
            self.txt_resultados.see(tk.END)

    def finalizar_coleta_safe(self, total_novos):
        """Metodo seguro para reativar os botões ao fim da Thread."""
        self.progresso.set(1)
        self.lbl_status.configure(
            text=f"Concluído! {total_novos} novos concursos adicionados ao banco.",
            text_color="green",
        )
        self.btn_iniciar.configure(state="normal")

    def executar_scraping(self, max_paginas):
        base_url = "https://conhecimento.fgv.br"
        url_concursos = f"{base_url}/concursos"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }

        novos_links_contados = 0

        for pagina in range(0, max_paginas):
            progresso_calc = pagina / max_paginas
            status_msg = f"Processando página {pagina + 1} de {max_paginas}..."
            
            # Atualiza progresso via Thread Principal de forma segura
            self.after(0, self.atualizar_interface_safe, status_msg, progresso_calc)

            params = {"page": pagina}

            try:
                resposta = requests.get(
                    url_concursos, params=params, headers=headers, timeout=10
                )
                if resposta.status_code != 200:
                    break

                soup = BeautifulSoup(resposta.text, "html.parser")
                view_content = soup.find("div", class_="view-content")

                if not view_content:
                    break

                links_da_pagina = view_content.find_all("a")
                if not links_da_pagina:
                    break

                for link in links_da_pagina:
                    href = link.get("href")
                    texto_titulo = link.get_text(strip=True)

                    if href:
                        url_completa = (
                            base_url + href if href.startswith("/") else href
                        )

                        foi_salvo = ConcursoRepository.salvar_link(
                            url=url_completa, titulo=texto_titulo
                        )

                        if foi_salvo:
                            novos_links_contados += 1
                            exibicao = f"[NOVO] {texto_titulo}\n🔗 {url_completa}\n\n"
                        else:
                            exibicao = f"[JÁ CADASTRADO] {texto_titulo}\n\n"

                        # Envia o texto gerado para a tela com segurança
                        self.after(0, self.atualizar_interface_safe, status_msg, progresso_calc, exibicao)

                time.sleep(1.2)

            except Exception as e:
                erro_msg = f">> Erro: {e}\n"
                self.after(0, self.atualizar_interface_safe, status_msg, progresso_calc, erro_msg)
                break

        # Finaliza liberando os controles de tela de forma segura
        self.after(0, self.finalizar_coleta_safe, novos_links_contados)


if __name__ == "__main__":
    # Inicializa o arquivo SQLite e cria a tabela antes de abrir a tela
    inicializar_banco()

    app = ScraperApp()
    app.mainloop()