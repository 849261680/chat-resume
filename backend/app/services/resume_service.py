from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.resume import Resume, OptimizationRecord, InterviewSession
from app.schemas.resume import ResumeCreate
from app.services.file_service import FileService

class ResumeService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, resume_id: int) -> Resume:
        return self.db.query(Resume).filter(Resume.id == resume_id).first()
    
    def get_by_owner(self, owner_id: int) -> List[Resume]:
        return self.db.query(Resume).filter(Resume.owner_id == owner_id).all()
    
    def create(self, resume_create: ResumeCreate, owner_id: int) -> Resume:
        """创建简历记录"""
        resume = Resume(
            title=resume_create.title,
            content=resume_create.content,
            original_filename=resume_create.original_filename,
            owner_id=owner_id
        )
        
        try:
            self.db.add(resume)
            self.db.commit()
            self.db.refresh(resume)
            return resume
        except Exception as e:
            # 回滚事务
            self.db.rollback()
            # 记录错误日志
            print(f"[ERROR] 简历创建失败: {str(e)}")
            # 重新抛出异常供上层处理
            raise e
    
    def update(self, resume_id: int, resume_update: dict) -> Resume:
        resume = self.get_by_id(resume_id)
        if resume:
            for key, value in resume_update.items():
                setattr(resume, key, value)
            self.db.commit()
            self.db.refresh(resume)
        return resume
    
    def delete(self, resume_id: int) -> bool:
        """删除简历及其关联数据"""
        # 获取要删除的简历
        resume = self.get_by_id(resume_id)
        if not resume:
            return False
        
        try:
            # 删除关联的优化记录
            self.db.query(OptimizationRecord).filter(
                OptimizationRecord.resume_id == resume_id
            ).delete()
            
            # 删除关联的面试会话
            self.db.query(InterviewSession).filter(
                InterviewSession.resume_id == resume_id
            ).delete()
            
            # 删除关联的文件
            if resume.file_path:
                file_service = FileService()
                file_service.delete_file(resume.file_path)
            
            # 删除简历记录
            self.db.delete(resume)
            self.db.commit()
            
            return True
            
        except Exception as e:
            # 回滚事务
            self.db.rollback()
            return False