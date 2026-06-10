"""用于覆盖简历 Agent 用户信息询问工具。"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.agents.resume.stream_events import (  # noqa: E402
    normalize_resume_stream_payload,
    user_input_request_event,
)
from app.tools.resume.ask_user_tool import ask_user  # noqa: E402
from app.tools.resume.registry import RESUME_TOOLS_SCHEMA, execute_resume_tool  # noqa: E402


def test_ask_user_tool_returns_frontend_request_payload():
    """用于验证 ask_user 返回前端卡片需要的稳定载荷。"""
    result = ask_user(
        {},
        question="你的目标岗位是什么？",
        options=["AI Agent 工程师", "后端工程师", "AI 应用工程师"],
        category="job_application",
        context="用于确定简历优化方向",
    )

    assert result["success"] is True
    assert result["terminate"] is True
    assert result["message"] == "你的目标岗位是什么？"
    request = result["user_input_request"]
    assert request["question"] == "你的目标岗位是什么？"
    assert request["options"] == ["AI Agent 工程师", "后端工程师", "AI 应用工程师"]
    assert request["category"] == "job_application"
    assert request["allow_custom"] is True


def test_ask_user_tool_is_registered_and_auto_executed():
    """用于验证 ask_user 暴露给模型且不需要确认。"""
    tool_names = {tool["function"]["name"] for tool in RESUME_TOOLS_SCHEMA}
    agent = ResumeAgent()

    assert "ask_user" in tool_names
    assert "ask_user" in agent.definition.tool_profiles["resume_edit"]
    assert "ask_user" in agent.definition.auto_execute_tool_names
    assert execute_resume_tool(
        "ask_user",
        resume_content={},
        question="你主要负责哪部分？",
        options=["后端", "前端"],
    )["success"] is True


def test_user_input_request_event_is_public_stream_payload():
    """用于验证用户信息询问事件能通过 SSE 公开传给前端。"""
    event = user_input_request_event(
        call_id="call_1",
        tool_id="ask_user",
        tool_display_name="询问信息",
        result={
            "success": True,
            "user_input_request": {
                "question": "这个项目是否有量化结果？",
                "options": ["有", "没有"],
                "category": "projects",
                "allow_custom": True,
            },
        },
        display_message="这个项目是否有量化结果？",
        tool_calls=[],
    )
    payload = normalize_resume_stream_payload(event)

    assert payload["event_type"] == "user_input_request"
    assert payload["tool_id"] == "ask_user"
    assert payload["user_input_request"]["question"] == "这个项目是否有量化结果？"
