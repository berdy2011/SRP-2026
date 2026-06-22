from sqlalchemy import Column, Integer, String, Text, DateTime, func
from database import Base

class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), index=True)  # ID разговора
    role = Column(String(16))                     # 'user' или 'assistant'
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())