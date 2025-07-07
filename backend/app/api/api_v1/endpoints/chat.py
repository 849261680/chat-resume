from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.services.openrouter_service import OpenRouterService

router = APIRouter()

class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    resume_id: int

class ChatResponse(BaseModel):
    """聊天响应模型"""
    response: str
    service: str = "openrouter"
    is_configured: bool = True

@router.post("/chat", response_model=ChatResponse)
async def chat_with_resume(
    chat_request: ChatRequest
):
    """与AI助手聊天，基于简历内容（简化版本，用于测试）"""
    
    # 简化版本：使用模拟简历内容进行测试
    mock_resume_content = {
        "personal_info": {
            "name": "测试用户",
            "email": "test@example.com",
            "phone": "13800138000",
            "position": "软件工程师"
        },
        "skills": [
            {"name": "Python", "level": "熟练", "category": "编程语言"},
            {"name": "React", "level": "熟练", "category": "前端框架"}
        ],
        "projects": [
            {
                "name": "简历管理系统",
                "description": "AI驱动的简历优化平台",
                "technologies": ["Python", "React", "FastAPI"]
            }
        ]
    }
    
    try:
        # 使用 OpenRouter 服务进行聊天
        openrouter_service = OpenRouterService()
        ai_response = await openrouter_service.chat_with_resume(
            chat_request.message,
            mock_resume_content
        )
        
        return ChatResponse(
            response=ai_response,
            service="openrouter",
            is_configured=True
        )
        
    except Exception as e:
        # 如果AI服务失败，返回错误信息
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI服务暂时不可用: {str(e)}"
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