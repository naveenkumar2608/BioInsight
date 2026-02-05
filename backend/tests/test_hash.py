from passlib.context import CryptContext
import time

print("Setting up CryptContext...")
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

password = "testpassword123"

print("Starting hash...")
start = time.time()
try:
    hashed = pwd_context.hash(password)
    end = time.time()
    print(f"Hash success: {hashed[:20]}...")
    print(f"Time taken: {end - start:.4f}s")
    
    print("Starting verify...")
    start = time.time()
    verify = pwd_context.verify(password, hashed)
    end = time.time()
    print(f"Verify success: {verify}")
    print(f"Time taken: {end - start:.4f}s")
except Exception as e:
    print(f"ERROR: {e}")
