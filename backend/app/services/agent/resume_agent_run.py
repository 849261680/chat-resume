"""用于承载一次 Resume Agent 运行、恢复和事件回放的生命周期。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, cast
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agents.resume.harness import ResumeAgentHarness
from app.infra.request_context import log_context
from app.runtime.permissions import confirmation_manager
from app.services.agent.resume_agent_persistence import ResumeAgentPersistence
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


class ResumeAgentRunOrchestrator:
    """用于把一次 Resume Agent 运行的 session、事件和持久化收敛到同一 Module。"""

    def __init__(
        self,
        db: Session,
        *,
        agent_factory: Callable[[], Any],
        confirmation_sessions: Any = confirmation_manager,
    ):
        """用于初始化运行生命周期所需依赖。"""
        self.db = db
        self.agent_factory = agent_factory
        self.confirmation_sessions = confirmation_sessions

    async def stream_events(
        self,
        request: ResumeAgentStreamInput,
    ) -> AsyncIterator[ResumeStreamEvent]:
        """用于驱动一次完整 Resume Agent SSE 运行。"""
        self.ensure_stream_supported(request)
        session_id = uuid4().hex
        confirmation_queue = self.confirmation_sessions.create(session_id)
        try:
            async for event in self._stream_events_with_context(
                request=request,
                session_id=session_id,
                confirmation_queue=confirmation_queue,
            ):
                yield event
        finally:
            self.confirmation_sessions.remove(session_id)

    def resume_session(self, *, session_id: str, user_id: int) -> dict[str, Any]:
        """用于恢复因工具确认中断而暂停的简历 Agent session。"""
        store = AgentSessionStore(self.db)
        session = store.get_session(session_id)
        self._ensure_resume_session_access(session, session_id=session_id, user_id=user_id)
        resume_id = self._resume_id_from_session(session, session_id=session_id)

        resume_service = ResumeService(self.db)
        resume = self._get_resume_for_user(
            resume_service,
            resume_id=resume_id,
            user_id=user_id,
        )
        persistence = ResumeAgentPersistence(resume_service)
        resume_content = persistence.load_resume_content(resume)
        original_resume = deepcopy(resume_content)

        result = ResumeAgentHarness(self.db, session_store=store).resume_session(
            session_id=session_id,
            resume_content=resume_content,
            allowed_sections=persistence.allowed_sections(resume_content),
        )
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result["message"],
            )

        latest_resume_content = result["resume_content"]
        if result.get("applied"):
            persistence.persist_resume_if_changed(
                resume_id=resume_id,
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
        return [
            self._replay_payload(session_id, event)
            for event in store.list_stream_events(
                session_id,
                after_sequence=after_sequence,
            )
        ]

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

    async def _stream_events_with_context(
        self,
        *,
        request: ResumeAgentStreamInput,
        session_id: str,
        confirmation_queue: Any,
    ) -> AsyncIterator[ResumeStreamEvent]:
        """用于在日志上下文中执行流式运行并把异常转成公开事件。"""
        with log_context(
            request_id=request.request_id,
            session_id=session_id,
            client_request_id=request.client_request_id,
        ):
            try:
                async for event in self._run_stream(
                    request=request,
                    session_id=session_id,
                    confirmation_queue=confirmation_queue,
                ):
                    yield event
            except HTTPException as exc:
                yield stream_error_event(str(exc.detail))
            except Exception as exc:
                logger.exception("Resume agent stream failed")
                yield stream_error_event(f"AI服务暂时不可用: {exc}")

    async def _run_stream(
        self,
        *,
        request: ResumeAgentStreamInput,
        session_id: str,
        confirmation_queue: Any,
    ) -> AsyncIterator[ResumeStreamEvent]:
        """用于执行成功路径上的 Resume Agent 流式运行。"""
        resume_service = ResumeService(self.db)
        resume = self._get_resume_for_user(
            resume_service,
            resume_id=request.resume_id,
            user_id=request.user_id,
        )
        persistence = ResumeAgentPersistence(resume_service)
        resume_content = persistence.load_resume_content(resume)
        original_resume = deepcopy(resume_content)
        store = AgentSessionStore(self.db)
        harness = ResumeAgentHarness(self.db, session_store=store)

        self._create_session(
            harness,
            request=request,
            session_id=session_id,
        )
        yield self._record_stream_event(
            store,
            session_id=session_id,
            event=session_started_event(session_id),
        )

        latest_resume_content = None
        async for event in self._run_harness_stream(
            harness=harness,
            resume_service=resume_service,
            request=request,
            session_id=session_id,
            resume_content=resume_content,
            confirmation_queue=confirmation_queue,
        ):
            if event.get("internal_only"):
                continue
            latest_resume_content = self._latest_resume_content(
                event,
                latest_resume_content,
            )
            yield self._record_stream_event(
                store,
                session_id=session_id,
                event=event,
            )

        persistence.persist_resume_if_changed(
            resume_id=request.resume_id,
            latest_resume_content=latest_resume_content,
            original_resume=original_resume,
        )
        persistence.sync_visibility_if_changed(
            resume=resume,
            resume_id=request.resume_id,
            request_visible=request.visible_modules,
            latest_resume_content=latest_resume_content,
        )
        logger.debug("Resume agent stream completed")
        yield self._record_stream_event(
            store,
            session_id=session_id,
            event=stream_done_event(resume_content=latest_resume_content),
        )

    async def _run_harness_stream(
        self,
        *,
        harness: ResumeAgentHarness,
        resume_service: ResumeService,
        request: ResumeAgentStreamInput,
        session_id: str,
        resume_content: dict[str, Any],
        confirmation_queue: Any,
    ) -> AsyncIterator[ResumeStreamEvent]:
        """用于把应用层输入转换为 harness 的运行参数。"""
        conversation_history = (
            []
            if self._should_ignore_history_for_request(request.message)
            else request.chat_history
        )
        event_stream = harness.run_resume_stream(
            session_id=session_id,
            agent=self.agent_factory(),
            user_message=request.message,
            resume_content=resume_content,
            conversation_history=conversation_history,
            confirmation_queue=confirmation_queue,
            allowed_sections=ResumeAgentPersistence(resume_service).allowed_sections(
                resume_content,
                visible_modules=request.visible_modules,
            ),
            event_callback=None,
            user_id=request.user_id,
            resume_id=request.resume_id,
            list_job_posts_reader=resume_service.list_job_post_payloads,
            read_job_post_reader=resume_service.get_job_post_payload,
            visible_modules=request.visible_modules,
        )
        async for event in event_stream:
            yield event

    @staticmethod
    def _create_session(
        harness: ResumeAgentHarness,
        *,
        request: ResumeAgentStreamInput,
        session_id: str,
    ) -> None:
        """用于创建持久化 session 并记录首条用户消息。"""
        harness.create_resume_session(
            session_id=session_id,
            user_id=request.user_id,
            resume_id=request.resume_id,
            user_message=request.message,
            visible_modules=request.visible_modules,
        )

    @staticmethod
    def _ensure_resume_session_access(
        session: Any,
        *,
        session_id: str,
        user_id: int,
    ) -> None:
        """用于校验恢复请求是否可以访问目标简历优化 session。"""
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

    @staticmethod
    def _resume_id_from_session(session: Any, *, session_id: str) -> int:
        """用于在恢复 session 前把 resume_id 收窄成整数。"""
        resume_id = getattr(session, "resume_id", None)
        if isinstance(resume_id, int):
            return resume_id
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session {session_id} 未关联有效简历",
        )

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
    def _latest_resume_content(
        event: ResumeStreamEvent,
        current: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """用于从流事件中提取最新的简历内容快照。"""
        resume_content = event.get("resume_content")
        if isinstance(resume_content, dict):
            return resume_content
        return current

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

    @staticmethod
    def _replay_payload(session_id: str, event: Any) -> ResumeStreamEvent:
        """用于把持久化事件转换成可公开回放的 SSE payload。"""
        payload = event.payload if isinstance(event.payload, dict) else {}
        replay_payload = dict(payload)
        replay_payload.pop("log_context", None)
        replay_payload["event_id"] = f"{session_id}:{event.sequence}"
        return cast(ResumeStreamEvent, replay_payload)


__all__ = ["ResumeAgentRunOrchestrator", "ResumeAgentStreamInput"]
