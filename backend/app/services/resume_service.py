from typing import List
from sqlalchemy.orm import Session
from app.models.resume import Resume
from app.schemas.resume import ResumeCreate

class ResumeService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, resume_id: int) -> Resume:
        return self.db.query(Resume).filter(Resume.id == resume_id).first()
    
    def get_by_owner(self, owner_id: int) -> List[Resume]:
        return self.db.query(Resume).filter(Resume.owner_id == owner_id).all()
    
    def create(self, resume_create: ResumeCreate, owner_id: int) -> Resume:
        resume = Resume(
            title=resume_create.title,
            content=resume_create.content,
            original_filename=resume_create.original_filename,
            owner_id=owner_id
        )
        self.db.add(resume)
        self.db.commit()
        self.db.refresh(resume)
        return resume
    
    def update(self, resume_id: int, resume_update: dict) -> Resume:
        resume = self.get_by_id(resume_id)
        if resume:
            for key, value in resume_update.items():
                setattr(resume, key, value)
            self.db.commit()
            self.db.refresh(resume)
        return resume