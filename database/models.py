from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base

from sqlalchemy import Column, Integer, String, ForeignKey, JSON

class ConcursoModel(Base):
    __tablename__ = "concursos"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, nullable=False, index=True)
    titulo = Column(String, nullable=True)
    ordem_coleta = Column(Integer, nullable=True)
    pagina_coleta = Column(Integer, nullable=True)

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
    baixado = Column(Boolean, default=False, nullable=False)

    concurso = relationship("ConcursoModel", back_populates="arquivos")

"""
class QuestaoSimuladoModel(Base):
    __tablename__ = "questoes_simulado"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    arquivo_prova_id = Column(Integer, ForeignKey("arquivos_provas.id")) # Vinculado à prova de origem
    materia = Column(String, default="Língua Portuguesa")
    
    enunciado = Column(String, nullable=False)
    
    # Armazenaremos as alternativas como um dicionário estruturado via JSON do SQLite
    # Ex: {"A": "Texto da A", "B": "Texto da B", ...}
    alternativas = Column(JSON, nullable=False) 
    
    alternativa_correta = Column(String(1), nullable=True) # Guarda apenas a letra correta (Ex: "C")

    # Relacionamento com a tabela de arquivos de provas já existente
    prova = relationship("ArquivoProvaModel")    
"""