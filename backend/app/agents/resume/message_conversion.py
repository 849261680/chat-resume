"""用于定义 Pi runtime 到 LLM 消息的显式转换边界。"""

from __future__ import annotations

from typing import Any

from pi_agent_core.types import AssistantMessage, ContentBlock, Message, TextContent, ToolCall, ToolResultMessage, UserMessage

_LLM_MESSAGE_TYPES = (UserMessage, AssistantMessage, ToolResultMessage)
_LLM_ROLES = {"user", "assistant", "toolResult"}
_TOOL_EVENT_TYPES = {"tool_call", "tool_result", "tool_confirmed", "tool_call_failed", "tool_rejected"}


def convert_resume_messages_to_llm(messages: list[Any]) -> list[Message]:
    """用于过滤不会进入模型上下文的内部消息。"""
    converted: list[Message] = []
    for message in messages:
        if _is_internal_message(message):
            continue
        if isinstance(message, _LLM_MESSAGE_TYPES):
            converted.append(message)
            continue
        if getattr(message, "role", None) in _LLM_ROLES:
            converted.append(message)
    return converted


def resume_chat_history_to_messages(history: list[dict[str, Any]]) -> list[Message]:
    """用于把持久化聊天记录还原为 Pi 风格消息链。"""
    messages: list[Message] = []
    for item in history:
        role = item.get("role")
        content = str(item.get("content") or "")
        if role == "user":
            messages.append(UserMessage(content=[TextContent(text=content)]))
            continue
        if role != "assistant":
            continue
        messages.extend(_assistant_history_messages(content, item.get("stream_events")))
    return messages


def _assistant_history_messages(content: str, raw_events: Any) -> list[Message]:
    """用于把一条 assistant 历史展开为文本与工具结果消息。"""
    events = raw_events if isinstance(raw_events, list) else []
    tool_messages = _tool_messages_from_events(events)
    if not tool_messages:
        return [AssistantMessage(content=[TextContent(text=content)])]
    messages: list[Message] = []
    messages.append(AssistantMessage(content=_assistant_content_from_events(content, events)))
    messages.extend(tool_messages)
    return messages


def _assistant_content_from_events(content: str, events: list[Any]) -> list[ContentBlock]:
    """用于还原 assistant 消息中的文本和 toolCall 块。"""
    blocks: list[ContentBlock] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") == "tool_call":
            call_id = _event_call_id(event)
            tool_name = _event_tool_name(event)
            if call_id and tool_name:
                blocks.append(ToolCall(id=call_id, name=tool_name, arguments=_event_tool_input(event)))
    if content:
        blocks.append(TextContent(text=content))
    return blocks or [TextContent(text="")]


def _tool_messages_from_events(events: list[Any]) -> list[ToolResultMessage]:
    """用于从 streamEvents 中还原工具结果消息。"""
    messages: list[ToolResultMessage] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "")
        if event_type not in _TOOL_EVENT_TYPES or event_type == "tool_call":
            continue
        call_id = _event_call_id(event)
        tool_name = _event_tool_name(event)
        if not call_id or not tool_name:
            continue
        messages.append(ToolResultMessage(
            tool_call_id=call_id,
            tool_name=tool_name,
            content=[TextContent(text=_tool_result_text(event))],
            details=event,
            is_error=event_type in {"tool_call_failed", "tool_rejected"},
        ))
    return messages


def _event_call_id(event: dict[str, Any]) -> str:
    """用于读取工具调用 id。"""
    return str(event.get("callId") or event.get("call_id") or "")


def _event_tool_name(event: dict[str, Any]) -> str:
    """用于读取工具名。"""
    raw_name = event.get("toolId") or event.get("tool_id") or event.get("toolName") or event.get("tool_name")
    tool_name = str(raw_name or "")
    aliases = {
        "更新记忆": "update_memory",
        "读取记忆": "read_memory",
        "优化要点": "update_bullet",
        "新增要点": "add_bullet",
        "删除要点": "remove_bullet",
        "岗位匹配摘要": "generate_job_match_summary",
    }
    return aliases.get(tool_name, tool_name)


def _event_tool_input(event: dict[str, Any]) -> dict[str, Any]:
    """用于读取工具输入参数。"""
    value = event.get("toolInput") or event.get("tool_input")
    return value if isinstance(value, dict) else {}


def _tool_result_text(event: dict[str, Any]) -> str:
    """用于把工具结果事件转成模型可读文本。"""
    message = event.get("displayMessage") or event.get("display_message")
    if isinstance(message, str) and message:
        return message
    if event.get("type") == "tool_confirmed":
        return "工具调用已确认并执行。"
    if event.get("type") == "tool_rejected":
        return "工具调用被用户拒绝。"
    return "工具调用已完成。"


def _is_internal_message(message: Any) -> bool:
    """用于识别只供 UI、审计或恢复使用的内部消息。"""
    if bool(getattr(message, "internal_only", False)):
        return True
    metadata = getattr(message, "metadata", None)
    if isinstance(metadata, dict) and metadata.get("internal_only"):
        return True
    return getattr(message, "role", None) not in _LLM_ROLES


__all__ = ["convert_resume_messages_to_llm", "resume_chat_history_to_messages"]
