from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import (
    AnalysisResult, ChatRequest, ChatResponse, DBUser, 
    UserCreate, UserResponse, Token, DBChatSession, 
    DBMessage, ChatSessionResponse, MessageResponse
)
from app.database import engine, Base, get_db, SQLALCHEMY_DATABASE_URL
from app.auth import get_password_hash, verify_password, create_access_token, SECRET_KEY, ALGORITHM
from jose import JWTError, jwt
from app.services.opentargets import search_target_id, get_drug_target_interactions
from app.services.llm import LLMService
from app.utils.scoring import calculate_confidence
import os

# Environment and Static Files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(BASE_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
FRONTEND_DIST = os.path.join(PROJECT_ROOT, "frontend-react", "dist")

# Tables are created in startup_event

app = FastAPI(title="BioInsight AI Chatbot")

# Auth setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Synchronous dependency for getting current user.
    FastAPI will run this in a threadpool, preventing event loop blockage.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(DBUser).filter(DBUser.email == email).first()
    if user is None:
        raise credentials_exception
    return user

@app.on_event("startup")
async def startup_event():
    print("\n" + "="*40)
    print("SERVER STARTING UP")
    print(f"DB Host: {SQLALCHEMY_DATABASE_URL.split('@')[-1]}")
    print("Application is ready to handle requests.")
    print("="*40 + "\n")
    

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global LLM Service instance (lazy loaded)
_llm_service: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        print("Initializing LLMService (Lazy Load)...")
        _llm_service = LLMService()
    return _llm_service

