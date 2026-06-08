import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///dados_concursos.db"

# Inicialização limpa e protegida da Engine
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# Configuração estável: expire_on_commit=False impede que o Debugger
# force o lazy-loading ao tentar varrer seus modelos em background.
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine,
    expire_on_commit=False  
)

Base = declarative_base()

def inicializar_banco():
    import database.models  # Garante que os modelos sejam carregados
    Base.metadata.create_all(bind=engine)