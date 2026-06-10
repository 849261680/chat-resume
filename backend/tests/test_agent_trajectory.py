"""Agent 轨迹测试：mock LLM → 验证工具选择和执行路径。

核心思路：不调用真实 LLM，而是注入预设的 LLM 响应（含 tool_call），
验证 Agent 是否正确选择了工具、执行了工具、处理了结果。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pi_agent_core import (
    AssistantMessage,
    StreamDoneEvent,
    StreamResult,
    StreamStartEvent,
    StreamTextDeltaEvent,
    StreamTextEndEvent,
    StreamTextStartEvent,
    StreamToolCallEndEvent,
    StreamToolCallStartEvent,
    TextContent,
    ToolCall,
)

from app.agents.resume.agent import ResumeAgent
from app.agents.resume.agent_loop import ResumeAgentLoop
from app.agents.resume.run_lifecycle import ResumeRunLifecycle
from app.agents.resume.turn_context import ResumeTurnContextBuilder
from app.agents.resume.tool_execution import ResumeToolExecutionStage


# ── 测试用简历 ──────────────────────────────────────────────

SAMPLE_RESUME: dict[str, Any] = {
    "personal_info": {"name": "张三", "email": "z@s.com"},
    "summary": {"text": "3 年前端工程师"},
    "work_experience": [
        {
            "id": "work_1",
            "company": "某公司",
            "title": "前端工程师",
            "highlights": [
                {"id": "hl_1", "text": "负责前端开发"},
            ],
        }
    ],
    "projects": [
        {
            "id": "proj_1",
            "name": "增长平台",
            "highlights": [
                {"id": "proj_hl_1", "text": "搭建数据分析看板"},
            ],
        }
    ],
    "skills": [{"id": "sk_1", "category": "前端", "items": ["React", "TypeScript"]}],
}


# ── Mock LLM 流构造工具 ─────────────────────────────────────


class FakeStream:
    """用于给 ResumeAgentLoop 提供确定性模型事件。"""

    def __init__(self, messages: list[AssistantMessage]):
        """用于保存模型消息序列。"""
        self.messages = list(messages)
        self.contexts: list[Any] = []
        self.calls = 0
        self.tool_names_seen: list[list[str]] = []

    async def __call__(self, model, context, options) -> StreamResult:
        """用于返回 pi-agent-core stream result。"""
        self.contexts.append(context)
        self.tool_names_seen.append(
            [t.name for t in context.tools] if context.tools else []
        )
        message = self.messages[self.calls]
        self.calls += 1
        events = self._events_for(message)

        async def events_iter():
            for event in events:
                yield event

        async def result():
            return message

        return {"events": events_iter(), "result": result}

    @staticmethod
    def _events_for(message: AssistantMessage) -> list[Any]:
        """用于把完整 assistant message 转换成测试流事件。"""
        events: list[Any] = [StreamStartEvent(partial=message)]
        for index, block in enumerate(message.content):
            if isinstance(block, TextContent):
                events.extend([
                    StreamTextStartEvent(content_index=index, partial=message),
                    StreamTextDeltaEvent(
                        content_index=index, delta=block.text, partial=message,
                    ),
                    StreamTextEndEvent(
                        content_index=index, content=block.text, partial=message,
                    ),
                ])
            if isinstance(block, ToolCall):
                events.extend([
                    StreamToolCallStartEvent(content_index=index, partial=message),
                    StreamToolCallEndEvent(
                        content_index=index, tool_call=block, partial=message,
                    ),
                ])
        events.append(StreamDoneEvent(reason=message.stop_reason, message=message))
        return events


def _text_msg(text: str) -> AssistantMessage:
    """构造纯文本 assistant message。"""
    return AssistantMessage(content=[TextContent(text=text)], stop_reason="stop")


def _tool_msg(tool_name: str, arguments: dict[str, Any]) -> AssistantMessage:
    """构造包含单个 tool_call 的 assistant message。"""
    tc = ToolCall(id="call_test", name=tool_name, arguments=arguments)
    return AssistantMessage(content=[TextContent(text=""), tc], stop_reason="toolUse")


# ── 轨迹运行辅助 ─────────────────────────────────────────────


async def _run_trajectory(
    user_message: str,
    *,
    resume_content: dict[str, Any] | None = None,
    llm_messages: list[AssistantMessage],
) -> dict[str, Any]:
    """运行一次 Agent 轨迹并收集工具调用记录。"""
    fake_stream = FakeStream(llm_messages)
    agent = ResumeAgent()
    stage = ResumeToolExecutionStage()
    loop = ResumeAgentLoop(
        stream_fn=fake_stream,
        tool_stage=stage,
    )
    builder = ResumeTurnContextBuilder(tool_stage=stage)
    state = ResumeRunLifecycle.new_stream_state()
    executed_tools: list[dict[str, Any]] = []

    pi_context, prompts, config = builder.build_loop_inputs(
        agent=agent.definition,
        user_message=user_message,
        context={"resume_content": resume_content or SAMPLE_RESUME},
        conversation_history=[],
        run_id="run_traj_test",
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        executed_tools=executed_tools,
        stream_state=state,
    )

    await loop.run(
        agent=agent.definition,
        run_id="run_traj_test",
        pi_context=pi_context,
        prompts=prompts,
        config=config,
        context={"resume_content": resume_content or SAMPLE_RESUME},
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        state=state,
        executed_tools=executed_tools,
        model_name="test-model",
    )

    return {
        "content": "".join(state.get("response_parts", [])),
        "tool_calls": executed_tools,
        "llm_call_count": fake_stream.calls,
        "tool_names_seen": fake_stream.tool_names_seen,
    }


# ── P0 轨迹测试 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trajectory_optimize_bullet_calls_update_bullet():
    """用户说'优化这条亮点' → Agent 应调用 update_bullet。"""
    result = await _run_trajectory(
        "帮我优化工作经历的第一条亮点",
        llm_messages=[
            _tool_msg("update_bullet", {
                "section": "work_experience",
                "item_id": "work_1",
                "bullet_id": "hl_1",
                "text": "主导前端架构重构，首屏加载提速 35%",
                "reason": "补充量化结果",
            }),
            _text_msg("已完成优化，补充了量化结果。"),
        ],
    )

    assert len(result["tool_calls"]) == 1
    tc = result["tool_calls"][0]
    assert tc["name"] == "优化要点"
    assert tc["success"] is True
    assert result["llm_call_count"] == 2


@pytest.mark.asyncio
async def test_trajectory_add_new_bullet_calls_add_bullet():
    """用户说'加一条亮点' → Agent 应调用 add_bullet。"""
    result = await _run_trajectory(
        "在工作经历中加一条关于性能优化的亮点",
        llm_messages=[
            _tool_msg("add_bullet", {
                "section": "work_experience",
                "item_id": "work_1",
                "text": "搭建前端性能监控体系，覆盖 30+ 关键链路",
                "reason": "用户要求新增",
            }),
            _text_msg("已添加。"),
        ],
    )

    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["name"] == "新增要点"
    assert result["tool_calls"][0]["success"] is True


@pytest.mark.asyncio
async def test_trajectory_delete_bullet_calls_remove_bullet():
    """用户说'删除这条亮点' → Agent 应调用 remove_bullet。"""
    result = await _run_trajectory(
        "删掉工作经历的第一条亮点",
        llm_messages=[
            _tool_msg("remove_bullet", {
                "section": "work_experience",
                "item_id": "work_1",
                "bullet_id": "hl_1",
                "reason": "用户要求删除",
            }),
            _text_msg("已删除。"),
        ],
    )

    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["name"] == "删除要点"


@pytest.mark.asyncio
async def test_trajectory_consultation_returns_text_without_tools():
    """用户只问问题 → Agent 应直接回复文字，不调用工具。"""
    result = await _run_trajectory(
        "简历里要不要写项目链接？",
        llm_messages=[
            _text_msg("建议加上项目链接，尤其是开源项目。"),
        ],
    )

    assert len(result["tool_calls"]) == 0
    assert len(result["content"]) > 0
    assert result["llm_call_count"] == 1


@pytest.mark.asyncio
async def test_trajectory_rejects_unknown_tool():
    """LLM 调用不存在的工具 → Agent 应返回错误而非崩溃。"""
    result = await _run_trajectory(
        "优化简历",
        llm_messages=[
            _tool_msg("nonexistent_tool", {"some_arg": "value"}),
            _text_msg("抱歉，发生了错误。"),
        ],
    )

    assert len(result["tool_calls"]) == 1
    tc = result["tool_calls"][0]
    assert tc["success"] is False


@pytest.mark.asyncio
async def test_trajectory_update_summary_for_summary_edit():
    """用户说'改个人总结' → Agent 应调用 update_summary。"""
    result = await _run_trajectory(
        "帮我改一下个人总结",
        llm_messages=[
            _tool_msg("update_summary", {
                "text": "5 年前端工程师，擅长 React 生态与性能优化",
                "reason": "用户要求修改总结",
            }),
            _text_msg("已更新个人总结。"),
        ],
    )

    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["name"] == "优化总结"
    assert result["tool_calls"][0]["success"] is True


@pytest.mark.asyncio
async def test_trajectory_multi_turn_react_loop():
    """Agent 执行两轮工具调用后收尾 → 验证多 turn ReAct 路径。"""
    result = await _run_trajectory(
        "优化工作经历的亮点，然后更新个人总结",
        llm_messages=[
            _tool_msg("update_bullet", {
                "section": "work_experience",
                "item_id": "work_1",
                "bullet_id": "hl_1",
                "text": "主导前端架构重构，接口响应提速 40%",
                "reason": "补充量化数据",
            }),
            _tool_msg("update_summary", {
                "text": "资深前端工程师，擅长性能优化",
                "reason": "与优化后的亮点对齐",
            }),
            _text_msg("已完成两处修改。"),
        ],
    )

    assert len(result["tool_calls"]) == 2
    assert result["tool_calls"][0]["name"] == "优化要点"
    assert result["tool_calls"][1]["name"] == "优化总结"
    assert result["llm_call_count"] == 3


@pytest.mark.asyncio
async def test_trajectory_tools_exposed_match_profile():
    """LLM 收到的工具列表应匹配 resume_edit profile。"""
    result = await _run_trajectory(
        "分析一下简历",
        llm_messages=[_text_msg("好的。")],
    )

    assert len(result["tool_names_seen"]) >= 1
    tool_names = result["tool_names_seen"][0]
    assert "update_bullet" in tool_names
    assert "add_bullet" in tool_names
    assert "remove_bullet" in tool_names
    assert "update_summary" in tool_names
    assert "score_resume" in tool_names
