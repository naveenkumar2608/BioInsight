import sys
import os

# Add the backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import DBUser
from app.auth import pwd_context

def check_users():
    db = SessionLocal()
    try:
        users = db.query(DBUser).all()
        print(f"Found {len(users)} users.")
        for user in users:
            print(f"User ID: {user.id}, Email: {user.email}")
            print(f"  Current DB value for password: {user.hashed_password}")
            
            try:
                # identify returns the hash scheme name if valid, else None or raises error
                scheme = pwd_context.identify(user.hashed_password)
                if scheme:
                     print(f"  > Hash format appears VALID (scheme: {scheme})")
                else:
                     print("  > Hash format: INVALID (None returned)")
            except ValueError:
                 print("  > Hash format: INVALID (ValueError)")
            except Exception as e:
                 print(f"  > Hash format: INVALID ({str(e)})")
                 
    except Exception as e:
        print(f"An error occurred accessing the database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_users()
