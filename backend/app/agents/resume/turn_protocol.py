"""用于收口 Resume Agent 单轮模型流事件的可见协议。"""

from __future__ import annotations

from typing import Any

from pi_agent_core import ToolCall


def visible_tool_call_started(raw_event: Any) -> ToolCall | None:
    """用于从底层流事件中读取可提前展示的工具调用。"""
    if str(getattr(raw_event, "type", "") or "") != "toolcall_start":
        return None
    content_index = getattr(raw_event, "content_index", None)
    if not isinstance(content_index, int):
        return None
    block = _content_block_at(raw_event, content_index)
    if not isinstance(block, ToolCall) or not block.id or not block.name:
        return None
    return block


def visible_text_delta(raw_event: Any) -> str:
    """用于从底层流事件中读取可见文本增量。"""
    if str(getattr(raw_event, "type", "") or "") != "text_delta":
        return ""
    return str(getattr(raw_event, "delta", "") or "")


def should_publish_live_text_delta(raw_event: Any) -> bool:
    """用于判断文本增量是否应实时透传给前端。"""
    partial = getattr(raw_event, "partial", None)
    provider = str(getattr(partial, "provider", "") or "")
    return provider in {"openai-agents", "deepseek"}


def _content_block_at(raw_event: Any, content_index: int) -> Any:
    """用于按 content_index 安全读取 partial content block。"""
    partial = getattr(raw_event, "partial", None)
    content = getattr(partial, "content", None)
    if not isinstance(content, list):
        return None
    if content_index < 0 or content_index >= len(content):
        return None
    return content[content_index]


__all__ = [
    "should_publish_live_text_delta",
    "visible_text_delta",
    "visible_tool_call_started",
]
