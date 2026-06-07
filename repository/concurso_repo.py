from sqlalchemy.orm import joinedload
from database.connection import SessionLocal
from database.models import ConcursoModel, ArquivoProvaModel

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
        try:
            existe = db.query(ArquivoProvaModel).filter(ArquivoProvaModel.url_arquivo == url_arquivo).first()
            if not existe:
                novo_arquivo = ArquivoProvaModel(concurso_id=concurso_id, descricao=descricao, url_arquivo=url_arquivo)
                db.add(novo_arquivo)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
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