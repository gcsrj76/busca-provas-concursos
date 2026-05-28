from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base

class ConcursoModel(Base):
    __tablename__ = "concursos"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, nullable=False, index=True)
    titulo = Column(String, nullable=True)
    ordem_coleta = Column(Integer, nullable=True)
    coletado_em = Column(DateTime(timezone=True), server_default=func.now())

    arquivos = relationship(
        "ArquivoProvaModel", back_populates="concurso", cascade="all, delete"
    )

class ArquivoProvaModel(Base):
    __tablename__ = "arquivos_provas"

    id = Column(Integer, primary_key=True, index=True)
    concurso_id = Column(Integer, ForeignKey("concursos.id"), nullable=False)
    descricao = Column(String, nullable=False)
    url_arquivo = Column(String, unique=True, nullable=False, index=True)
    coletado_em = Column(DateTime(timezone=True), server_default=func.now())

    concurso = relationship("ConcursoModel", back_populates="arquivos")