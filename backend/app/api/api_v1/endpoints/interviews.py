from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.resume import InterviewSession, Resume
from app.schemas.interview import InterviewSessionResponse
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/", response_model=List[InterviewSessionResponse])
async def get_all_interview_sessions(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有面试会话"""
    
    # 获取用户所有简历的面试会话
    sessions = db.query(InterviewSession).join(Resume).filter(
        Resume.owner_id == current_user["id"]
    ).order_by(InterviewSession.created_at.desc()).all()
    
    # 为每个会话添加简历标题
    result = []
    for session in sessions:
        session_data = InterviewSessionResponse.model_validate(session)
        # 添加简历标题到响应中
        session_dict = session_data.model_dump()
        session_dict["resume_title"] = session.resume.title
        result.append(session_dict)
    
    return result

@router.get("/stats")
async def get_interview_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取面试统计信息"""
    
    # 获取总面试次数
    total_interviews = db.query(InterviewSession).join(Resume).filter(
        Resume.owner_id == current_user["id"]
    ).count()
    
    # 获取已完成面试次数
    completed_interviews = db.query(InterviewSession).join(Resume).filter(
        Resume.owner_id == current_user["id"],
        InterviewSession.status == "completed"
    ).count()
    
    # 获取进行中面试次数
    active_interviews = db.query(InterviewSession).join(Resume).filter(
        Resume.owner_id == current_user["id"],
        InterviewSession.status == "active"
    ).count()
    
    return {
        "total_interviews": total_interviews,
        "completed_interviews": completed_interviews,
        "active_interviews": active_interviews,
        "completion_rate": round(completed_interviews / max(total_interviews, 1) * 100, 1)
    }