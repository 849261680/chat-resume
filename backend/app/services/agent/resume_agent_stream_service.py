"""用于提供简历 Agent 流式服务的对外 facade。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm import Session

from app.agents.resume.agent import ResumeAgent
from app.services.agent.resume_agent_run import (
    ResumeAgentRunOrchestrator,
    ResumeAgentStreamInput,
)
from app.types.stream import ResumeStreamEvent


class ResumeAgentStreamService:
    """用于保持 HTTP 层调用稳定，并委托运行 Module 处理 Agent 生命周期。"""

    def __init__(self, db: Session):
        """用于初始化流式服务 facade。"""
        self._run = ResumeAgentRunOrchestrator(
            db,
            agent_factory=lambda: ResumeAgent(),
        )

    async def stream_events(
        self,
        request: ResumeAgentStreamInput,
    ) -> AsyncIterator[ResumeStreamEvent]:
        """用于驱动一次完整的简历 Agent SSE 事件流。"""
        async for event in self._run.stream_events(request):
            yield event

    def resume_session(self, *, session_id: str, user_id: int) -> dict[str, Any]:
        """用于恢复因工具确认中断而暂停的简历 Agent session。"""
        return self._run.resume_session(session_id=session_id, user_id=user_id)

    def replay_stream_events(
        self,
        *,
        session_id: str,
        user_id: int,
        after_sequence: int,
    ) -> list[ResumeStreamEvent]:
        """用于按 SSE cursor 回放指定 session 的公开流事件。"""
        return self._run.replay_stream_events(
            session_id=session_id,
            user_id=user_id,
            after_sequence=after_sequence,
        )

    @staticmethod
    def ensure_stream_supported(request: ResumeAgentStreamInput) -> None:
        """用于兼容旧字段并拒绝已迁移的面试入口。"""
        ResumeAgentRunOrchestrator.ensure_stream_supported(request)

    _load_resume_content = staticmethod(ResumeAgentRunOrchestrator._load_resume_content)
    _persist_resume_if_changed = staticmethod(
        ResumeAgentRunOrchestrator._persist_resume_if_changed
    )
    _record_stream_event = staticmethod(ResumeAgentRunOrchestrator._record_stream_event)
    _strip_visibility_meta = staticmethod(
        ResumeAgentRunOrchestrator._strip_visibility_meta
    )
    _sync_visibility_if_changed = staticmethod(
        ResumeAgentRunOrchestrator._sync_visibility_if_changed
    )


__all__ = ["ResumeAgentStreamInput", "ResumeAgentStreamService"]
