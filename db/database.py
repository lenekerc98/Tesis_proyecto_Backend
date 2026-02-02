from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql://postgres:T3sis26$@proyecto-tesis-ia.cvqygw680vc7.us-east-1.rds.amazonaws.com:5432/postgres"

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
