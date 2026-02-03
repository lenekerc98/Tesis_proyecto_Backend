import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Render inyectará estas variables. Si no existen, usará la URL por defecto (tu string actual)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:T3sis26$@proyecto-tesis-ia.cvqygw680vc7.us-east-1.rds.amazonaws.com:5432/postgres")

# Ajuste para Render: Algunas bases de datos requieren sslmode
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# DEPENDENCIA DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()