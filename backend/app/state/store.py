"""用于统一读写 Agent session 和事件日志。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infra.request_context import get_log_context
from app.state.models import AgentEvent, AgentSession


class AgentSessionStore:
    """用于封装 session 与 event 的数据库访问细节。"""

    def __init__(self, db: Session):
        """用于注入当前请求使用的数据库会话。"""
        self.db = db

    def create_session(
        self,
        *,
        user_id: int,
        task_type: str,
        resume_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> AgentSession:
        """用于创建一条新的 Agent session 记录。"""
        merged_metadata = self._merge_log_context_metadata(
            metadata,
            session_id=session_id,
        )
        session = AgentSession(
            id=session_id or uuid4().hex,
            user_id=user_id,
            resume_id=resume_id,
            task_type=task_type,
            status="created",
            metadata_json=merged_metadata,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: str) -> AgentSession | None:
        """用于按 session_id 查询单条 Agent session。"""
        return self.db.query(AgentSession).filter(AgentSession.id == session_id).first()

    def update_status(
        self,
        session_id: str,
        status: str,
        *,
        current_step: str | None = None,
        failed_reason: str | None = None,
        clear_current_step: bool = False,
    ) -> AgentSession | None:
        """用于更新 session 当前状态和执行位置。"""
        session = self.get_session(session_id)
        if not session:
            return None
        session.status = status
        if clear_current_step:
            session.current_step = None
        elif current_step is not None:
            session.current_step = current_step
        if failed_reason is not None:
            session.failed_reason = failed_reason
        if status in {"completed", "failed", "cancelled"}:
            session.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(session)
        return session

    def append_event(
        self,
        *,
        session_id: str,
        event_type: str,
        source: str,
        payload: dict[str, Any] | None = None,
    ) -> AgentEvent:
        """用于向指定 session 追加一条有序事件。"""
        sequence = self._next_sequence(session_id)
        enriched_payload = self._merge_log_context_payload(
            payload,
            session_id=session_id,
        )
        event = AgentEvent(
            session_id=session_id,
            sequence=sequence,
            event_type=event_type,
            source=source,
            payload=enriched_payload,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_events(
        self,
        session_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[AgentEvent]:
        """用于按顺序读取某个 session 的事件列表。"""
        query = (
            self.db.query(AgentEvent)
            .filter(AgentEvent.session_id == session_id)
            .order_by(AgentEvent.sequence.asc())
        )
        if after_sequence is not None:
            query = query.filter(AgentEvent.sequence > after_sequence)
        if limit is not None:
            query = query.limit(limit)
        return list(query.all())

    def get_latest_event(
        self,
        session_id: str,
        *,
        event_type: str | None = None,
    ) -> AgentEvent | None:
        """用于读取某个 session 最近的一条事件。"""
        query = self.db.query(AgentEvent).filter(AgentEvent.session_id == session_id)
        if event_type is not None:
            query = query.filter(AgentEvent.event_type == event_type)
        return query.order_by(AgentEvent.sequence.desc()).first()

    def get_latest_waiting_confirmation_session(
        self,
        *,
        user_id: int,
        resume_id: int,
    ) -> AgentSession | None:
        """用于读取指定简历最新的待确认 Agent session。"""
        return (
            self.db.query(AgentSession)
            .filter(
                AgentSession.user_id == user_id,
                AgentSession.resume_id == resume_id,
                AgentSession.status == "waiting_confirmation",
            )
            .order_by(AgentSession.updated_at.desc(), AgentSession.created_at.desc())
            .first()
        )

    def get_timed_out_paused_sessions(self, timeout_seconds: int) -> list[str]:
        """返回所有超过 timeout_seconds 仍处于 paused 状态的 session_id 列表。"""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
        rows = (
            self.db.query(AgentSession.id)
            .filter(
                AgentSession.status == "paused",
                AgentSession.updated_at <= cutoff,
            )
            .all()
        )
        return [row.id for row in rows]

    def append_confirmation_event(
        self,
        *,
        session_id: str,
        call_id: str,
        confirmed: bool,
        source: str = "user",
        tool_name: str | None = None,
        active_stream: bool = True,
        feedback: str | None = None,
    ) -> AgentEvent:
        """用于把工具确认结果写成标准事件。"""
        payload: dict[str, Any] = {
            "call_id": call_id,
            "tool_name": tool_name,
            "active_stream": active_stream,
        }
        if feedback:
            payload["feedback"] = feedback
        return self.append_event(
            session_id=session_id,
            event_type="tool_call_confirmed" if confirmed else "tool_call_rejected",
            source=source,
            payload=payload,
        )

    def append_stream_event(
        self,
        *,
        session_id: str,
        payload: dict[str, Any],
    ) -> AgentEvent:
        """用于记录一条可被 SSE cursor 回放的公开流事件。"""
        return self.append_event(
            session_id=session_id,
            event_type="stream_event",
            source="sse",
            payload=payload,
        )

    def list_stream_events(
        self,
        session_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[AgentEvent]:
        """用于读取某个 session 在 cursor 之后的公开流事件。"""
        query = (
            self.db.query(AgentEvent)
            .filter(
                AgentEvent.session_id == session_id,
                AgentEvent.event_type == "stream_event",
            )
            .order_by(AgentEvent.sequence.asc())
        )
        if after_sequence is not None:
            query = query.filter(AgentEvent.sequence > after_sequence)
        if limit is not None:
            query = query.limit(limit)
        return list(query.all())

    def append_events(
        self,
        session_id: str,
        events: Iterable[tuple[str, str, dict[str, Any]]],
    ) -> list[AgentEvent]:
        """用于批量追加多条事件，复用统一落库逻辑。"""
        return [
            self.append_event(
                session_id=session_id,
                event_type=event_type,
                source=source,
                payload=payload,
            )
            for event_type, source, payload in events
        ]

    def _next_sequence(self, session_id: str) -> int:
        """用于为新事件分配递增序号。"""
        current = (
            self.db.query(func.max(AgentEvent.sequence))
            .filter(AgentEvent.session_id == session_id)
            .scalar()
        )
        return int(current or 0) + 1

    @staticmethod
    def _merge_log_context_metadata(
        metadata: dict[str, Any] | None,
        *,
        session_id: str | None,
    ) -> dict[str, Any]:
        """用于把日志上下文合并进 session 元数据。"""
        merged = dict(metadata or {})
        log_context = AgentSessionStore._current_log_context(session_id=session_id)
        if not log_context:
            return merged
        existing = merged.get("log_context")
        base = dict(existing) if isinstance(existing, dict) else {}
        base.update(log_context)
        merged["log_context"] = base
        return merged

    @staticmethod
    def _merge_log_context_payload(
        payload: dict[str, Any] | None,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        """用于把日志上下文合并进事件 payload。"""
        merged = dict(payload or {})
        log_context = AgentSessionStore._current_log_context(session_id=session_id)
        if not log_context:
            return merged
        existing = merged.get("log_context")
        base = dict(existing) if isinstance(existing, dict) else {}
        base.update(log_context)
        merged["log_context"] = base
        return merged

    @staticmethod
    def _current_log_context(*, session_id: str | None) -> dict[str, str]:
        """用于从当前请求上下文提取日志关联字段。"""
        context = get_log_context()
        log_context = {
            "request_id": context["request_id"],
            "session_id": session_id or context["session_id"],
            "tool_call_id": context["tool_call_id"],
            "client_request_id": context["client_request_id"],
        }
        return {
            key: value
            for key, value in log_context.items()
            if isinstance(value, str) and value
        }


__all__ = ["AgentSessionStore"]
