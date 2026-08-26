import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, Integer, JSON, Uuid
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class ReviewSession(Base):
    __tablename__ = 'review_sessions'
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    repo_url = Column(String, index=True)
    branch = Column(String, default="main")
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    attempts = relationship("AgentAttempt", back_populates="session", cascade="all, delete-orphan")
    diagnosis = relationship("DiagnosisRecord", back_populates="session", uselist=False, cascade="all, delete-orphan")
    metrics = relationship("ConfidenceMetric", back_populates="session", uselist=False, cascade="all, delete-orphan")

class AgentAttempt(Base):
    __tablename__ = 'agent_attempts'
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(Uuid, ForeignKey('review_sessions.id'), nullable=False)
    attempt_number = Column(Integer)
    status = Column(String, default="running")
    patch_diff = Column(Text, nullable=True)
    test_logs = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("ReviewSession", back_populates="attempts")

class DiagnosisRecord(Base):
    __tablename__ = 'diagnosis_records'
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(Uuid, ForeignKey('review_sessions.id'), nullable=False)
    failure_classification = Column(String, nullable=True)
    severity_rating = Column(String, nullable=True)
    ast_context = Column(JSON, nullable=True)
    diff_trees = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("ReviewSession", back_populates="diagnosis")

class ConfidenceMetric(Base):
    __tablename__ = 'confidence_metrics'
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(Uuid, ForeignKey('review_sessions.id'), nullable=False)
    overall_score = Column(Float, default=0.0)
    compilation_confidence = Column(Float, default=0.0)
    test_pass_confidence = Column(Float, default=0.0)
    semantic_preservation_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("ReviewSession", back_populates="metrics")
