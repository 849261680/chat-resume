"""用于编排简历 Agent 流式会话和恢复流程。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, cast
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agents.resume.agent import ResumeAgent
from app.infra.request_context import log_context
from app.agents.resume.harness import ResumeAgentHarness
from app.runtime.permissions import confirmation_manager
from app.services.domain import ResumeService
from app.state import AgentSessionStore
from app.types.stream import (
    ResumeStreamEvent,
    session_started_event,
    stream_done_event,
    stream_error_event,
)

logger = logging.getLogger(__name__)

_RESUME_SNAPSHOT_KEYWORDS = (
    "复述",
    "重复一遍",
    "当前简历",
    "现在的简历",
    "我的简历内容",
    "完整内容",
    "列出我的简历",
    "把我的简历写出来",
)
@dataclass(frozen=True)
class ResumeAgentStreamInput:
    """用于承载一次简历 Agent 流式会话的应用层输入。"""

    message: str
    resume_id: int
    user_id: int
    request_id: str | None
    client_request_id: str | None = None
    chat_history: list[dict[str, str]] = field(default_factory=list)
    visible_modules: list[str] = field(default_factory=list)
    agent_type: str = "resume"
    is_interview: bool = False


class ResumeAgentStreamService:
    """用于把 HTTP 之外的简历 Agent 会话规则集中在应用层。"""

    def __init__(self, db: Session):
        """用于初始化流式会话编排所需依赖。"""
        self.db = db

    async def stream_events(
        self,
        request: ResumeAgentStreamInput,
    ) -> AsyncIterator[ResumeStreamEvent]:
        """用于驱动一次完整的简历 Agent SSE 事件流。"""
        self.ensure_stream_supported(request)
        session_id = uuid4().hex
        confirmation_queue = confirmation_manager.create(session_id)

        with log_context(
            request_id=request.request_id,
            session_id=session_id,
            client_request_id=request.client_request_id,
        ):
            final_content_parts: list[str] = []
            latest_resume_content: dict[str, Any] | None = None

            try:
                resume_service = ResumeService(self.db)
                resume = self._get_resume_for_user(
                    resume_service,
                    resume_id=request.resume_id,
                    user_id=request.user_id,
                )
                resume_dict = self._load_resume_content(resume)
                original_resume = deepcopy(resume_dict)
                conversation_history = (
                    []
                    if self._should_ignore_history_for_request(request.message)
                    else request.chat_history
                )
                store = AgentSessionStore(self.db)
                harness = ResumeAgentHarness(self.db, session_store=store)
                harness.create_resume_session(
                    session_id=session_id,
                    user_id=request.user_id,
                    resume_id=request.resume_id,
                    user_message=request.message,
                    visible_modules=request.visible_modules,
                )
                yield self._record_stream_event(
                    store,
                    session_id=session_id,
                    event=session_started_event(session_id),
                )
                event_stream = harness.run_resume_stream(
                    session_id=session_id,
                    agent=ResumeAgent(),
                    user_message=request.message,
                    resume_content=resume_dict,
                    conversation_history=conversation_history,
                    confirmation_queue=confirmation_queue,
                    allowed_sections={k for k in resume_dict if not k.startswith("_")},
                    event_callback=None,
                    user_id=request.user_id,
                    resume_id=request.resume_id,
                    list_job_posts_reader=resume_service.list_job_post_payloads,
                    read_job_post_reader=resume_service.get_job_post_payload,
                    visible_modules=request.visible_modules,
                )
                async for event in event_stream:
                    if event.get("internal_only"):
                        continue
                    resume_content = event.get("resume_content")
                    if isinstance(resume_content, dict):
                        latest_resume_content = resume_content
                    content = event.get("content")
                    if content:
                        final_content_parts.append(content)
                    yield self._record_stream_event(
                        store,
                        session_id=session_id,
                        event=event,
                    )

                self._persist_resume_if_changed(
                    resume_service,
                    resume_id=request.resume_id,
                    latest_resume_content=latest_resume_content,
                    original_resume=original_resume,
                )
                logger.debug("Resume agent stream completed")
                yield self._record_stream_event(
                    store,
                    session_id=session_id,
                    event=stream_done_event(
                        resume_content=latest_resume_content,
                    ),
                )
            except HTTPException as exc:
                yield stream_error_event(str(exc.detail))
            except Exception as exc:
                logger.exception("Resume agent stream failed")
                yield stream_error_event(f"AI服务暂时不可用: {exc}")
            finally:
                confirmation_manager.remove(session_id)

    def resume_session(self, *, session_id: str, user_id: int) -> dict[str, Any]:
        """用于恢复因工具确认中断而暂停的简历 Agent session。"""
        store = AgentSessionStore(self.db)
        session = store.get_session(session_id)
        if not session or session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} 不存在",
            )
        if session.task_type != "resume_optimization":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前 session 不是简历优化任务",
            )
        if session.resume_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前 session 未关联简历",
            )

        resume_service = ResumeService(self.db)
        resume = self._get_resume_for_user(
            resume_service,
            resume_id=session.resume_id,
            user_id=user_id,
        )
        resume_content = self._load_resume_content(resume)
        original_resume = deepcopy(resume_content)

        result = ResumeAgentHarness(self.db, session_store=store).resume_session(
            session_id=session_id,
            resume_content=resume_content,
            allowed_sections={k for k in resume_content if not k.startswith("_")},
        )
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result["message"],
            )

        latest_resume_content = result["resume_content"]
        if result.get("applied"):
            self._persist_resume_if_changed(
                resume_service,
                resume_id=session.resume_id,
                latest_resume_content=latest_resume_content,
                original_resume=original_resume,
            )

        logger.info("Resume agent session resumed applied=%s", bool(result.get("applied")))
        return {
            "ok": True,
            "session_id": session_id,
            "applied": bool(result.get("applied")),
            "message": result["message"],
            "resume_content": latest_resume_content,
        }

    def replay_stream_events(
        self,
        *,
        session_id: str,
        user_id: int,
        after_sequence: int,
    ) -> list[ResumeStreamEvent]:
        """用于按 SSE cursor 回放指定 session 的公开流事件。"""
        store = AgentSessionStore(self.db)
        session = store.get_session(session_id)
        if not session or session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} 不存在",
            )
        replayed: list[ResumeStreamEvent] = []
        for event in store.list_stream_events(
            session_id,
            after_sequence=after_sequence,
        ):
            payload = event.payload if isinstance(event.payload, dict) else {}
            replay_payload = dict(payload)
            replay_payload.pop("log_context", None)
            replay_payload["event_id"] = f"{session_id}:{event.sequence}"
            replayed.append(cast(ResumeStreamEvent, replay_payload))
        return replayed

    @staticmethod
    def ensure_stream_supported(request: ResumeAgentStreamInput) -> None:
        """用于兼容旧字段并拒绝已迁移的面试入口。"""
        requested = (request.agent_type or "").strip().lower()
        if requested == "resume":
            return
        if requested in {"interview", "interviewer"} or request.is_interview:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="面试聊天入口已下线，请使用 /api/interviews 结构化面试链路。",
            )
        return

    @staticmethod
    def _should_ignore_history_for_request(message: str) -> bool:
        """用于识别应直接基于当前简历回答的问题。"""
        normalized = (message or "").strip()
        return any(keyword in normalized for keyword in _RESUME_SNAPSHOT_KEYWORDS)

    @staticmethod
    def _get_resume_for_user(
        resume_service: ResumeService,
        *,
        resume_id: int,
        user_id: int,
    ):
        """用于统一读取并校验当前用户可访问的简历。"""
        resume = resume_service.get_by_id(resume_id)
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="简历不存在",
            )
        if resume.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限访问此简历",
            )
        return resume

    @staticmethod
    def _dump_resume_content(resume: Any) -> dict[str, Any]:
        """用于把 ORM 简历内容安全收窄成可编辑字典。"""
        return cast(
            dict[str, Any],
            resume.content if isinstance(resume.content, dict) else {},
        )

    @staticmethod
    def _load_resume_content(resume: Any) -> dict[str, Any]:
        """用于读取完整简历内容供 Agent 推理和工具使用。"""
        return ResumeAgentStreamService._dump_resume_content(resume)

    @staticmethod
    def _persist_resume_if_changed(
        resume_service: ResumeService,
        *,
        resume_id: int,
        latest_resume_content: dict[str, Any] | None,
        original_resume: dict[str, Any],
    ) -> None:
        """用于只在内容确实变化时落库存储结构化简历。"""
        if latest_resume_content is None or latest_resume_content == original_resume:
            return
        resume_service.update(resume_id, {"content": latest_resume_content})

    @staticmethod
    def _record_stream_event(
        store: AgentSessionStore,
        *,
        session_id: str,
        event: ResumeStreamEvent,
    ) -> ResumeStreamEvent:
        """用于给公开 SSE 事件分配 cursor 并写入事件日志。"""
        payload = dict(event)
        stored = store.append_stream_event(session_id=session_id, payload=payload)
        payload["event_id"] = f"{session_id}:{stored.sequence}"
        return cast(ResumeStreamEvent, payload)

__all__ = ["ResumeAgentStreamInput", "ResumeAgentStreamService"]