@app.get("/")
def read_root():
    return {"status": "online", "message": "BioInsight AI API is running"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    health_status = {"status": "healthy", "database": "connected", "dist_dir": FRONTEND_DIST}
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = str(e)
    
    # Check if frontend build exists
    if not os.path.exists(FRONTEND_DIST):
        health_status["frontend_build"] = "missing"
    else:
        health_status["frontend_build"] = "found"
        
    return health_status

async def perform_analysis(drug: str, target: str) -> AnalysisResult:
    import time
    start_time = time.time()
    print("2. ANALYSIS PIPELINE START")
    print(f"   Targeting: {drug} → {target}")
    
    # 1. Fetch Data
    print("   [Step 1] Resolving Target ID...", end=" ", flush=True)
    target_id, target_name = await search_target_id(target)
    
    evidence = []
    if target_id:
        print(f"SUCCESS ({target_name}, {target_id})")
        print("   [Step 2] Fetching Interaction Evidence...", end=" ", flush=True)
        evidence = await get_drug_target_interactions(drug, target_id)
        print(f"SUCCESS ({len(evidence)} items)")
    else:
        print("FAILED (Target not found in Open Targets)")
        target_name = target
    
    fetch_time = time.time()
    
    # 2. Logic Layer - Calculate confidence
    print("   [Step 3] Calculating Confidence Score...", end=" ", flush=True)
    confidence_info = calculate_confidence(evidence)
    # The new scoring logic returns a 0-100 score, we normalize to 0-1 for internal consistency
    confidence_score = confidence_info["score"] / 100.0
    print(f"DONE ({confidence_info['score']:.1f}%)")
    
    # 3. AI Layer
    print("   [Step 4] AI Narrative Generation (DeepSeek)...", end=" ", flush=True)
    structured_evidence = {
        "metadata": {
            "confidence_score": confidence_score,
            "max_phase": confidence_info.get("max_phase", 0),
            "deduplicated_evidence_count": confidence_info.get("evidence_count", 0),
            "unique_sources": confidence_info.get("source_count", 0),
            "evidence_types": confidence_info.get("evidence_types", []),
            "reasoning": confidence_info.get("reasoning", "")
        },
        "evidence_items": []
    }
    
    sources = set()
    for item in evidence[:5]:
        refs = item.get("references", [])
        if refs is None: refs = []
        ref_sources = [r.get("source") for r in refs if r.get("source")]
        
        structured_evidence["evidence_items"].append({
            "drug": item.get("drug", {}).get("name"),
            "target": target_name,
            "mechanism": item.get("mechanismOfAction"),
            "phase": item.get("phase"),
            "drugType": item.get("drugType"),
            "references": ref_sources
        })
        for s in ref_sources:
            sources.add(s)
            
    from fastapi.concurrency import run_in_threadpool
    
    ls = get_llm_service()
    explanation = await run_in_threadpool(ls.analyze, structured_evidence)
    print("SUCCESS")
    print(f"   TOTAL ANALYSIS TIME: {time.time() - start_time:.2f}s")
    print("─"*50 + "\n")
    
    return AnalysisResult(
        drug=drug,
        target=target_name,
        explanation=explanation,
        confidence_score=confidence_score,
        evidence_sources=list(sources),
        raw_evidence_count=confidence_info.get("evidence_count", len(evidence))
    )


# --- Auth Endpoints ---

@app.post("/auth/signup", response_model=UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    print(f"SIGNUP REQUEST: {user.email}")
    try:
        db_user = db.query(DBUser).filter(DBUser.email == user.email).first()
        if db_user:
            print(f"SIGNUP FAILED: Email {user.email} already exists")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        
        print(f"SIGNUP: Hashing password for {user.email}...")
        hashed_password = get_password_hash(user.password)
        
        new_user = DBUser(
            email=user.email,
            hashed_password=hashed_password,
            full_name=user.full_name
        )
        print(f"SIGNUP: Saving user {user.email} to DB...")
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        print(f"SIGNUP SUCCESS: {user.email}")
        return new_user
    except Exception as e:
        print(f"SIGNUP ERROR: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    print(f"LOGIN: Form received for {form_data.username}")
    try:
        print(f"LOGIN: Fetching user from DB...")
        user = db.query(DBUser).filter(DBUser.email == form_data.username).first()
        if not user:
            print(f"LOGIN FAILED: User {form_data.username} not found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        print(f"LOGIN: Verifying password for {user.email}...")
        if not verify_password(form_data.password, user.hashed_password):
            print(f"LOGIN FAILED: Incorrect password for {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        from app.auth import ACCESS_TOKEN_EXPIRE_MINUTES
        from datetime import timedelta
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        print(f"LOGIN: Generating token for {user.email}...")
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        print(f"LOGIN SUCCESS: {user.email}")
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"LOGIN ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/me", response_model=UserResponse)
def read_users_me(current_user: DBUser = Depends(get_current_user)):
    return current_user

# --- Chat History Endpoints ---

@app.get("/api/sessions", response_model=List[ChatSessionResponse])
def get_sessions(current_user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(DBChatSession).filter(DBChatSession.user_id == current_user.id).order_by(DBChatSession.created_at.desc()).all()

@app.get("/api/sessions/{session_id}", response_model=List[MessageResponse])
def get_session_messages(session_id: str, current_user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(DBChatSession).filter(DBChatSession.id == session_id, DBChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = db.query(DBMessage).filter(DBMessage.session_id == session_id).order_by(DBMessage.created_at.asc()).all()
    
    # Map DBChatMessage to MessageResponse
    results = []
    for m in messages:
        results.append(MessageResponse(
            text=m.text,
            is_user=bool(m.is_user),
            data=m.analysis_data,
            created_at=m.created_at
        ))
    return results

# --- Chat Endpoint ---
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, current_user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    message = request.message
    session_id = request.session_id
    
    # Get or create session
    if session_id:
        chat_session = db.query(DBChatSession).filter(DBChatSession.id == session_id, DBChatSession.user_id == current_user.id).first()
        if not chat_session:
            session_id = None # Fallback to new session if invalid id provided
            
    if not session_id:
        chat_session = DBChatSession(user_id=current_user.id, title=message[:30] + "...")
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)
        session_id = chat_session.id
    
    # Save User Message
    user_msg = DBMessage(session_id=session_id, text=message, is_user=1)
    db.add(user_msg)
    db.commit()
    
    # 1. Extract and Validate Entities (normalize -> extract -> validate)
    ls = get_llm_service()
    drug, target = await ls.extract_entities(message)
    
    if not (drug and target):
        # Structured refusal behavior matching success format
        drug_status = drug if drug else '✗ Not specified'
        target_status = target if target else '✗ Not specified'
        
        refusal_reply = (
            f"I apologize, but I couldn't extract both a drug and a biological target from your query.\n\n"
            f"To proceed, please specify both:\n"
            f"- A **drug name** (e.g., Imatinib, Aspirin, Erlotinib)\n"
            f"- A **target protein** (e.g., BCR-ABL1, EGFR, COX-2)\n\n"
            f"**Example:** \"What is the interaction between Imatinib and BCR-ABL1?\""
        )
        
        # Create a "Status" analysis data to trigger the card format in frontend
        error_result = AnalysisResult(
            drug=drug_status,
            target=target_status,
            explanation=refusal_reply,
            confidence_score=0.0,
            evidence_sources=[],
            raw_evidence_count=0
        )

        # Still save the assistant's refusal to the session history
        assistant_msg = DBMessage(
            session_id=session_id, 
            text="### Entity Extraction Status", 
            is_user=0,
            analysis_data=error_result.dict()
        )
        db.add(assistant_msg)
        db.commit()

        return ChatResponse(
            reply=assistant_msg.text,
            session_id=session_id,
            confidence=0.0,
            entities={"drug": drug, "target": target},
            data=error_result
        )
    
    # 2. Run Analysis (retrieve -> explain)
    try:
        result = await perform_analysis(drug, target)
        
        # Save Assistant Message
        assistant_msg = DBMessage(
            session_id=session_id, 
            text=f"I've analyzed the interaction between **{drug}** and **{target}**. Here's what the evidence shows:",
            is_user=0,
            analysis_data=result.dict() if result else None
        )
        db.add(assistant_msg)
        db.commit()

        return ChatResponse(
            reply=assistant_msg.text,
            session_id=session_id,
            confidence=result.confidence_score,
            entities={"drug": drug, "target": target},
            data=result
        )
    except Exception as e:
        error_text = f"I encountered an error while analyzing {drug} and {target}: {str(e)}"
        assistant_msg = DBMessage(session_id=session_id, text=error_text, is_user=0)
        db.add(assistant_msg)
        db.commit()
        
        return ChatResponse(
            reply=error_text,
            session_id=session_id,
            confidence=0.0,
            entities={"drug": drug, "target": target},
            data=None
        )



# Only mount if the build directory exists (avoiding crash if search history is used during development)
if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")
else:
    print(f"Warning: Static build directory '{FRONTEND_DIST}' not found. Serving API only.")
