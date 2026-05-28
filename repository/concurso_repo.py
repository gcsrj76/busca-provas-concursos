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