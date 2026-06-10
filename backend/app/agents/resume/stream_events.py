"""用于定义简历 Agent 流式事件的标准化工具。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.types.stream import DiffItem, ResumeStreamEvent, ResumeStreamEventType

_EVENT_TYPE_BY_NAME: dict[str, ResumeStreamEventType] = {
    "session_started": "session_started",
    "text_delta": "text_delta",
    "tool_call": "tool_call",
    "tool_pending": "tool_pending",
    "tool_confirmed": "tool_confirmed",
    "tool_rejected": "tool_rejected",
    "tool_call_failed": "tool_call_failed",
    "tool_result": "tool_result",
    "user_input_request": "user_input_request",
    "prompt_rendered": "prompt_rendered",
    "llm_request": "llm_request",
    "llm_response": "llm_response",
    "done": "done",
    "unknown": "unknown",
}


def infer_event_type(event: Mapping[str, Any]) -> ResumeStreamEventType:
    """用于推断事件类型。"""
    if event.get("tool_pending"):
        return "tool_pending"
    if event.get("tool_call_started"):
        return "tool_call"
    if event.get("tool_confirmed"):
        return "tool_confirmed"
    if event.get("tool_rejected"):
        return "tool_rejected"
    if event.get("tool_call_failed"):
        return "tool_call_failed"
    if event.get("prompt_rendered"):
        return "prompt_rendered"
    if event.get("llm_request"):
        return "llm_request"
    if event.get("llm_response"):
        return "llm_response"
    if event.get("done"):
        return "done"
    if event.get("user_input_request"):
        return "user_input_request"
    if event.get("display_message") and event.get("result") is not None:
        return "tool_result"
    if event.get("content"):
        return "text_delta"
    if event.get("session_id"):
        return "session_started"
    return "unknown"


def normalize_event_type(
    value: Any,
    event: Mapping[str, Any],
) -> ResumeStreamEventType:
    """用于标准化事件类型。"""
    if isinstance(value, str):
        event_type = _EVENT_TYPE_BY_NAME.get(value)
        if event_type is not None:
            return event_type
    return infer_event_type(event)


def normalize_diff_items(value: Any) -> list[DiffItem]:
    """用于标准化差异条目。"""
    if not isinstance(value, list):
        return []
    diff_items: list[DiffItem] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        diff_item: DiffItem = {}
        for key in ("before", "after", "reason"):
            raw = item.get(key)
            if raw is not None:
                diff_item[key] = str(raw)
        if diff_item:
            diff_items.append(diff_item)
    return diff_items


def _list_of_strings(value: Any) -> list[str]:
    """用于处理列表of字符串。"""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _list_of_optional_strings(value: Any) -> list[str | None]:
    """用于处理列表of可选字符串。"""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) or item is None]


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    """用于处理列表of字典。"""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    """用于处理字典ornone。"""
    return value if isinstance(value, dict) else None


def _string_or_none(value: Any) -> str | None:
    """用于处理字符串ornone。"""
    return value if isinstance(value, str) else None


def _float_or_none(value: Any) -> float | None:
    """用于处理浮点数ornone。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _int_or_none(value: Any) -> int | None:
    """用于处理整数ornone。"""
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def normalize_resume_stream_payload(
    event: Mapping[str, Any],
    *,
    resume_content: dict[str, Any] | None = None,
) -> ResumeStreamEvent:
    """用于标准化简历流式载荷。"""
    payload: ResumeStreamEvent = {
        "event_type": normalize_event_type(event.get("event_type"), event),
        "content": str(event.get("content") or ""),
        "qr_images": _list_of_strings(event.get("qr_images")),
        "tool_calls": _list_of_dicts(event.get("tool_calls")),
        "resume_content": resume_content,
        "diff_items": normalize_diff_items(event.get("diff_items")),
        "done": bool(event.get("done", False)),
    }
    for key in (
        "tool_call_started",
        "tool_pending",
        "tool_confirmed",
        "tool_rejected",
        "tool_call_failed",
        "internal_only",
        "prompt_rendered",
        "llm_request",
        "llm_response",
    ):
        value = event.get(key)
        if isinstance(value, bool):
            payload[key] = value

    for key in (
        "call_id",
        "tool_name",
        "tool_display_name",
        "diff_summary",
        "agent_name",
        "system_prompt",
        "user_message_preview",
        "model",
        "response_content",
        "session_id",
        "error",
        "tool_profile",
    ):
        value = _string_or_none(event.get(key))
        if value is not None:
            payload[key] = value

    tool_id = _string_or_none(event.get("tool_id")) or _tool_id_from_event(event)
    if tool_id is not None:
        payload["tool_id"] = tool_id
    display_name = _string_or_none(event.get("tool_display_name")) or _string_or_none(
        event.get("tool_name")
    )
    if display_name is not None:
        payload["tool_display_name"] = display_name

    tool_call = _dict_or_none(event.get("tool_call"))
    if tool_call is not None:
        payload["tool_call"] = tool_call
    tool_input = _dict_or_none(event.get("tool_input"))
    if tool_input is not None:
        payload["tool_input"] = tool_input
    params = _dict_or_none(event.get("params"))
    if params is not None:
        payload["params"] = params
    messages = _list_of_dicts(event.get("messages"))
    if messages:
        payload["messages"] = messages
    tool_names = _list_of_optional_strings(event.get("tool_names"))
    if tool_names:
        payload["tool_names"] = tool_names
    latency_ms = _float_or_none(event.get("latency_ms"))
    if latency_ms is not None:
        payload["latency_ms"] = latency_ms
    tool_call_count = _int_or_none(event.get("tool_call_count"))
    if tool_call_count is not None:
        payload["tool_call_count"] = tool_call_count
    for key in ("tool_count", "message_count", "prompt_chars"):
        value = _int_or_none(event.get(key))
        if value is not None:
            payload[key] = value
    for key in ("first_token_latency_ms", "confirmation_wait_ms"):
        value = _float_or_none(event.get(key))
        if value is not None:
            payload[key] = value
    usage = _dict_or_none(event.get("usage"))
    if usage is not None:
        payload["usage"] = usage
    if "result" in event:
        payload["result"] = event.get("result")
    user_input_request = _dict_or_none(event.get("user_input_request"))
    if user_input_request is not None:
        payload["user_input_request"] = user_input_request
    display_message = event.get("display_message")
    if isinstance(display_message, str) or display_message is None:
        payload["display_message"] = display_message
    return payload


