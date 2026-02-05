
import os
import sqlalchemy
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"c:\BioInsight\backend\.env")

def nuke_connections():
    url = os.getenv("DATABASE_URL")
    # Connect to 'postgres' db to kill connections to 'bioinsight'
    base_url = url.rsplit('/', 1)[0] + '/postgres'
    print(f"Connecting to management DB: {base_url}")
    
    try:
        engine = create_engine(base_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            print("Killing all connections to 'bioinsight'...")
            conn.execute(text("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = 'bioinsight'
                AND pid <> pg_backend_pid();
            """))
            print("SUCCESS: Connections terminated.")
    except Exception as e:
        print(f"FAIL: {e}")

if __name__ == "__main__":
    nuke_connections()
