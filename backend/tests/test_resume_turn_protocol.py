"""用于验证 Resume Agent 单轮模型流事件协议。"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from pi_agent_core import AssistantMessage, TextContent, ToolCall

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.turn_protocol import (  # noqa: E402
    should_publish_live_text_delta,
    visible_text_delta,
    visible_tool_call_started,
)


def test_visible_tool_call_started_reads_valid_toolcall_start() -> None:
    """用于验证可见工具调用从底层 start 事件中读取。"""
    tool_call = ToolCall(id="call_1", name="update_bullet", arguments={})
    event = SimpleNamespace(
        type="toolcall_start",
        content_index=0,
        partial=AssistantMessage(
            api="responses",
            provider="openai-agents",
            model="gpt-test",
            content=[tool_call],
        ),
    )

    assert visible_tool_call_started(event) == tool_call


def test_visible_tool_call_started_ignores_invalid_content_index() -> None:
    """用于验证无效 content index 不会产生幽灵工具卡片。"""
    event = SimpleNamespace(
        type="toolcall_start",
        content_index=1,
        partial=AssistantMessage(
            api="responses",
            provider="openai-agents",
            model="gpt-test",
            content=[TextContent(text="计划")],
        ),
    )

    assert visible_tool_call_started(event) is None


def test_visible_text_delta_and_live_publish_provider_contract() -> None:
    """用于验证文本增量和可实时透传 provider 判断保持稳定。"""
    live_event = SimpleNamespace(
        type="text_delta",
        delta="先优化这一条",
        partial=SimpleNamespace(provider="deepseek"),
    )
    buffered_event = SimpleNamespace(
        type="text_delta",
        delta="稍后 flush",
        partial=SimpleNamespace(provider="openrouter"),
    )

    assert visible_text_delta(live_event) == "先优化这一条"
    assert should_publish_live_text_delta(live_event) is True
    assert visible_text_delta(buffered_event) == "稍后 flush"
    assert should_publish_live_text_delta(buffered_event) is False
