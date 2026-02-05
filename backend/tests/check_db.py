
import os
import sqlalchemy
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

def test_db():
    url = os.getenv("DATABASE_URL")
    print(f"Testing connection to: {url}")
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            print("SUCCESS: Connection established.")
            # Check if tables exist
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            print(f"Tables found: {tables}")
    except Exception as e:
        print(f"FAIL: {e}")

if __name__ == "__main__":
    test_db()
