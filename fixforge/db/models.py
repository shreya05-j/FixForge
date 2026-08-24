from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class FixSession(Base):
    __tablename__ = 'fix_sessions'
    
    id = Column(String, primary_key=True, index=True)
    issue_url = Column(String, index=True)
    status = Column(String)
    confidence = Column(Float)
    patch_generated = Column(Boolean, default=False)
    log_output = Column(Text)
