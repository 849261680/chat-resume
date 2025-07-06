from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel

class ResumeCreate(BaseModel):
    title: str
    content: Dict[str, Any]
    original_filename: Optional[str] = None

class ResumeResponse(BaseModel):
    id: int
    title: str
    content: Dict[str, Any]
    original_filename: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class OptimizationRequest(BaseModel):
    jd_content: str

class OptimizationResponse(BaseModel):
    id: int
    resume_id: int
    jd_content: str
    suggestions: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True