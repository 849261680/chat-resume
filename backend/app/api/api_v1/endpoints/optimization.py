from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.openrouter_service import OpenRouterService
from app.services.resume_service import ResumeService
from app.schemas.resume import OptimizationRequest, OptimizationResponse
from app.models.resume import OptimizationRecord
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/{resume_id}/optimize", response_model=OptimizationResponse)
async def optimize_resume(
    resume_id: int,
    optimization_request: OptimizationRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """优化简历"""
    
    # 获取简历
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
    
    try:
        # 调用 OpenRouter API 进行分析
        openrouter_service = OpenRouterService()
        analysis_result = await openrouter_service.analyze_resume_jd_match(
            resume.content, 
            optimization_request.jd_content
        )
        
        # 保存优化记录
        optimization_record = OptimizationRecord(
            resume_id=resume_id,
            jd_content=optimization_request.jd_content,
            suggestions=analysis_result
        )
        db.add(optimization_record)
        db.commit()
        db.refresh(optimization_record)
        
        return OptimizationResponse.model_validate(optimization_record)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to optimize resume: {str(e)}"
        )

@router.get("/{resume_id}/optimizations")
async def get_optimizations(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取简历的优化记录"""
    
    # 验证简历权限
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
    
    # 获取优化记录
    optimizations = db.query(OptimizationRecord).filter(
        OptimizationRecord.resume_id == resume_id
    ).order_by(OptimizationRecord.created_at.desc()).all()
    
    return [OptimizationResponse.model_validate(opt) for opt in optimizations]