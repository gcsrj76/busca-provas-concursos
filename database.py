import os
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

DATABASE_URL = "sqlite:///dados_concursos.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ConcursoModel(Base):
    """Mapeamento da tabela de concursos."""

    __tablename__ = "concursos"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, nullable=False, index=True)
    titulo = Column(String, nullable=True)
    coletado_em = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamento: Permite acessar os arquivos a partir do concurso
    arquivos = relationship(
        "ArquivoProvaModel", back_populates="concurso", cascade="all, delete"
    )


class ArquivoProvaModel(Base):
    """Mapeamento dos links internos de Provas Objetivas de cada concurso."""

    __tablename__ = "arquivos_provas"

    id = Column(Integer, primary_key=True, index=True)
    concurso_id = Column(Integer, ForeignKey("concursos.id"), nullable=False)
    descricao = Column(String, nullable=False)
    url_arquivo = Column(String, unique=True, nullable=False, index=True)
    coletado_em = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamento inverso
    concurso = relationship("ConcursoModel", back_populates="arquivos")


def inicializar_banco():
    """Garante que as tabelas sejam criadas no arquivo .db."""
    Base.metadata.create_all(engine)