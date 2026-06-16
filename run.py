from database.connection import inicializar_banco
from views.main_activity import ScraperApp

if __name__ == "__main__":
    # Inicializa e monta as tabelas do SQLite automaticamente caso não existam
    inicializar_banco()
    
    # Inicia a aplicação utilizando a nova arquitetura modular por abas internas
    app = ScraperApp()
    app.mainloop()

    # TO DO LIST
    # CORRIGIR (IMPORTAÇÃO) SEPARAÇÃO DE PALAVRAS, INDEVIDAS;
    # CORRIGIR (IMPORTAÇÃO), OUTRAS MATÉRIAS SENDO CARREGADAS;
    # IMPLEMENTAR LEITURA/CAPTURA DE IMAGENS NA IMPORTAÇÃO;