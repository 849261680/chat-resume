"""用于固定 SDK event 到后端 SSE payload 的公开协议。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pi_agent_core.types import Model

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.stream_events import (  # noqa: E402
    text_delta_event,
    tool_confirmed_event,
    tool_pending_event,
    user_input_request_event,
)
from app.entrypoints.http.resume_agent import format_sse_event  # noqa: E402
from app.runtime.openai_agents_adapter import OpenAIAgentsStreamAdapter  # noqa: E402
from app.types.stream import public_resume_stream_event  # noqa: E402


def _decode_sse_data(rendered: str) -> dict[str, Any]:
    """用于从单个 SSE frame 中解析 JSON data。"""
    data_line = next(line for line in rendered.splitlines() if line.startswith("data: "))
    parsed = json.loads(data_line.removeprefix("data: "))
    assert isinstance(parsed, dict)
    return parsed


def test_sdk_text_delta_becomes_public_sse_text_delta_payload():
    """用于验证 SDK 文本 delta 会穿透成前端可消费的 text_delta。"""
    model = Model(api="responses", provider="openai-agents", id="gpt-test")
    sdk_event = OpenAIAgentsStreamAdapter.text_delta_event_from_sdk_delta(
        model,
        "先改写项目亮点。",
    )

    backend_event = text_delta_event(content=sdk_event.delta)
    public_event = public_resume_stream_event(backend_event)
    rendered = format_sse_event(public_event, event_id="session_1:2")

    assert rendered.startswith("id: session_1:2\n")
    assert _decode_sse_data(rendered) == {
        "event_type": "text_delta",
        "content": "先改写项目亮点。",
        "tool_calls": [],
        "done": False,
    }


def test_tool_pending_payload_contains_confirmation_contract_fields():
    """用于验证工具待确认 SSE payload 保留确认 UI 所需字段。"""
    event = tool_pending_event(
        call_id="call_1",
        tool_id="update_bullet",
        tool_call={"function": {"name": "update_bullet", "arguments": {"text": "new"}}},
        tool_display_name="update_bullet",
        tool_input={"section": "projects", "item_id": "p1"},
        diff_summary="更新项目亮点",
        diff_items=[{"before": "old", "after": "new", "reason": "更量化"}],
        tool_calls=[{"name": "update_bullet"}],
    )

    payload = public_resume_stream_event(event)

    assert payload["event_type"] == "tool_pending"
    assert payload["tool_pending"] is True
    assert payload["call_id"] == "call_1"
    assert payload["tool_id"] == "update_bullet"
    assert payload["tool_input"] == {"section": "projects", "item_id": "p1"}
    assert payload["diff_items"] == [{"before": "old", "after": "new", "reason": "更量化"}]


def test_tool_confirmed_payload_hides_internal_context_but_keeps_decision_fields():
    """用于验证工具确认 SSE payload 不泄漏内部 context。"""
    event = tool_confirmed_event(
        call_id="call_1",
        tool_id="update_bullet",
        tool_display_name="update_bullet",
        tool_calls=[{"name": "update_bullet"}],
        qr_images=[],
        result={"ok": True},
        display_message="已更新",
        diff_summary="更新项目亮点",
        diff_items=[{"before": "old", "after": "new"}],
        context={"resume_content": {"projects": []}},
    )

    payload = public_resume_stream_event(event)

    assert payload["event_type"] == "tool_confirmed"
    assert payload["tool_confirmed"] is True
    assert payload["call_id"] == "call_1"
    assert payload["display_message"] == "已更新"
    assert "context" not in payload


def test_user_input_request_payload_contains_question_contract():
    """用于验证追问用户事件保留结构化问题。"""
    event = user_input_request_event(
        call_id="call_ask",
        tool_id="ask_user",
        tool_display_name="ask_user",
        result={
            "user_input_request": {
                "question": "这个指标来自哪里？",
                "options": ["来自日志", "不确定"],
                "allow_custom": True,
            }
        },
        display_message=None,
        tool_calls=[{"name": "ask_user"}],
    )

    payload = public_resume_stream_event(event)

    assert payload["event_type"] == "user_input_request"
    assert payload["call_id"] == "call_ask"
    assert payload["tool_id"] == "ask_user"
    assert payload["user_input_request"]["question"] == "这个指标来自哪里？"
