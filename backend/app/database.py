from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bioinsight")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True, 
    pool_recycle=1800,
    connect_args={"connect_timeout": 5}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        # Set a 10s timeout for all operations in this session
        db.execute(text("SET statement_timeout = 10000"))
        yield db
    finally:
        db.close()
