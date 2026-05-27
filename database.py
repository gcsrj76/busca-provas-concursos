import os
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

# Define o local do banco de dados (será um arquivo chamado dados_concursos.db)
DATABASE_URL = "sqlite:///dados_concursos.db"

# CORREÇÃO AQUI: O termo correto da biblioteca é create_engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Cria a fábrica de sessões para conversar com o banco
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe base para a criação das tabelas
Base = declarative_base()


class ConcursoModel(Base):
    """Mapeamento da tabela de concursos no banco de dados."""

    __tablename__ = "concursos"

    id = Column(Integer, primary_key=True, index=True)
    # A URL será única para evitar registros duplicados no banco
    url = Column(String, unique=True, nullable=False, index=True)
    titulo = Column(String, nullable=True)
    # Guarda automaticamente o momento em que o link foi descoberto
    coletado_em = Column(DateTime(timezone=True), server_default=func.now())


def inicializar_banco():
    """Garante que as tabelas sejam criadas no arquivo .db."""
    Base.metadata.create_all(engine)