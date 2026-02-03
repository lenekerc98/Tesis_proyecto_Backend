import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Intenta cargar el .env si existe, si no, no pasa nada (así no da error en Render)
load_dotenv()

# Prioridad 1: Variable de entorno de Render. Prioridad 2: Tu link de AWS.
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:T3sis26$@proyecto-tesis-ia.cvqygw680vc7.us-east-1.rds.amazonaws.com:5432/postgres"

# Render a veces prefiere 'postgresql' en lugar de 'postgres'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configuración de SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependencia para tus rutas de FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()