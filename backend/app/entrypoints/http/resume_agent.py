"""
智能聊天API端点模块

提供与 AI Agent 聊天交互的 API 端点，包括简历优化。
"""

import json
import logging
from time import perf_counter
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user
from app.infra.config import settings
from app.infra.database import get_db
from app.infra.request_context import log_context
from app.runtime.permissions import confirmation_manager
from app.services.agent import (
    ResumeAgentConfirmationConflict,
    ResumeAgentSessionNotFound,
    ResumeAgentSessionService,
    ResumeAgentStreamInput,
    ResumeAgentStreamService,
)
from app.services.llm import ChatService
from app.state import AgentSessionStore
from app.types.stream import public_resume_stream_event

logger = logging.getLogger(__name__)

router = APIRouter()


def log_stream_phase(
    phase: str,
    *,
    started_at: float,
    stream_input: ResumeAgentStreamInput,
    **fields,
) -> None:
    """用于按开关记录 Resume Agent SSE 阶段耗时。"""
    if not settings.AGENT_TRACE_LOG_ENABLED:
        return
    logger.info(
        "resume_agent.stream.%s",
        phase,
        extra={
            "agent_trace": True,
            "stream_phase": phase,
            "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
            "client_request_id": stream_input.client_request_id or "-",
            "resume_id": stream_input.resume_id,
            "user_id": stream_input.user_id,
            **fields,
        },
    )


def parse_sse_event_id(value: str | None) -> tuple[str, int] | None:
    """用于把 Last-Event-ID 解析为 session_id 和事件序号。"""
    if not value or ":" not in value:
        return None
    session_id, sequence_text = value.rsplit(":", 1)
    if not session_id or not sequence_text.isdigit():
        return None
    return session_id, int(sequence_text)


def format_sse_event(payload: dict, *, event_id: str | None = None) -> str:
    """用于把事件 payload 格式化为 SSE 文本块。"""
    data = json.dumps(payload, ensure_ascii=False)
    if event_id:
        return f"id: {event_id}\ndata: {data}\n\n"
    return f"data: {data}\n\n"


class ChatRequest(BaseModel):
    """用于承载简历 Agent 聊天请求体。"""

    message: str
    resume_id: int
    chat_history: list = []  # 聊天历史，可选
    visible_modules: list[str] = []
    agent_type: str = "resume"
    is_interview: bool = False  # 兼容旧前端字段；面试主链路已迁移到 /api/interviews


class ConfirmToolRequest(BaseModel):
    """用于承载工具确认结果。"""

    session_id: str
    call_id: str
    confirmed: bool
    source: str | None = None


class ResumeSessionRequest(BaseModel):
    """用于承载暂停 session 的恢复请求。"""

    session_id: str


