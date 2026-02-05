from pydantic import BaseModel, EmailStr
from typing import List, Optional, Any
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
import datetime

# --- SQLAlchemy Models (Database) ---

class DBUser(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    sessions = relationship("DBChatSession", back_populates="user")

class DBChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String, default="New Analysis")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("DBUser", back_populates="sessions")
    messages = relationship("DBMessage", back_populates="session", cascade="all, delete-orphan")

class DBMessage(Base):
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    text = Column(Text)
    is_user = Column(Integer, default=0) # 0: Assistant, 1: User
    analysis_data = Column(JSON, nullable=True) # To store AnalysisResult JSON
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    session = relationship("DBChatSession", back_populates="messages")

# --- Pydantic Models (API) ---

class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    text: str
    is_user: bool
    data: Optional[dict] = None # Matches Frontend naming
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class AnalysisResult(BaseModel):
    drug: str
    target: str
    evidence_type: str = "Known Drug Interaction"
    explanation: str
    confidence_score: float
    evidence_sources: List[str]
    raw_evidence_count: int

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    confidence: float
    entities: dict
    data: Optional[AnalysisResult] = None
