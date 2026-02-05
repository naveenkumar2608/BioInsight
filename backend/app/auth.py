from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

# Secret key to sign JWT tokens
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-12345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

# Password hashing context
# We use passlib for selection but handle verification carefully
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """
    Robust password verification that handles the passlib-bcrypt incompatibility.
    """
    if not plain_password or not hashed_password:
        return False
        
    try:
        # 1. Truncate password for bcrypt compatibility (72 byte limit)
        # We do this for all for safety, but mostly for bcrypt
        pw_bytes = plain_password.encode('utf-8')
        if len(pw_bytes) > 72:
            pw_bytes = pw_bytes[:72]
            plain_password = pw_bytes.decode('utf-8', errors='ignore')

        # 2. Check if it's a bcrypt hash ($2a$, $2b$, $2y$)
        if hashed_password.startswith(('$2a$', '$2b$', '$2y$')):
            # Verify using bcrypt directly to bypass passlib version check bug
            h_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(pw_bytes, h_bytes)
            
        # 3. Fallback to passlib for other schemes (like argon2)
        return pwd_context.verify(plain_password, hashed_password)
        
    except Exception as e:
        print(f"Auth Error: {e}")
        # Final fallback - try passlib anyway
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except:
            return False

def get_password_hash(password):
    """
    Hash a password using the default scheme (argon2).
    """
    if not password:
        raise ValueError("Password cannot be empty")
    
    # Truncate for consistency
    pw_bytes = password.encode('utf-8')
    if len(pw_bytes) > 72:
        password = pw_bytes[:72].decode('utf-8', errors='ignore')
        
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
