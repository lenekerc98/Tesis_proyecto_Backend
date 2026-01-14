from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql://postgres:Atom0909@localhost:5432/Proyecto_Tesis_IA"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

#DEPENDENCIA DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()