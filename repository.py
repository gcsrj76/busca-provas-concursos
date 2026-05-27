from database import ArquivoProvaModel, ConcursoModel, SessionLocal
from sqlalchemy.orm import joinedload

class ConcursoRepository:
    
    @staticmethod
    def limpar_banco():
        """Apaga todos os registros de concursos. 
        Os arquivos de provas vinculados serão apagados por cascata (Cascade Delete).
        """
        db = SessionLocal()
        try:
            # Remove todos os registros da tabela de concursos
            db.query(ConcursoModel).delete()
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Erro ao limpar o banco de dados: {e}")
        finally:
            db.close()

    @staticmethod
    def salvar_link(url: str, titulo: str = None) -> bool:
        db = SessionLocal()
        try:
            existe = db.query(ConcursoModel).filter(ConcursoModel.url == url).first()
            if not existe:
                novo_concurso = ConcursoModel(url=url, titulo=titulo)
                db.add(novo_concurso)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            print(f"Erro ao salvar concurso: {e}")
            return False
        finally:
            db.close()

    @staticmethod
    def listar_todos():
        db = SessionLocal()
        try:
            # Adicionado o .order_by(ConcursoModel.id.asc()) para garantir a ordem de inserção
            return db.query(ConcursoModel).options(joinedload(ConcursoModel.arquivos)).order_by(ConcursoModel.id.asc()).all()
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
            print(f"Erro ao salvar arquivo de prova: {e}")
            return False
        finally:
            db.close()