def text_delta_event(
    *,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
) -> ResumeStreamEvent:
    """用于处理文本增量事件。"""
    return {
        "event_type": "text_delta",
        "content": content,
        "tool_calls": tool_calls or [],
        "context": context,
        "done": False,
    }


def prompt_rendered_event(
    *,
    agent_name: str,
    system_prompt: str,
    user_message_preview: str,
) -> ResumeStreamEvent:
    """用于处理提示词渲染结果事件。"""
    return {
        "event_type": "prompt_rendered",
        "internal_only": True,
        "prompt_rendered": True,
        "agent_name": agent_name,
        "system_prompt": system_prompt,
        "user_message_preview": user_message_preview,
        "done": False,
    }


def llm_request_event(
    *,
    agent_name: str,
    model: str,
    messages: list[dict[str, Any]],
    params: dict[str, Any],
    tool_names: list[str | None],
    tool_profile: str,
    prompt_chars: int,
) -> ResumeStreamEvent:
    """用于处理模型请求事件。"""
    return {
        "event_type": "llm_request",
        "internal_only": True,
        "llm_request": True,
        "agent_name": agent_name,
        "model": model,
        "messages": messages,
        "params": params,
        "tool_names": tool_names,
        "tool_profile": tool_profile,
        "tool_count": len(tool_names),
        "message_count": len(messages),
        "prompt_chars": prompt_chars,
        "done": False,
    }


def llm_response_event(
    *,
    agent_name: str,
    model: str,
    response_content: str,
    tool_call_count: int,
    latency_ms: float,
    first_token_latency_ms: float | None,
    usage: dict[str, Any] | None,
    confirmation_wait_ms: float,
) -> ResumeStreamEvent:
    """用于处理模型响应事件。"""
    return {
        "event_type": "llm_response",
        "internal_only": True,
        "llm_response": True,
        "agent_name": agent_name,
        "model": model,
        "response_content": response_content,
        "tool_call_count": tool_call_count,
        "latency_ms": latency_ms,
        "first_token_latency_ms": first_token_latency_ms,
        "usage": usage or {},
        "confirmation_wait_ms": confirmation_wait_ms,
        "done": False,
    }


def tool_pending_event(
    *,
    call_id: str,
    tool_id: str,
    tool_call: dict[str, Any],
    tool_display_name: str,
    tool_input: dict[str, Any],
    diff_summary: str,
    diff_items: Any,
    tool_calls: list[dict[str, Any]],
) -> ResumeStreamEvent:
    """用于处理工具待确认事件。"""
    return {
        "event_type": "tool_pending",
        "content": "",
        "tool_pending": True,
        "call_id": call_id,
        "tool_id": tool_id,
        "tool_call": tool_call,
        "tool_name": tool_display_name,
        "tool_display_name": tool_display_name,
        "tool_input": tool_input,
        "diff_summary": diff_summary,
        "diff_items": normalize_diff_items(diff_items),
        "tool_calls": tool_calls,
        "done": False,
    }


def tool_call_event(
    *,
    call_id: str,
    tool_id: str,
    tool_call: dict[str, Any],
    tool_display_name: str,
    tool_input: dict[str, Any],
    display_message: str,
    tool_calls: list[dict[str, Any]],
) -> ResumeStreamEvent:
    """用于处理工具调用事件。"""
    return {
        "event_type": "tool_call",
        "content": "",
        "tool_call_started": True,
        "call_id": call_id,
        "tool_id": tool_id,
        "tool_call": tool_call,
        "tool_name": tool_display_name,
        "tool_display_name": tool_display_name,
        "tool_input": tool_input,
        "display_message": display_message,
        "tool_calls": tool_calls,
        "done": False,
    }


