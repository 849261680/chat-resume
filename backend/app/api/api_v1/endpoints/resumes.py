from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.resume import ResumeCreate, ResumeResponse
from app.services.resume_service import ResumeService
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/", response_model=List[ResumeResponse])
async def get_resumes(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resume_service = ResumeService(db)
    resumes = resume_service.get_by_owner(current_user["id"])
    return [ResumeResponse.from_orm(resume) for resume in resumes]

@router.post("/", response_model=ResumeResponse)
async def create_resume(
    resume_create: ResumeCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resume_service = ResumeService(db)
    resume = resume_service.create(resume_create, current_user["id"])
    return ResumeResponse.from_orm(resume)

@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)
    
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return ResumeResponse.from_orm(resume)