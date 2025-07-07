from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.openrouter_service import OpenRouterService
import json

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

@router.post("/chat/stream")
async def chat_with_resume_stream(
    chat_request: ChatRequest
):
    """与AI助手进行流式聊天，基于简历内容"""
    
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
    
    async def generate_stream():
        try:
            openrouter_service = OpenRouterService()
            
            # 构建消息上下文
            resume_text = openrouter_service._format_resume_content(mock_resume_content)
            system_prompt = f"""你是一位资深的简历优化专家和职业顾问，拥有多年的HR和招聘经验。请基于用户的简历内容提供专业、有针对性的建议。

用户当前简历信息：
{resume_text}

## 核心服务能力

作为专业的简历顾问，我可以提供以下服务：

1. **内容优化** - 改进表达方式，使用行业术语和关键词
2. **结构调整** - 优化信息层次，提高可读性  
3. **亮点突出** - 识别并强化核心竞争力
4. **匹配度提升** - 针对目标职位定制内容
5. **专业建议** - 基于行业标准提供改进方案

## 回复格式要求

请用Markdown格式回复，遵循以下规范：

- 使用清晰的标题结构（## 主标题，### 副标题）
- 用有序或无序列表组织要点
- 重要内容用**粗体**强调
- 用代码块展示具体的文案示例
- 保持段落简洁，逻辑清晰
- 使用中文回复，考虑中国职场文化

请根据用户的具体问题，提供专业的指导意见。"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chat_request.message}
            ]
            
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