"""用于定义和序列化简历 Agent SSE 通道的事件载荷结构。"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

ResumeStreamEventType = Literal[
    "session_started",
    "text_delta",
    "tool_call",
    "tool_pending",
    "tool_confirmed",
    "tool_rejected",
    "tool_call_failed",
    "tool_result",
    "user_input_request",
    "prompt_rendered",
    "llm_request",
    "llm_response",
    "done",
    "unknown",
]


class DiffItem(TypedDict, total=False):
    """用于描述单条结构化简历改动。"""

    before: str
    after: str
    reason: str


class ResumeStreamEvent(TypedDict, total=False):
    """用于约束前后端流式事件字段的可选集合。"""

    event_type: ResumeStreamEventType
    content: str
    qr_images: list[str]
    tool_calls: list[dict[str, Any]]
    resume_content: dict[str, Any] | None
    tool_call_started: bool
    tool_pending: bool
    tool_confirmed: bool
    tool_rejected: bool
    tool_call_failed: bool
    call_id: str
    tool_call: dict[str, Any]
    tool_id: str
    tool_name: str
    tool_display_name: str
    tool_input: dict[str, Any]
    diff_summary: str
    diff_items: list[DiffItem]
    result: Any
    display_message: str | None
    user_input_request: dict[str, Any]
    internal_only: bool
    prompt_rendered: bool
    llm_request: bool
    llm_response: bool
    agent_name: str
    system_prompt: str
    user_message_preview: str
    model: str
    messages: list[dict[str, Any]]
    params: dict[str, Any]
    tool_names: list[str | None]
    tool_profile: str
    tool_count: int
    message_count: int
    prompt_chars: int
    response_content: str
    latency_ms: float
    first_token_latency_ms: float | None
    confirmation_wait_ms: float
    usage: dict[str, Any]
    tool_call_count: int
    context: dict[str, Any] | None
    done: bool
    session_id: str
    event_id: str
    error: str


def public_resume_stream_event(
    event: ResumeStreamEvent,
) -> dict[str, Any]:
    """用于把内部事件收窄成允许传给前端的 SSE 载荷。"""
    return {
        key: value
        for key, value in event.items()
        if value is not None and key not in {"context", "internal_only"}
    }


def session_started_event(session_id: str) -> ResumeStreamEvent:
    """用于构造简历 Agent 流式会话开始事件。"""
    return {
        "event_type": "session_started",
        "session_id": session_id,
        "content": "",
        "done": False,
    }


def stream_done_event(
    *,
    resume_content: dict[str, Any] | None = None,
) -> ResumeStreamEvent:
    """用于构造简历 Agent 流式会话完成事件。"""
    event: ResumeStreamEvent = {
        "event_type": "done",
        "content": "",
        "qr_images": [],
        "tool_calls": [],
        "done": True,
    }
    if resume_content is not None:
        event["resume_content"] = resume_content
    return event


def stream_error_event(error: str) -> ResumeStreamEvent:
    """用于构造简历 Agent 流式会话失败事件。"""
    return {
        "event_type": "done",
        "error": error,
        "done": True,
    }


__all__ = [
    "DiffItem",
    "ResumeStreamEvent",
    "ResumeStreamEventType",
    "public_resume_stream_event",
    "session_started_event",
    "stream_done_event",
    "stream_error_event",
]
