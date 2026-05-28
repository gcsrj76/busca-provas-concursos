import os
import shutil

try:
    import pypdf
except ImportError:
    pypdf = None

class PdfSearchService:
    @staticmethod
    def buscar_e_separar(pasta_origem, pasta_filtrados, termo, callback_interface):
        if not pypdf:
            callback_interface("Erro: Instale o pypdf!", 1.0, "Instale executando: pip install pypdf\n")
            return

        if not os.path.exists(pasta_filtrados):
            os.makedirs(pasta_filtrados, exist_ok=True)

        arquivos = [f for f in os.listdir(pasta_origem) if f.lower().endswith(".pdf")]
        total = len(arquivos)

        if total == 0:
            callback_interface("Nenhum PDF encontrado na pasta de origem.", 1.0, "Processamento vazio.\n")
            return

        cont_match = 0
        termo_lower = termo.lower()

        for i, nome_arq in enumerate(arquivos):
            prog = (i + 1) / total
            callback_interface(f"Analisando arquivo {i+1}/{total}...", prog)
            caminho_origem = os.path.join(pasta_origem, nome_arq)
            encontrou = False

            try:
                with open(caminho_origem, "rb") as f:
                    leitor = pypdf.PdfReader(f)
                    for num_pag in range(len(leitor.pages)):
                        texto_pag = leitor.pages[num_pag].extract_text()
                        if texto_pag and termo_lower in texto_pag.lower():
                            encontrou = True
                            break
                
                if encontrou:
                    cont_match += 1
                    shutil.copy2(caminho_origem, os.path.join(pasta_filtrados, nome_arq))
                    callback_interface(None, None, f"🎯 [MATCH & COPIADO] {nome_arq}\n")
                else:
                    callback_interface(None, None, f"⏭️ [NÃO CONTÉM] {nome_arq}\n")
            except Exception as e:
                callback_interface(None, None, f"⚠️ [ERRO LEITURA] {nome_arq}: {e}\n")

        callback_interface("Processamento Concluído!", 1.0, f"\n=== PROCESSO LOCAL FINALIZADO ===\n{cont_match} arquivos movidos com sucesso para a pasta selecionada.\n")