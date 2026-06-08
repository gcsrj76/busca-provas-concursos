from sqlalchemy.orm import joinedload
from database.connection import SessionLocal
from database.models import ConcursoModel, ArquivoProvaModel
import os
import time 

class ConcursoRepository:
    
    @staticmethod
    def limpar_banco():
        db = SessionLocal()
        try:
            db.query(ConcursoModel).delete()
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Erro ao limpar banco: {e}")
        finally:
            db.close()

    @staticmethod
    def salvar_link(url: str, titulo: str = None, ordem_coleta: int = None, pagina_coleta: int = None) -> bool:
        db = SessionLocal()
        try:
            existe = db.query(ConcursoModel).filter(ConcursoModel.url == url).first()
            if not existe:
                novo_concurso = ConcursoModel(
                    url=url, 
                    titulo=titulo, 
                    ordem_coleta=ordem_coleta, 
                    pagina_coleta=pagina_coleta
                )
                db.add(novo_concurso)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            return False
        finally:
            db.close()

    @staticmethod
    def listar_todos():
        db = SessionLocal()
        try:
            return db.query(ConcursoModel).options(joinedload(ConcursoModel.arquivos)).order_by(ConcursoModel.id.asc()).all()
        finally:
            db.close()

    @staticmethod
    def contar_concursos() -> int:
        db = SessionLocal()
        try:
            return db.query(ConcursoModel).count()
        finally:
            db.close()

    @staticmethod
    def contar_arquivos_provas() -> int:
        db = SessionLocal()
        try:
            return db.query(ArquivoProvaModel).count()
        finally:
            db.close()

    @staticmethod
    def salvar_arquivo_prova(concurso_id: int, descricao: str, url_arquivo: str) -> bool:
        db = SessionLocal()
        # Define o nome do arquivo de log na pasta corrente
        arquivo_log = "erros_gravacao_provas.log"
        
        try:
            # 1. Se a URL exata já existe, não faz nada (Evita duplicados idênticos)
            existe_url = db.query(ArquivoProvaModel).filter(
                ArquivoProvaModel.url_arquivo == url_arquivo
            ).first()
            
            if existe_url:
                # REGISTRO DE LOG: Arquivo ignorado por duplicidade de link
                with open(arquivo_log, "a", encoding="utf-8") as log:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    log.write(f"[{timestamp}] [IGNORADO] Concurso ID: {concurso_id} | Nome: '{descricao}'\n")
                    log.write(f"👉 Motivo: A URL já está cadastrada no banco de dados.\n")
                    log.write(f"🔗 URL: {url_arquivo}\n")
                    log.write("-" * 80 + "\n")
                return False

            # 2. Se a URL é nova, mas a descrição já existe para este concurso, gera um sufixo
            descricao_final = descricao
            contador = 1
            
            while True:
                existe_descricao = db.query(ArquivoProvaModel).filter(
                    ArquivoProvaModel.concurso_id == concurso_id,
                    ArquivoProvaModel.descricao == descricao_final
                ).first()
                
                if not existe_descricao:
                    break
                
                descricao_final = f"{descricao} - {contador}"
                contador += 1

            # 3. Grava o novo registro com o nome definitivo
            novo_arquivo = ArquivoProvaModel(
                concurso_id=concurso_id, 
                descricao=descricao_final, 
                url_arquivo=url_arquivo
            )
            db.add(novo_arquivo)
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            
            # REGISTRO DE LOG: Falha crítica ou erro de banco de dados
            with open(arquivo_log, "a", encoding="utf-8") as log:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                log.write(f"[{timestamp}] [ERRO CRÍTICO] Concurso ID: {concurso_id} | Nome tentado: '{descricao}'\n")
                log.write(f"💥 Motivo/Exceção: {str(e)}\n")
                log.write(f"🔗 URL tentada: {url_arquivo}\n")
                log.write("-" * 80 + "\n")
            return False
            
        finally:
            db.close()

    @staticmethod
    def atualizar_status_download(arquivo_id: int, status: bool):
        """Atualiza o campo 'baixado' de um arquivo específico no banco de dados."""
        db = SessionLocal()
        try:
            arquivo = db.query(ArquivoProvaModel).filter(ArquivoProvaModel.id == arquivo_id).first()
            if arquivo:
                arquivo.baixado = status
                db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()  

    @staticmethod
    def obter_arquivos_pendentes():
        """Retorna apenas os arquivos cujo status 'baixado' seja falso, trazendo o concurso associado."""
        session = SessionLocal()
        try:
            # AJUSTE CRÍTICO: Utiliza joinedload para embutir o concurso antes de fechar a sessão
            return session.query(ArquivoProvaModel)\
                .filter(ArquivoProvaModel.baixado == False)\
                .options(joinedload(ArquivoProvaModel.concurso))\
                .all()
        finally:
            session.close()

    @staticmethod
    def resetar_status_downloads():
        """Define o campo 'baixado' como False para TODOS os registros da tabela arquivos_provas."""
        db = SessionLocal()
        try:
            # Faz o update em lote mudando de True para False
            db.query(ArquivoProvaModel).update({ArquivoProvaModel.baixado: False})
            db.commit()
            print("🔄 [BANCO] Todos os registros de arquivos foram resetados para pendentes (baixado = False).")
        except Exception as e:
            db.rollback()
            print(f"⚠️ Erro ao resetar status de downloads: {e}")
            raise e
        finally:
            db.close()     

    @staticmethod
    def gerar_listagem_provisoria_descricoes():
        # Nome do arquivo que será gerado na pasta corrente
        nome_arquivo_txt = "listagem_descricoes_provas.txt"
        
        # Inicia a sessão com o banco de dados
        db = SessionLocal()
        try:
            print("⏳ Buscando descrições no banco de dados...")
            
            # O .with_entities garante que o SQLAlchemy traga APENAS a coluna descrição, 
            # evitando carregar o resto dos dados pesados (como as URLs) para a memória.
            resultados = db.query(ArquivoProvaModel).with_entities(ArquivoProvaModel.descricao).all()
            
            total_registros = len(resultados)
            if total_registros == 0:
                print("⚠️ A tabela 'arquivos_provas' está vazia. Nenhum arquivo gerado.")
                return

            print(f"✍️ Gravando {total_registros} itens no arquivo '{nome_arquivo_txt}'...")
            
            # Cria/Sobrescreve o arquivo txt salvando cada descrição em uma nova linha
            with open(nome_arquivo_txt, "w", encoding="utf-8") as f:
                for registro in resultados:
                    # registro[0] pois o with_entities retorna uma tupla por linha
                    f.write(f"{registro[0]}\n")
                    
            print(f"🎉 Sucesso! Arquivo '{nome_arquivo_txt}' gerado na pasta corrente.")
            
        except Exception as e:
            print(f"💥 Ocorreu um erro ao gerar a listagem: {e}")
            
        finally:
            db.close()
