"""
面试评分API端点
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.services.interview_scoring_service import InterviewScoringService
from app.services.resume_service import ResumeService
from app.core.database import get_db
from app.api.deps import get_current_user

router = APIRouter()

class ScoringRequest(BaseModel):
    """评分请求模型"""
    question: str
    answer: str
    resume_id: int
    jd_keywords: Optional[List[str]] = None

class ScoringResponse(BaseModel):
    """评分响应模型"""
    relevance_score: float
    star_analysis: Dict[str, bool]
    keyword_match: Dict[str, Any]
    fluency_score: float
    overall_score: float
    suggestions: List[str]

@router.post("/score", response_model=ScoringResponse)
async def score_interview_answer(
    scoring_request: ScoringRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    对面试回答进行多维度评分
    """
    try:
        # 验证简历权限
        resume_service = ResumeService(db)
        resume = resume_service.get_by_id(scoring_request.resume_id)
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="简历不存在"
            )
        
        if resume.owner_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限访问此简历"
            )
        
        # 初始化评分服务
        scoring_service = InterviewScoringService()
        
        # 进行评分
        result = await scoring_service.score_answer(
            question=scoring_request.question,
            answer=scoring_request.answer,
            resume_content=resume.content,
            jd_keywords=scoring_request.jd_keywords
        )
        
        return ScoringResponse(
            relevance_score=result.relevance_score,
            star_analysis=result.star_analysis,
            keyword_match=result.keyword_match,
            fluency_score=result.fluency_score,
            overall_score=result.overall_score,
            suggestions=result.suggestions
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"评分服务暂时不可用: {str(e)}"
        )

@router.get("/keywords")
async def get_tech_keywords():
    """
    获取技术关键词库
    """
    scoring_service = InterviewScoringService()
    return {
        "tech_keywords": scoring_service.tech_keywords,
        "star_keywords": scoring_service.star_keywords
    }