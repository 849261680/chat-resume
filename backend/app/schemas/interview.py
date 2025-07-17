from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel

class InterviewSessionCreate(BaseModel):
    job_position: Optional[str] = None
    interview_mode: Optional[str] = None  # comprehensive, technical, behavioral
    jd_content: Optional[str] = None
    question_count: Optional[int] = 10

class InterviewSessionResponse(BaseModel):
    id: int
    resume_id: int
    job_position: Optional[str] = None
    interview_mode: Optional[str] = None
    jd_content: Optional[str] = None
    questions: List[Dict[str, Any]]
    answers: List[Dict[str, Any]]
    feedback: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}

class InterviewQuestionResponse(BaseModel):
    question: str
    question_type: str
    question_index: int

class InterviewAnswerRequest(BaseModel):
    answer: str
    question_index: int

class InterviewEvaluationResponse(BaseModel):
    question: str
    answer: str
    evaluation: Dict[str, Any]
    score: int
    feedback: str
    suggestions: List[str]