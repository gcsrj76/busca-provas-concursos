from database import ConcursoModel, SessionLocal


class ConcursoRepository:

    @staticmethod
    def salvar_link(url: str, titulo: str = None) -> bool:
        """Salva um link no banco de dados se ele ainda não existir.

        Retorna True se foi salvo, False se já existia.
        """
        db = SessionLocal()
        try:
            # Verifica se a URL já está cadastrada
            existe = (
                db.query(ConcursoModel).filter(ConcursoModel.url == url).first()
            )

            if not existe:
                novo_concurso = ConcursoModel(url=url, titulo=titulo)
                db.add(novo_concurso)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()  # Desfaz alterações em caso de erro
            print(f"Erro ao salvar no banco: {e}")
            return False
        finally:
            db.close()  # Garante o fechamento da conexão

    @staticmethod
    def listar_todos():
        """Retorna todos os concursos salvos no banco de dados."""
        db = SessionLocal()
        try:
            return db.query(ConcursoModel).all()
        finally:
            db.close()