@router.post("/chat/stream")
async def chat_with_resume_stream(
    request: Request,
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于以 SSE 方式驱动一次完整的简历 Agent 流式对话。"""
    stream_input = ResumeAgentStreamInput(
        message=chat_request.message,
        resume_id=chat_request.resume_id,
        user_id=current_user["id"],
        request_id=getattr(request.state, "request_id", None),
        client_request_id=getattr(request.state, "client_request_id", None),
        chat_history=cast(list[dict[str, str]], chat_request.chat_history),
        visible_modules=chat_request.visible_modules,
        agent_type=chat_request.agent_type,
        is_interview=chat_request.is_interview,
    )
    ResumeAgentStreamService.ensure_stream_supported(stream_input)
    logger.debug(
        "resume_agent.stream.requested",
        extra={
            "agent_type": stream_input.agent_type,
            "resume_id": chat_request.resume_id,
            "user_id": current_user["id"],
            "message_chars": len(chat_request.message or ""),
            "client_request_id": stream_input.client_request_id or "-",
        },
    )
    stream_service = ResumeAgentStreamService(db)
    last_event_id = request.headers.get("last-event-id") or request.headers.get(
        "Last-Event-ID"
    )
    replay_cursor = parse_sse_event_id(last_event_id)

    if replay_cursor is not None:
        session_id, after_sequence = replay_cursor

        async def replay_stream():
            """用于根据 Last-Event-ID 回放已持久化的 SSE 事件。"""
            for payload in stream_service.replay_stream_events(
                session_id=session_id,
                user_id=current_user["id"],
                after_sequence=after_sequence,
            ):
                public_payload = public_resume_stream_event(payload)
                event_id = public_payload.get("event_id")
                yield format_sse_event(
                    public_payload,
                    event_id=event_id if isinstance(event_id, str) else None,
                )

        return StreamingResponse(
            replay_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    async def generate_stream():
        """用于生成简历 Agent 的流式响应。"""
        stream_started_at = perf_counter()
        first_public_sse_sent = False
        first_content_sent = False
        log_stream_phase(
            "stream_start",
            started_at=stream_started_at,
            stream_input=stream_input,
            message_chars=len(stream_input.message or ""),
            visible_module_count=len(stream_input.visible_modules),
        )
        async for event in stream_service.stream_events(stream_input):
            payload = public_resume_stream_event(event)
            event_id = payload.get("event_id")
            event_type = payload.get("event_type")
            if not first_public_sse_sent:
                first_public_sse_sent = True
                log_stream_phase(
                    "first_public_sse_sent",
                    started_at=stream_started_at,
                    stream_input=stream_input,
                    event_type=event_type or "-",
                    event_id=event_id or "-",
                )
            if payload.get("content") and not first_content_sent:
                first_content_sent = True
                log_stream_phase(
                    "first_content_sent",
                    started_at=stream_started_at,
                    stream_input=stream_input,
                    event_type=event_type or "-",
                    event_id=event_id or "-",
                    content_chars=len(str(payload.get("content") or "")),
                )
            if payload.get("done"):
                log_stream_phase(
                    "stream_done",
                    started_at=stream_started_at,
                    stream_input=stream_input,
                    event_type=event_type or "-",
                    event_id=event_id or "-",
                    had_content=first_content_sent,
                )
            if event_type in {
                "tool_call",
                "tool_pending",
                "tool_confirmed",
                "tool_rejected",
                "tool_result",
                "tool_call_failed",
            }:
                logger.info(
                    "resume_agent.sse.tool_event.sent",
                    extra={
                        "event_type": event_type,
                        "event_id": event_id,
                        "call_id": payload.get("call_id"),
                        "tool_name": payload.get("tool_id"),
                        "tool_display_name": payload.get("tool_display_name"),
                        "tool_pending": bool(payload.get("tool_pending")),
                        "tool_confirmed": bool(payload.get("tool_confirmed")),
                        "tool_rejected": bool(payload.get("tool_rejected")),
                        "diff_item_count": len(payload.get("diff_items") or []),
                        "tool_calls_count": len(payload.get("tool_calls") or []),
                        "has_result": "result" in payload,
                    },
                )
            yield format_sse_event(
                payload,
                event_id=event_id if isinstance(event_id, str) else None,
            )

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@router.post("/chat/confirm-tool")
async def confirm_tool(
    http_request: Request,
    request: ConfirmToolRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于接收前端对单个工具调用的确认或拒绝结果。"""
    with log_context(
        request_id=getattr(http_request.state, "request_id", None),
        session_id=request.session_id,
        tool_call_id=request.call_id,
        client_request_id=getattr(http_request.state, "client_request_id", None),
    ):
        started_at = perf_counter()
        logger.info(
            "resume_agent.confirm_tool.received",
            extra={
                "confirmed": request.confirmed,
                "source": request.source or "-",
            },
        )
        store = AgentSessionStore(db)
        service = ResumeAgentSessionService(
            store,
            confirmation_sessions=confirmation_manager,
        )
        try:
            result = await service.confirm_tool(
                session_id=request.session_id,
                call_id=request.call_id,
                confirmed=request.confirmed,
                user_id=current_user["id"],
            )
        except ResumeAgentSessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ResumeAgentConfirmationConflict as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        if result.ok and not result.duplicate:
            logger.info(
                "Resume agent tool confirmation received confirmed=%s source=%s",
                request.confirmed,
                request.source or "-",
                extra={
                    "confirmed": request.confirmed,
                    "source": request.source or "-",
                },
            )
        logger.info(
            "resume_agent.confirm_tool.completed",
            extra={
                "confirmed": request.confirmed,
                "source": request.source or "-",
                "ok": result.ok,
                "duplicate": result.duplicate,
                "resumable": result.resumable,
                "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        return result.to_response()


@router.post("/chat/resume-session")
async def resume_agent_session(
    http_request: Request,
    request: ResumeSessionRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于恢复因确认中断而暂停的简历 Agent session。"""
    with log_context(
        request_id=getattr(http_request.state, "request_id", None),
        session_id=request.session_id,
        client_request_id=getattr(http_request.state, "client_request_id", None),
    ):
        service = ResumeAgentStreamService(db)
        return service.resume_session(
            session_id=request.session_id,
            user_id=current_user["id"],
        )


@router.get("/status")
async def get_ai_status():
    """用于返回当前 AI 聊天服务是否已完成配置。"""
    try:
        chat_service = ChatService()
        # 简单的状态检查
        if chat_service.api_key and chat_service.api_key.strip():
            return {
                "service": "openrouter",
                "status": "connected",
                "is_configured": True,
            }
        else:
            return {
                "service": "mock",
                "status": "not_configured",
                "is_configured": False,
            }
    except Exception:
        return {"service": "mock", "status": "error", "is_configured": False}
