from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(JSON, nullable=False)  # 结构化简历内容
    original_filename = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="resumes")
    optimization_records = relationship("OptimizationRecord", back_populates="resume")
    interview_sessions = relationship("InterviewSession", back_populates="resume")

class OptimizationRecord(Base):
    __tablename__ = "optimization_records"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    jd_content = Column(Text, nullable=False)
    suggestions = Column(JSON, nullable=False)
    applied = Column(JSON, nullable=True)  # 用户应用的建议
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    resume = relationship("Resume", back_populates="optimization_records")

class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    job_position = Column(String, nullable=True)  # 面试职位
    interview_mode = Column(String, nullable=True)  # 面试模式: comprehensive, technical, behavioral
    jd_content = Column(Text, nullable=True)  # 职位描述
    questions = Column(JSON, nullable=False)  # 问题列表
    answers = Column(JSON, nullable=False)    # 答案列表
    feedback = Column(JSON, nullable=True)    # AI反馈
    report_data = Column(JSON, nullable=True)  # 面试报告数据缓存
    status = Column(String, default="active")  # active, completed, paused
    overall_score = Column(Integer, nullable=True)  # 面试整体分数 (0-100)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    resume = relationship("Resume", back_populates="interview_sessions")