from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime
import os

from chat_models import Base, ChatUser, ChatSession, ChatMessage
from config import DATABASE_CONFIG
from ai_assistant import AIAssistant

# Initialize AI Assistant
ai_assistant = AIAssistant()

# Create FastAPI app
app = FastAPI(title="Think41 Chat API")

# Database connection
db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
engine = create_engine(db_url)

# Create tables
Base.metadata.create_all(engine)

# SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models for request/response
class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class SessionBase(BaseModel):
    session_name: Optional[str] = None

class SessionCreate(SessionBase):
    pass

class SessionResponse(SessionBase):
    id: int
    user_id: int
    created_at: datetime
    last_updated: datetime

    class Config:
        orm_mode = True

class MessageBase(BaseModel):
    content: str
    role: str

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: int
    session_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class ChatRequest(BaseModel):
    message: str
    user_id: int
    session_id: Optional[int] = None

class ChatResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    session_id: int

# API Endpoints

@app.post("/users/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = ChatUser(username=user.username, email=user.email)
    db.add(db_user)
    try:
        db.commit()
        db.refresh(db_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or email already exists")
    return db_user

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(ChatUser).filter(ChatUser.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/users/{user_id}/sessions/", response_model=SessionResponse)
def create_session(user_id: int, session: SessionCreate, db: Session = Depends(get_db)):
    db_session = ChatSession(user_id=user_id, session_name=session.session_name)
    db.add(db_session)
    try:
        db.commit()
        db.refresh(db_session)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not create session")
    return db_session

@app.get("/users/{user_id}/sessions/", response_model=List[SessionResponse])
def get_user_sessions(user_id: int, db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == user_id).all()
    return sessions

@app.post("/sessions/{session_id}/messages/", response_model=MessageResponse)
def create_message(session_id: int, message: MessageCreate, db: Session = Depends(get_db)):
    db_message = ChatMessage(
        session_id=session_id,
        content=message.content,
        role=message.role
    )
    db.add(db_message)
    try:
        db.commit()
        db.refresh(db_message)
        
        # Update session last_updated timestamp
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        session.last_updated = func.now()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not create message")
    return db_message

@app.get("/sessions/{session_id}/messages/", response_model=List[MessageResponse])
def get_session_messages(session_id: int, db: Session = Depends(get_db)):
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at).all()
    return messages

@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.post("/chat/", response_model=ChatResponse)
async def chat(chat_request: ChatRequest, db: Session = Depends(get_db)):
    # Verify user exists
    user = db.query(ChatUser).filter(ChatUser.id == chat_request.user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found. Please create a user first.")

    # Get or create session
    session = None
    if chat_request.session_id:
        session = db.query(ChatSession).filter(ChatSession.id == chat_request.session_id).first()
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        # Create new session
        session = ChatSession(
            user_id=chat_request.user_id,
            session_name=f"Chat Session {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    try:
        # Save user message
        user_message = ChatMessage(
            session_id=session.id,
            content=chat_request.message,
            role="user"
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)

        # Get conversation history
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
            .all()
        ]

        # Generate AI response
        ai_response = ai_assistant.generate_response(chat_request.message, conversation_history)

        # Save AI response
        assistant_message = ChatMessage(
            session_id=session.id,
            content=ai_response,
            role="assistant"
        )
        db.add(assistant_message)
        
        # Update session last_updated
        session.last_updated = func.now()
        
        db.commit()
        db.refresh(assistant_message)

        return ChatResponse(
            user_message=user_message,
            assistant_message=assistant_message,
            session_id=session.id
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")
