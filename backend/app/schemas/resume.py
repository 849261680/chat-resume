from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel

class ResumeCreate(BaseModel):
    title: str
    content: Dict[str, Any]
    original_filename: Optional[str] = None

class ResumeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    original_filename: Optional[str] = None

class ResumeResponse(BaseModel):
    id: int
    title: str
    content: Dict[str, Any]
    original_filename: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}

class OptimizationRequest(BaseModel):
    jd_content: str

class OptimizationResponse(BaseModel):
    id: int
    resume_id: int
    jd_content: str
    suggestions: Dict[str, Any]
    created_at: datetime
    
    model_config = {"from_attributes": True}