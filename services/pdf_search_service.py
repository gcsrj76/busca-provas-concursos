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

    @staticmethod
    def filtrar_por_padrao_fgv(pasta_origem: str, pasta_filtrados: str, callback_interface) -> None:
        """
        Varre a pasta de origem e copia para a pasta de destino apenas os PDFs que atendem
        a uma das duas assinaturas de capa padrão da FGV na primeira página.
        """
        # Garante a existência da pasta de destino
        if not os.path.exists(pasta_filtrados):
            os.makedirs(pasta_filtrados, exist_ok=True)

        arquivos = [f for f in os.listdir(pasta_origem) if f.lower().endswith(".pdf")]
        total = len(arquivos)

        if total == 0:
            callback_interface("Nenhum PDF encontrado na pasta de origem.", 1.0, "Processamento vazio.\n")
            return

        cont_match = 0
        
        # Definição dos termos de validação
        termos_possibilidade_1 = ["SUA PROVA", "TEMPO", "NÃO SERÁ PERMITIDO", "INFORMAÇÕES GERAIS"]
        termos_possibilidade_2 = ["prova escrita objetiva", "informações gerais"]

        for i, nome_arq in enumerate(arquivos):
            prog = (i + 1) / total
            callback_interface(f"Analisando capa de {i+1}/{total}...", prog, None)
            
            caminho_origem = os.path.join(pasta_origem, nome_arq)
            atende_padrao = False

            try:
                with open(caminho_origem, "rb") as f:
                    leitor = pypdf.PdfReader(f)
                    
                    if len(leitor.pages) > 0:
                        # Extrai o texto estritamente da primeira página (índice 0)
                        texto_capa = leitor.pages[0].extract_text()
                        
                        if texto_capa:
                            # --- POSSIBILIDADE 1 (Estrita / Caixa Alta) ---
                            # O operador 'in' diferencia maiúsculas de minúsculas nativamente
                            passou_regra_1 = all(termo in texto_capa for termo in termos_possibilidade_1)
                            
                            # --- POSSIBILIDADE 2 (Flexível / Qualquer capitalização) ---
                            # Convertemos o texto da capa para minúsculo para permitir variações
                            texto_capa_lower = texto_capa.lower()
                            passou_regra_2 = all(termo in texto_capa_lower for termo in termos_possibilidade_2)
                            
                            # Se passar em qualquer uma das duas regras, o arquivo é válido
                            atende_padrao = passou_regra_1 or passou_regra_2
                
                if atende_padrao:
                    cont_match += 1
                    shutil.copy2(caminho_origem, os.path.join(pasta_filtrados, nome_arq))
                    callback_interface(None, prog, f"🎯 [PADRÃO FGV DETECTADO] {nome_arq}\n")
                else:
                    callback_interface(None, prog, f"⏭️ [PADRÃO DIFERENTE] {nome_arq}\n")
                    
            except Exception as e:
                callback_interface(None, prog, f"⚠️ [ERRO LEITURA] {nome_arq}: {e}\n")

        # Finalização enviando o status 1.0 (100%) para a interface
        callback_interface(
            "Triagem de Padrão FGV Concluída!", 
            1.0, 
            f"\n=== TRIAGEM LOCAL FINALIZADA ===\n{cont_match} cadernos de prova da FGV identificados e separados.\n"
        )