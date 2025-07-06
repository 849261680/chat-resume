from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.deepseek_service import DeepSeekService
from app.services.resume_service import ResumeService
from app.models.resume import InterviewSession
from app.schemas.interview import (
    InterviewSessionCreate, 
    InterviewSessionResponse, 
    InterviewQuestionResponse,
    InterviewAnswerRequest,
    InterviewEvaluationResponse
)
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/{resume_id}/interview/start", response_model=InterviewSessionResponse)
async def start_interview(
    resume_id: int,
    session_create: InterviewSessionCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """开始面试会话"""
    
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
    
    try:
        # 生成初始面试问题
        deepseek_service = DeepSeekService()
        questions = await deepseek_service.generate_interview_questions(
            resume.content, 
            session_create.jd_content if session_create.jd_content else ""
        )
        
        # 创建面试会话
        interview_session = InterviewSession(
            resume_id=resume_id,
            jd_content=session_create.jd_content,
            questions=questions,
            answers=[],
            feedback={},
            status="active"
        )
        db.add(interview_session)
        db.commit()
        db.refresh(interview_session)
        
        return InterviewSessionResponse.from_orm(interview_session)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start interview: {str(e)}"
        )

@router.get("/{resume_id}/interview/{session_id}/question", response_model=InterviewQuestionResponse)
async def get_next_question(
    resume_id: int,
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取下一个面试问题"""
    
    # 验证权限
    interview_session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.resume_id == resume_id
    ).first()
    
    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found"
        )
    
    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)
    
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # 获取当前问题索引
    current_question_index = len(interview_session.answers)
    
    # 如果还有预设问题，返回下一个
    if current_question_index < len(interview_session.questions):
        question = interview_session.questions[current_question_index]
        return InterviewQuestionResponse(
            question=question["question"],
            question_type=question.get("type", "general"),
            question_index=current_question_index
        )
    
    # 如果已经回答完所有预设问题，根据对话历史生成新问题
    try:
        deepseek_service = DeepSeekService()
        
        # 构建对话历史
        conversation_history = []
        for i, answer in enumerate(interview_session.answers):
            if i < len(interview_session.questions):
                conversation_history.append({
                    "question": interview_session.questions[i]["question"],
                    "answer": answer["answer"]
                })
        
        # 生成新问题
        new_question = await deepseek_service.generate_next_interview_question(
            conversation_history, 
            resume.content
        )
        
        # 更新会话问题列表
        interview_session.questions.append(new_question)
        db.commit()
        
        return InterviewQuestionResponse(
            question=new_question["question"],
            question_type=new_question.get("type", "follow_up"),
            question_index=current_question_index
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate next question: {str(e)}"
        )

@router.post("/{resume_id}/interview/{session_id}/answer", response_model=InterviewEvaluationResponse)
async def submit_answer(
    resume_id: int,
    session_id: int,
    answer_request: InterviewAnswerRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """提交面试答案并获取评估"""
    
    # 验证权限
    interview_session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.resume_id == resume_id
    ).first()
    
    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found"
        )
    
    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)
    
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        # 获取当前问题
        question_index = answer_request.question_index
        if question_index >= len(interview_session.questions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid question index"
            )
        
        current_question = interview_session.questions[question_index]["question"]
        
        # 使用 DeepSeek 评估答案
        deepseek_service = DeepSeekService()
        evaluation = await deepseek_service.evaluate_interview_answer(
            current_question,
            answer_request.answer,
            resume.content
        )
        
        # 保存答案和评估
        answer_data = {
            "answer": answer_request.answer,
            "evaluation": evaluation,
            "question_index": question_index
        }
        
        # 更新会话答案
        if len(interview_session.answers) <= question_index:
            # 扩展答案列表
            interview_session.answers.extend([{}] * (question_index - len(interview_session.answers) + 1))
        
        interview_session.answers[question_index] = answer_data
        db.commit()
        
        return InterviewEvaluationResponse(
            question=current_question,
            answer=answer_request.answer,
            evaluation=evaluation,
            score=evaluation.get("score", 0),
            feedback=evaluation.get("feedback", ""),
            suggestions=evaluation.get("suggestions", [])
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate answer: {str(e)}"
        )

@router.post("/{resume_id}/interview/{session_id}/end")
async def end_interview(
    resume_id: int,
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """结束面试会话"""
    
    # 验证权限
    interview_session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.resume_id == resume_id
    ).first()
    
    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found"
        )
    
    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)
    
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # 更新会话状态
    interview_session.status = "completed"
    db.commit()
    
    return {"message": "Interview session ended successfully"}

@router.get("/{resume_id}/interview/sessions", response_model=List[InterviewSessionResponse])
async def get_interview_sessions(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取面试会话列表"""
    
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
    
    # 获取面试会话
    sessions = db.query(InterviewSession).filter(
        InterviewSession.resume_id == resume_id
    ).order_by(InterviewSession.created_at.desc()).all()
    
    return [InterviewSessionResponse.from_orm(session) for session in sessions]