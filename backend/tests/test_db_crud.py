
import os
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String
import uuid
import datetime

# Manually load .env since we're in a script
from dotenv import load_dotenv
load_dotenv(dotenv_path=r"c:\BioInsight\backend\.env")

Base = declarative_base()

class DBUser(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    full_name = Column(String)
    created_at = Column(sqlalchemy.DateTime, default=datetime.datetime.utcnow)

def test_crud():
    url = os.getenv("DATABASE_URL")
    print(f"Testing CRUD on: {url}")
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        test_email = f"test_{uuid.uuid4().hex[:6]}@example.com"
        print(f"Creating user: {test_email}")
        
        new_user = DBUser(id=str(uuid.uuid4()), email=test_email, hashed_password="test", full_name="Test")
        db.add(new_user)
        db.commit()
        print("Commit success.")
        
        user = db.query(DBUser).filter(DBUser.email == test_email).first()
        print(f"Found user: {user.email if user else 'NONE'}")
        
        db.delete(user)
        db.commit()
        print("Delete and cleanup success.")
        db.close()
        print("DONE.")
    except Exception as e:
        print(f"FAIL: {e}")

if __name__ == "__main__":
    test_crud()
