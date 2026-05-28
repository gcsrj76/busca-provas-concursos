import tkinter as tk
import customtkinter as ctk
from repository.concurso_repo import ConcursoRepository

class ViewHome(ctk.CTkFrame):
    """Tela Principal que exibe apenas dados consolidados e histórico salvo no banco."""
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.lbl_titulo = ctk.CTkLabel(self, text="🏛️ Painel Geral de Concursos Coletados", font=("Arial", 18, "bold"))
        self.lbl_titulo.pack(pady=15)

        self.frame_resumo = ctk.CTkFrame(self)
        self.frame_resumo.pack(padx=20, pady=10, fill="x")

        self.lbl_cont_concursos = ctk.CTkLabel(self.frame_resumo, text="Concursos Mapeados: 0", font=("Arial", 12, "bold"))
        self.lbl_cont_concursos.pack(side="left", padx=20, pady=10)

        self.lbl_cont_provas = ctk.CTkLabel(self.frame_resumo, text="Links de Provas Mapeados: 0", font=("Arial", 12, "bold"))
        self.lbl_cont_provas.pack(side="right", padx=20, pady=10)

        self.txt_historico = ctk.CTkTextbox(self, width=700, height=450)
        self.txt_historico.pack(padx=20, pady=15, fill="both", expand=True)

        self.atualizar_dados_painel()

    def atualizar_dados_painel(self):
        self.txt_historico.delete("1.0", tk.END)
        concursos = ConcursoRepository.listar_todos()
        
        self.lbl_cont_concursos.configure(text=f"Concursos Mapeados: {len(concursos)}")
        self.lbl_cont_provas.configure(text=f"Links de Provas Mapeados: {ConcursoRepository.contar_arquivos_provas()}")

        if concursos:
            self.txt_historico.insert(tk.END, "=== HISTÓRICO ATUALIZADO DO BANCO DE DADOS ===\n\n")
            for c in concursos:
                bloco = f"• {c.titulo}\n  🔗 URL Base: {c.url}\n"
                if c.arquivos:
                    bloco += f"  📚 Contém {len(c.arquivos)} provas associadas.\n"
                bloco += "\n"
                self.txt_historico.insert(tk.END, bloco)
        else:
            self.txt_historico.insert(tk.END, "O banco de dados está vazio no momento. Use a aba 'Coletar dados' no menu lateral.")