def tool_rejected_event(
    *,
    call_id: str,
    tool_id: str,
    tool_display_name: str,
    diff_summary: str,
    diff_items: Any,
    result: dict[str, Any],
    tool_calls: list[dict[str, Any]],
) -> ResumeStreamEvent:
    """用于处理工具rejected事件。"""
    return {
        "event_type": "tool_rejected",
        "content": "",
        "tool_rejected": True,
        "call_id": call_id,
        "tool_id": tool_id,
        "tool_name": tool_display_name,
        "tool_display_name": tool_display_name,
        "diff_summary": diff_summary,
        "diff_items": normalize_diff_items(diff_items),
        "result": result,
        "tool_calls": tool_calls,
        "done": False,
    }


def tool_call_failed_event(
    *,
    call_id: str,
    tool_id: str,
    tool_display_name: str,
    tool_calls: list[dict[str, Any]],
    result: Any,
    display_message: str | None,
) -> ResumeStreamEvent:
    """用于处理工具调用失败状态事件。"""
    return {
        "event_type": "tool_call_failed",
        "content": "",
        "tool_call_failed": True,
        "call_id": call_id,
        "tool_id": tool_id,
        "tool_name": tool_display_name,
        "tool_display_name": tool_display_name,
        "tool_calls": tool_calls,
        "result": result,
        "display_message": display_message,
        "done": False,
    }


def tool_confirmed_event(
    *,
    call_id: str,
    tool_id: str,
    tool_display_name: str,
    tool_calls: list[dict[str, Any]],
    qr_images: list[str],
    result: Any,
    display_message: str | None,
    diff_summary: str | None,
    diff_items: Any,
    context: dict[str, Any],
) -> ResumeStreamEvent:
    """用于处理工具已确认事件。"""
    payload: ResumeStreamEvent = {
        "event_type": "tool_confirmed",
        "content": "",
        "tool_confirmed": True,
        "call_id": call_id,
        "tool_id": tool_id,
        "tool_name": tool_display_name,
        "tool_display_name": tool_display_name,
        "tool_calls": tool_calls,
        "qr_images": qr_images,
        "result": result,
        "display_message": display_message,
        "diff_items": normalize_diff_items(diff_items),
        "context": context,
        "done": False,
    }
    if diff_summary is not None:
        payload["diff_summary"] = diff_summary
    return payload


def tool_result_event(
    *,
    call_id: str | None = None,
    tool_id: str | None = None,
    tool_display_name: str | None = None,
    tool_calls: list[dict[str, Any]],
    result: Any,
    display_message: str | None,
    context: dict[str, Any] | None,
) -> ResumeStreamEvent:
    """用于处理工具结果事件。"""
    payload: ResumeStreamEvent = {
        "event_type": "tool_result",
        "content": "",
        "tool_calls": tool_calls,
        "result": result,
        "display_message": display_message,
        "context": context,
        "done": False,
    }
    if call_id is not None:
        payload["call_id"] = call_id
    if tool_id is not None:
        payload["tool_id"] = tool_id
    if tool_display_name is not None:
        payload["tool_name"] = tool_display_name
        payload["tool_display_name"] = tool_display_name
    return payload


def user_input_request_event(
    *,
    call_id: str | None = None,
    tool_id: str | None = None,
    tool_display_name: str | None = None,
    result: dict[str, Any],
    display_message: str | None,
    tool_calls: list[dict[str, Any]],
) -> ResumeStreamEvent:
    """用于处理 Agent 向用户追问信息的结构化请求。"""
    payload: ResumeStreamEvent = {
        "event_type": "user_input_request",
        "content": "",
        "tool_calls": tool_calls,
        "result": result,
        "display_message": display_message,
        "done": False,
    }
    request = result.get("user_input_request")
    if isinstance(request, dict):
        payload["user_input_request"] = request
    if call_id is not None:
        payload["call_id"] = call_id
    if tool_id is not None:
        payload["tool_id"] = tool_id
    if tool_display_name is not None:
        payload["tool_name"] = tool_display_name
        payload["tool_display_name"] = tool_display_name
    return payload


def _tool_id_from_event(event: Mapping[str, Any]) -> str | None:
    """用于处理工具标识from事件。"""
    tool_call = event.get("tool_call")
    if not isinstance(tool_call, dict):
        return None
    function = tool_call.get("function")
    if not isinstance(function, dict):
        return None
    name = function.get("name")
    return name if isinstance(name, str) and name else None


__all__ = [
    "infer_event_type",
    "llm_request_event",
    "llm_response_event",
    "normalize_diff_items",
    "normalize_resume_stream_payload",
    "prompt_rendered_event",
    "text_delta_event",
    "tool_call_event",
    "tool_call_failed_event",
    "tool_confirmed_event",
    "tool_pending_event",
    "tool_rejected_event",
    "tool_result_event",
    "user_input_request_event",
]
