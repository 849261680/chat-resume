"""用于管理简历 Agent 会话状态和工具确认。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.runtime.permissions import ConfirmationSessionManager, confirmation_manager
from app.runtime.tool_confirmation import normalize_confirmation_feedback
from app.state.models import AgentEvent
from app.state.store import AgentSessionStore


class ResumeAgentSessionNotFound(Exception):
    """Raised when the current user cannot access the requested agent session."""


class ResumeAgentConfirmationConflict(Exception):
    """Raised when a tool confirmation does not match the pending session state."""


@dataclass(frozen=True, slots=True)
class ConfirmToolResult:
    """Stable response shape for a tool confirmation transition."""

    ok: bool
    duplicate: bool = False
    resumable: bool = False
    message: str | None = None

    def to_response(self) -> dict[str, Any]:
        """用于转换为响应。"""
        response: dict[str, Any] = {"ok": self.ok}
        if self.duplicate:
            response["duplicate"] = True
        if self.resumable:
            response["resumable"] = True
        if self.message:
            response["message"] = self.message
        return response


class ResumeAgentSessionService:
    """Owns Resume Agent session state transitions that outlive one HTTP handler."""

    def __init__(
        self,
        session_store: AgentSessionStore,
        confirmation_sessions: ConfirmationSessionManager = confirmation_manager,
    ):
        """用于初始化当前对象。"""
        self.session_store = session_store
        self.confirmation_sessions = confirmation_sessions

    async def confirm_tool(
        self,
        *,
        session_id: str,
        call_id: str,
        confirmed: bool,
        user_id: int,
        source: str | None = None,
        feedback: str | None = None,
    ) -> ConfirmToolResult:
        """用于确认工具。"""
        session = self.session_store.get_session(session_id)
        if not session or session.user_id != user_id:
            raise ResumeAgentSessionNotFound(f"Session {session_id} 不存在")
        clean_feedback = normalize_confirmation_feedback(feedback)

        latest_pending = self.session_store.get_latest_event(
            session_id,
            event_type="tool_call_previewed",
        )
        pending_call_id = self._pending_call_id(latest_pending)
        if pending_call_id != call_id:
            raise ResumeAgentConfirmationConflict(
                "当前 session 没有匹配的待确认工具调用"
            )

        if session.status != "waiting_confirmation":
            return ConfirmToolResult(
                ok=True,
                duplicate=True,
                message="该工具确认已处理",
            )

        queue = self.confirmation_sessions.get(session_id)
        if queue is None:
            self.session_store.append_confirmation_event(
                session_id=session_id,
                call_id=call_id,
                confirmed=confirmed,
                tool_name=self._pending_tool_name(latest_pending),
                active_stream=False,
                source=source or "user",
                feedback=clean_feedback,
            )
            self.session_store.update_status(
                session_id,
                "paused",
                current_step=call_id,
            )
            return ConfirmToolResult(
                ok=False,
                resumable=True,
                message=(
                    "确认结果已记录，但当前流式连接已结束，"
                    "需要恢复 session 后继续执行"
                ),
            )

        self.session_store.update_status(
            session_id,
            "running",
            clear_current_step=True,
        )
        await queue.put(
            {"confirmed": confirmed, "feedback": clean_feedback}
            if clean_feedback
            else confirmed
        )
        return ConfirmToolResult(ok=True)

    @staticmethod
    def _pending_call_id(event: AgentEvent | None) -> str | None:
        """用于处理待确认调用标识。"""
        if not event or not isinstance(event.payload, dict):
            return None
        call_id = event.payload.get("call_id")
        return call_id if isinstance(call_id, str) else None

    @staticmethod
    def _pending_tool_name(event: AgentEvent | None) -> str | None:
        """用于处理待确认工具name。"""
        if not event or not isinstance(event.payload, dict):
            return None
        tool_name = event.payload.get("tool_name")
        return tool_name if isinstance(tool_name, str) else None


__all__ = [
    "ConfirmToolResult",
    "ResumeAgentConfirmationConflict",
    "ResumeAgentSessionNotFound",
    "ResumeAgentSessionService",
]
