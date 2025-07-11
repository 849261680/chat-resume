from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.services.openrouter_service import OpenRouterService
from app.services.resume_service import ResumeService
from app.core.prompts import ResumeAssistantPrompts
from app.core.database import get_db
from app.api.deps import get_current_user
import json

router = APIRouter()

class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    resume_id: int
    chat_history: list = []  # 聊天历史，可选
    is_interview: bool = False  # 是否为面试模式
    interview_mode: str = "comprehensive"  # 面试模式：comprehensive, technical, behavioral
    
    def __init__(self, **data):
        super().__init__(**data)
        print(f"ChatRequest 初始化 - is_interview: {self.is_interview}, interview_mode: {self.interview_mode}")

class ChatResponse(BaseModel):
    """聊天响应模型"""
    response: str
    service: str = "openrouter"
    is_configured: bool = True

@router.post("/chat", response_model=ChatResponse)
async def chat_with_resume(
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """与AI助手聊天，基于用户真实简历内容"""
    
    try:
        # 获取用户真实简历数据
        resume_service = ResumeService(db)
        resume = resume_service.get_by_id(chat_request.resume_id)
        
        # 验证简历存在性和用户权限
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="简历不存在"
            )
        
        # 调试信息
        print(f"Debug - Resume ID: {chat_request.resume_id}")
        print(f"Debug - Resume owner_id: {resume.owner_id}")
        print(f"Debug - Current user ID: {current_user['id']}")
        print(f"Debug - Current user: {current_user}")
            
        if resume.owner_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"没有权限访问此简历 (简历所有者: {resume.owner_id}, 当前用户: {current_user['id']})"
            )
        
        # 使用真实简历数据
        resume_content = resume.content
        
        # 使用新的提示词管理系统，包含聊天历史
        openrouter_service = OpenRouterService()
        messages = ResumeAssistantPrompts.build_chat_messages(
            chat_request.message,
            resume_content,
            chat_request.chat_history
        )
        
        # 调用AI服务
        response = await openrouter_service.chat_completion(messages)
        ai_response = openrouter_service._clean_ai_response(
            response["choices"][0]["message"]["content"]
        )
        
        return ChatResponse(
            response=ai_response,
            service="openrouter",
            is_configured=True
        )
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 处理其他异常
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI服务暂时不可用: {str(e)}"
        )

@router.post("/chat/stream")
async def chat_with_resume_stream(
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """与AI助手进行流式聊天，基于用户真实简历内容"""
    
    print("=== 流式聊天API被调用 ===")
    print(f"收到请求 - is_interview: {chat_request.is_interview}")
    print(f"用户消息: {chat_request.message}")
    
    async def generate_stream():
        try:
            # 获取用户真实简历数据
            resume_service = ResumeService(db)
            resume = resume_service.get_by_id(chat_request.resume_id)
            
            # 验证简历存在性和用户权限
            if not resume:
                error_data = {
                    "error": "简历不存在",
                    "done": True
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                return
            
            # 调试信息
            print(f"Debug Stream - Resume ID: {chat_request.resume_id}")
            print(f"Debug Stream - Resume owner_id: {resume.owner_id}")
            print(f"Debug Stream - Current user ID: {current_user['id']}")
            print(f"Debug Stream - Current user: {current_user}")
                
            if resume.owner_id != current_user["id"]:
                error_data = {
                    "error": f"没有权限访问此简历 (简历所有者: {resume.owner_id}, 当前用户: {current_user['id']})",
                    "done": True
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                return
            
            # 使用真实简历数据
            resume_content = resume.content
            
            openrouter_service = OpenRouterService()
            
            # 根据模式构建不同的消息
            print(f"Debug - is_interview: {chat_request.is_interview}")
            print(f"Debug - chat_request: {chat_request}")
            
            if chat_request.is_interview:
                # 面试模式：使用面试官提示词
                print(f"Debug - 使用面试官提示词，模式: {chat_request.interview_mode}")
                messages = ResumeAssistantPrompts.build_interview_messages(
                    chat_request.message,
                    resume_content,
                    chat_request.chat_history,
                    chat_request.interview_mode
                )
            else:
                # 普通模式：使用简历优化师提示词
                print("Debug - 使用简历优化师提示词")
                messages = ResumeAssistantPrompts.build_chat_messages(
                    chat_request.message,
                    resume_content,
                    chat_request.chat_history
                )
            
            # 流式响应
            async for content_chunk in openrouter_service.chat_completion_stream(messages):
                # 以Server-Sent Events格式发送
                data = {
                    "content": content_chunk,
                    "done": False
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            
            # 发送结束标记
            end_data = {"content": "", "done": True}
            yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            # 发送错误信息
            error_data = {
                "error": f"AI服务暂时不可用: {str(e)}",
                "done": True
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@router.get("/status")
async def get_ai_status():
    """获取AI服务状态"""
    try:
        openrouter_service = OpenRouterService()
        # 简单的状态检查
        if openrouter_service.api_key:
            return {
                "service": "openrouter",
                "status": "connected",
                "is_configured": True
            }
        else:
            return {
                "service": "mock",
                "status": "not_configured",
                "is_configured": False
            }
    except Exception:
        return {
            "service": "mock", 
            "status": "error",
            "is_configured": False
        }