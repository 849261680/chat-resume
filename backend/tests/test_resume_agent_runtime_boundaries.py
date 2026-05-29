"""用于覆盖 Resume Agent runtime 边界和工具 profile 行为。"""

from __future__ import annotations

import asyncio
import inspect
import logging
import sys
from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pi_agent_core import (
    AgentContext,
    AssistantMessage,
    SimpleStreamOptions,
    StreamDoneEvent,
    StreamStartEvent,
    StreamTextDeltaEvent,
    StreamTextEndEvent,
    StreamTextStartEvent,
    StreamToolCallEndEvent,
    StreamToolCallStartEvent,
    TextContent,
    ToolCall,
    ToolExecutionStartEvent,
    ToolResultMessage,
    UserMessage,
)
from pi_agent_core.types import Message, Model, StreamResult

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.agents.resume.agent_loop import ResumeAgentLoop  # noqa: E402
from app.agents.resume.run_lifecycle import ResumeRunLifecycle  # noqa: E402
from app.agents.resume.runner import ResumeAgentRunner  # noqa: E402
from app.agents.resume.stream_adapter import ResumeReActStreamAdapter  # noqa: E402
from app.agents.resume.tool_execution import ResumeToolExecutionStage  # noqa: E402
from app.agents.resume.turn_context import ResumeTurnContextBuilder  # noqa: E402
from app.infra.config import settings  # noqa: E402
from app.agents.resume.message_conversion import convert_resume_messages_to_llm  # noqa: E402
from app.runtime.openrouter_adapter import build_openrouter_config  # noqa: E402
from app.runtime.contracts import AgentDefinition  # noqa: E402
from app.services.agent.resume_agent_stream_service import (  # noqa: E402
    ResumeAgentStreamService,
)
from app.agents.resume.session import (  # noqa: E402
    ResumeAgentSession,
    maybe_compact_resume_context,
)
from app.runtime.tool_confirmation import ToolConfirmationPolicy  # noqa: E402

RESUME_EDIT_TOOL_NAMES = {
    "update_summary",
    "update_profile",
    "upsert_job_application",
    "update_item_fields",
    "update_skills",
    "add_resume_item",
    "remove_resume_item",
    "update_overview",
    "update_bullet",
    "add_bullet",
    "remove_bullet",
    "generate_job_match_summary",
    "list_job_posts",
    "read_job_post",
    "read_memory",
    "update_memory",
}


def test_agent_definition_default_tool_profile_is_not_resume_specific():
    """用于验证通用 runtime contract 不携带 Resume Agent 业务默认。"""
    default_profile = next(
        field.default
        for field in fields(AgentDefinition)
        if field.name == "default_tool_profile"
    )

    assert default_profile == ""


def _new_test_stream_state() -> dict[str, Any]:
    """用于创建测试里的 Resume Agent stream state。"""
    return ResumeRunLifecycle.new_stream_state()


def _build_test_turn_inputs(
    agent: ResumeAgent,
    *,
    user_message: str,
    context: dict[str, Any],
    state: dict[str, Any],
    conversation_history: list[dict[str, str]] | None = None,
) -> tuple[AgentContext, list[Message], Any]:
    """用于通过 turn context builder 生成测试 loop 输入。"""
    stage = ResumeToolExecutionStage()
    builder = ResumeTurnContextBuilder(tool_stage=stage)
    return builder.build_loop_inputs(
        agent=agent.definition,
        user_message=user_message,
        context=context,
        conversation_history=conversation_history or [],
        run_id="run_test",
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        executed_tools=[],
        stream_state=state,
    )


class FakeLoopStream:
    """用于给独立 ResumeAgentLoop 提供确定性模型事件。"""

    def __init__(self, messages: list[AssistantMessage]):
        """用于保存模型消息序列。"""
        self.messages = list(messages)
        self.contexts: list[AgentContext] = []
        self.options: list[SimpleStreamOptions] = []
        self.calls = 0

    async def __call__(
        self,
        model: Model,
        context: AgentContext,
        options: SimpleStreamOptions,
    ) -> StreamResult:
        """用于返回 pi-agent-core stream result。"""
        del model
        self.contexts.append(context)
        self.options.append(options)
        message = self.messages[self.calls]
        self.calls += 1
        events = self._events_for(message)

        async def events_iter():
            """用于按顺序返回预设流事件。"""
            for event in events:
                yield event

        async def result():
            """用于返回当前完整 assistant message。"""
            return message

        return {"events": events_iter(), "result": result}

    @staticmethod
    def _events_for(message: AssistantMessage) -> list[Any]:
        """用于把完整 assistant message 转换成测试流事件。"""
        events: list[Any] = [StreamStartEvent(partial=message)]
        for index, block in enumerate(message.content):
            if isinstance(block, TextContent):
                events.extend(
                    [
                        StreamTextStartEvent(content_index=index, partial=message),
                        StreamTextDeltaEvent(
                            content_index=index,
                            delta=block.text,
                            partial=message,
                        ),
                        StreamTextEndEvent(
                            content_index=index,
                            content=block.text,
                            partial=message,
                        ),
                    ]
                )
            if isinstance(block, ToolCall):
                events.extend(
                    [
                        StreamToolCallStartEvent(
                            content_index=index,
                            partial=message,
                        ),
                        StreamToolCallEndEvent(
                            content_index=index,
                            tool_call=block,
                            partial=message,
                        ),
                    ]
                )
        events.append(StreamDoneEvent(reason=message.stop_reason, message=message))
        return events


def fake_loop_text(text: str) -> AssistantMessage:
    """用于构造测试文本 assistant message。"""
    return AssistantMessage(content=[TextContent(text=text)], stop_reason="stop")


def fake_loop_tool_call(
    *,
    name: str,
    args: dict[str, Any],
    call_id: str,
) -> AssistantMessage:
    """用于构造测试工具调用 assistant message。"""
    return AssistantMessage(
        content=[ToolCall(id=call_id, name=name, arguments=args)],
        stop_reason="toolUse",
    )


def _build_runtime_inputs(agent: ResumeAgent, user_message: str) -> tuple[Any, dict[str, Any]]:
    """用于生成最小 turn 输入并返回 pi_context 和 state。"""
    state = _new_test_stream_state()
    context = {
        "resume_content": {"projects": [{"id": "proj_1", "name": "Chat Resume"}]},
    }
    pi_context, _prompts, _config = _build_test_turn_inputs(
        agent,
        user_message=user_message,
        context=context,
        state=state,
    )
    return pi_context, state


def test_plain_message_exposes_resume_tools_for_model_choice():
    """用于验证普通消息也由模型自行决定是否调用工具。"""
    agent = ResumeAgent()

    pi_context, state = _build_runtime_inputs(agent, "这份简历有哪些问题？")

    assert state["tool_profile"] == "resume_edit"
    assert {tool.name for tool in pi_context.tools} == RESUME_EDIT_TOOL_NAMES


def test_system_prompt_does_not_mirror_active_tools():
    """用于验证系统提示词不再镜像实际暴露给模型的工具。"""
    agent = ResumeAgent()

    pi_context, state = _build_runtime_inputs(agent, "优化项目经历")

    assert "## 可用工具" not in pi_context.system_prompt
    assert "update_bullet" not in pi_context.system_prompt
    assert "generate_job_match_summary" not in pi_context.system_prompt
    assert set(state["tool_names"]) == RESUME_EDIT_TOOL_NAMES


def test_system_prompt_template_omits_tool_summary_variables():
    """用于验证 system.md 不保留工具摘要占位。"""
    prompt_path = BACKEND_DIR / "app" / "prompts" / "resume_agent" / "system.md"
    raw_prompt = prompt_path.read_text(encoding="utf-8")

    assert "edit_tools_available" not in raw_prompt
    assert "job_match_tool_available" not in raw_prompt
    assert "default(true)" not in raw_prompt
    assert "{{" not in raw_prompt
    assert "${available_tools}" not in raw_prompt
    assert "${tool_usage_rules}" not in raw_prompt
    assert "${tool_protocol}" not in raw_prompt
    assert "首轮" not in raw_prompt


def test_system_prompt_tool_list_matches_requested_profile():
    """用于验证工具摘要随当前工具 profile 更新。"""
    agent = ResumeAgent()
    state = _new_test_stream_state()
    context = {
        "resume_content": {"projects": [{"id": "proj_1", "name": "Chat Resume"}]},
        "tool_profile": "read_only",
    }

    pi_context, _prompts, _config = _build_test_turn_inputs(
        agent,
        user_message="只分析，不要修改",
        context=context,
        state=state,
    )

    assert [tool.name for tool in pi_context.tools] == [
        "generate_job_match_summary",
        "list_job_posts",
        "read_job_post",
        "read_memory",
    ]
    assert "generate_job_match_summary" not in pi_context.system_prompt
    assert "update_bullet" not in pi_context.system_prompt


def test_turn_context_keeps_tools_available_for_hidden_sections():
    """用于验证隐藏模块不会裁剪 Agent 可见工具 schema。"""
    agent = ResumeAgent()
    state = _new_test_stream_state()
    context = {
        "resume_content": {
            "projects": [{"id": "proj_1", "name": "Chat Resume"}],
            "skills": [{"id": "skill_1", "category": "AI", "items": ["Agent"]}],
        },
        "allowed_sections": {"projects"},
    }

    pi_context, _prompts, _config = _build_test_turn_inputs(
        agent,
        user_message="补充技能专长",
        context=context,
        state=state,
    )

    tools_by_name = {tool.name: tool for tool in pi_context.tools}
    assert "update_skills" in tools_by_name
    assert "add_resume_item" in tools_by_name
    assert "skills" in tools_by_name["add_resume_item"].parameters.properties[
        "section"
    ]["enum"]
    assert "update_skills" in state["tool_names"]


def test_resume_stream_service_loads_full_resume_content_for_agent_tools():
    """用于验证隐藏模块不会裁掉 Agent 可读写的简历内容。"""
    content = {
        "personal_info": {"name": "张三"},
        "summary": {"text": "AI Agent 开发工程师"},
        "projects": [{"id": "proj_1", "name": "Chat Resume"}],
        "skills": [{"id": "skill_1", "category": "AI", "items": ["Agent"]}],
    }
    resume = type("ResumeStub", (), {"content": content})()

    loaded = ResumeAgentStreamService._load_resume_content(resume)

    assert loaded == content
    assert loaded["skills"] == [{"id": "skill_1", "category": "AI", "items": ["Agent"]}]


def test_resume_turn_context_builder_prepares_profiled_tools_independently():
    """用于验证 turn context 构建可以脱离 ResumeAgentRuntime 单独测试。"""
    agent = ResumeAgent()
    stage = ResumeToolExecutionStage()
    builder = ResumeTurnContextBuilder(tool_stage=stage)
    state = _new_test_stream_state()
    context = {
        "resume_content": {"projects": [{"id": "proj_1", "name": "Chat Resume"}]},
        "tool_profile": "read_only",
    }

    pi_context, prompts, config = builder.build_loop_inputs(
        agent=agent.definition,
        user_message="只分析，不要修改",
        context=context,
        conversation_history=[{"role": "assistant", "content": "历史回答"}],
        run_id="turn_builder_test",
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        executed_tools=[],
        stream_state=state,
    )

    assert [tool.name for tool in pi_context.tools] == [
        "generate_job_match_summary",
        "list_job_posts",
        "read_job_post",
        "read_memory",
    ]
    assert prompts[0].role == "user"
    assert context["tool_profile"] == "read_only"
    assert context["available_tool_names"] == [
        "generate_job_match_summary",
        "list_job_posts",
        "read_job_post",
        "read_memory",
    ]
    assert state["tool_profile"] == "read_only"
    assert state["tool_names"] == [
        "generate_job_match_summary",
        "list_job_posts",
        "read_job_post",
        "read_memory",
    ]
    assert state["prompt_chars"] == len(pi_context.system_prompt)
    assert config.convert_to_llm is not None


def test_system_prompt_resume_json_hides_technologies_compat_fields():
    """用于验证提示词中的简历 JSON 不暴露兼容用 technologies 字段。"""
    agent = ResumeAgent()
    state = _new_test_stream_state()
    context = {
        "resume_content": {
            "work_experience": [
                {
                    "id": "work_1",
                    "company": "某科技公司",
                    "technologies": ["Python"],
                }
            ],
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Deep Research Agent",
                    "technologies": ["LangChain"],
                }
            ],
        }
    }

    pi_context, _prompts, _config = _build_test_turn_inputs(
        agent,
        user_message="补充 Python 技术栈",
        context=context,
        state=state,
    )

    assert "technologies" not in pi_context.system_prompt
    assert "Deep Research Agent" in pi_context.system_prompt


def test_job_match_message_still_exposes_resume_tools_for_model_choice():
    """用于验证岗位匹配消息不再由后端收窄工具集。"""
    agent = ResumeAgent()

    pi_context, state = _build_runtime_inputs(agent, "这个 JD 的岗位匹配度怎么样？")

    assert state["tool_profile"] == "resume_edit"
    assert {tool.name for tool in pi_context.tools} == RESUME_EDIT_TOOL_NAMES


def test_llm_request_event_records_profile_counts_and_prompt_size():
    """用于验证 LLM 请求日志字段包含 profile、工具数量和 prompt 信息。"""
    agent = ResumeAgent()
    pi_context, state = _build_runtime_inputs(agent, "优化项目经历")

    event = ResumeAgentLoop.llm_request_event(
        agent.definition,
        pi_context,
        [],
        state,
        "test-model",
    )

    assert event["tool_profile"] == "resume_edit"
    assert event["tool_count"] == len(RESUME_EDIT_TOOL_NAMES)
    assert event["message_count"] == 1
    assert event["prompt_chars"] > 0


def test_llm_response_event_records_first_token_usage_and_confirmation_wait():
    """用于验证 LLM 响应日志字段包含首 token、usage 和确认等待耗时。"""
    agent = ResumeAgent()
    lifecycle = ResumeRunLifecycle(model_name_provider=lambda: "test-model")
    state = lifecycle.new_stream_state()
    state["first_token_latency_ms"] = 12.5
    state["confirmation_wait_ms"] = 30.0
    state["usage"] = {"input": 10, "output": 5, "total_tokens": 15}

    event = lifecycle.llm_response_event(agent.definition, state)

    assert event["first_token_latency_ms"] == 12.5
    assert event["confirmation_wait_ms"] == 30.0
    assert event["usage"]["total_tokens"] == 15


def test_resume_run_lifecycle_builds_events_independently():
    """用于验证 run lifecycle 可以脱离 ResumeAgentRuntime 单独生成事件。"""
    agent = ResumeAgent()
    lifecycle = ResumeRunLifecycle(model_name_provider=lambda: "test-model")
    state = lifecycle.new_stream_state()
    state["response_parts"] = ["已完成", "优化。"]
    state["tool_call_count"] = 1
    state["first_token_latency_ms"] = 8.0
    state["usage"] = {"total_tokens": 12}
    state["confirmation_wait_ms"] = 20.0

    prompt_event = lifecycle.prompt_rendered_event(
        agent.definition,
        "system prompt",
        "x" * 2000,
    )
    response_event = lifecycle.llm_response_event(agent.definition, state)

    assert prompt_event["event_type"] == "prompt_rendered"
    assert prompt_event["agent_name"] == agent.definition.prompt_spec.name
    assert len(prompt_event["user_message_preview"]) == 1500
    assert response_event["event_type"] == "llm_response"
    assert response_event["model"] == "test-model"
    assert response_event["response_content"] == "已完成优化。"
    assert response_event["tool_call_count"] == 1
    assert response_event["first_token_latency_ms"] == 8.0
    assert response_event["usage"]["total_tokens"] == 12
    assert response_event["confirmation_wait_ms"] == 20.0


@pytest.mark.asyncio
async def test_resume_agent_runner_runs_sync_independently():
    """用于验证 Resume Agent runner 可脱离 ResumeAgentRuntime 编排一次 run。"""
    agent = ResumeAgent()
    stage = ResumeToolExecutionStage()
    loop = ResumeAgentLoop(
        stream_fn=FakeLoopStream([fake_loop_text("这是简历建议。")]),
        tool_stage=stage,
    )
    runner = ResumeAgentRunner(
        agent_loop=loop,
        turn_context_builder=ResumeTurnContextBuilder(tool_stage=stage),
        lifecycle=ResumeRunLifecycle(model_name_provider=lambda: "test-model"),
        model_name_provider=lambda: "test-model",
    )
    events: list[dict[str, Any]] = []

    def record_event(event: Mapping[str, Any]) -> None:
        """用于保存 runtime callback 事件以便断言。"""
        events.append(dict(event))

    result = await runner.run(
        agent=agent.definition,
        user_message="分析这份简历",
        context={"resume_content": {"projects": [{"id": "proj_1", "name": "Chat Resume"}]}},
        conversation_history=[],
        event_callback=record_event,
    )

    assert result["content"] == "这是简历建议。"
    assert result["tool_calls"] == []
    assert events[0]["event_type"] == "prompt_rendered"
    assert any(event.get("event_type") == "llm_request" for event in events)
    assert any(event.get("content") == "这是简历建议。" for event in events)
    assert events[-1]["event_type"] == "llm_response"
    assert events[-1]["model"] == "test-model"


@pytest.mark.asyncio
async def test_resume_react_stream_adapter_keeps_one_tool_call_per_turn():
    """用于验证 ReAct stream adapter 可脱离 ResumeAgentRuntime 裁剪工具调用。"""
    message = AssistantMessage(
        content=[
            ToolCall(id="call_1", name="update_bullet", arguments={"text": "A"}),
            ToolCall(id="call_2", name="update_summary", arguments={"summary": "B"}),
        ],
        stop_reason="toolUse",
    )
    stream = FakeLoopStream([message])
    adapter = ResumeReActStreamAdapter(stream)
    response = await adapter(None, AgentContext(system_prompt="", messages=[], tools=[]), None)

    result = response["result"]()
    if inspect.isawaitable(result):
        result = await result

    assert isinstance(result, AssistantMessage)
    assert [block.id for block in result.content if isinstance(block, ToolCall)] == ["call_1"]


def test_allowed_tool_call_uses_normal_detection_trace(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """用于验证默认工具集下模型工具调用不再被判为 unexpected。"""
    agent = ResumeAgent()
    loop = ResumeAgentLoop(stream_fn=FakeLoopStream([]), tool_stage=ResumeToolExecutionStage())
    state = _new_test_stream_state()
    state["tool_profile"] = "resume_edit"
    state["tool_names"] = ["update_bullet"]
    event = ToolExecutionStartEvent(
        tool_call_id="call_1",
        tool_name="update_bullet",
        args={},
    )
    monkeypatch.setattr(settings, "AGENT_TRACE_LOG_ENABLED", True)

    with caplog.at_level("INFO", logger="app.agents.resume.runtime"):
        loop.trace_tool_call_detected(agent.definition, "run_test", event, state)
        loop.trace_tool_call_detected(agent.definition, "run_test", event, state)

    messages = [record.getMessage() for record in caplog.records]
    assert "agent.trace.reasoning.unexpected_tool_call" not in messages
    assert messages.count("agent.trace.reasoning.tool_call_detected") == 2


def test_failed_tool_preview_logs_warning(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """用于验证工具预览失败在日志里更醒目。"""
    agent = ResumeAgent()
    stage = ResumeToolExecutionStage()
    monkeypatch.setattr(settings, "AGENT_TRACE_LOG_ENABLED", True)

    with caplog.at_level("INFO", logger="app.agents.resume.runtime"):
        stage.trace_tool_preview(
            agent.definition,
            "run_test",
            "call_preview",
            "update_bullet",
            {
                "tool_name": "优化要点",
                "display_message": "update_bullet 缺少必填参数: section",
                "result": {"success": False, "error": "missing section"},
            },
        )

    preview_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "agent.trace.tool.preview_failed"
    )
    assert preview_record.levelno == logging.WARNING
    assert getattr(preview_record, "tool_name") == "update_bullet"
    assert getattr(preview_record, "result_success") is False


def test_tool_requested_trace_summarizes_large_text_input(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """用于验证工具请求日志只记录可读摘要而不是完整文本。"""
    agent = ResumeAgent()
    stage = ResumeToolExecutionStage()
    long_text = "基于 LlamaIndex 构建文档索引与向量存储层，支撑 RAG 检索。" * 8
    monkeypatch.setattr(settings, "AGENT_TRACE_LOG_ENABLED", True)

    with caplog.at_level("INFO", logger="app.agents.resume.runtime"):
        stage.trace_tool_requested(
            agent.definition,
            "run_test",
            "call_requested",
            "add_bullet",
            {
                "item_id": "proj_1",
                "reason": "补充 JD 要求的 LlamaIndex 技术栈，强化 RAG 向量检索能力",
                "section": "projects",
                "text": long_text,
            },
            True,
        )

    requested_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "agent.trace.tool.requested"
    )
    tool_input = getattr(requested_record, "tool_input")
    assert tool_input["item_id"] == "proj_1"
    assert tool_input["section"] == "projects"
    assert tool_input["text_chars"] == len(long_text)
    assert tool_input["text_preview"].startswith("基于 LlamaIndex")
    assert "text" not in tool_input


def test_convert_resume_messages_filters_internal_only_messages():
    """用于验证 convert_to_llm 不会把 UI 或内部事件送进模型。"""
    user = UserMessage(content=[TextContent(text="用户问题")])
    assistant = AssistantMessage(content=[TextContent(text="助手回答")])
    tool_result = ToolResultMessage(
        tool_call_id="call_1",
        tool_name="read_resume",
        content=[TextContent(text="结果")],
    )
    internal = SimpleNamespace(role="ui", content=[TextContent(text="只给 UI")])

    converted = convert_resume_messages_to_llm([user, assistant, tool_result, internal])

    assert converted == [user, assistant, tool_result]


@pytest.mark.asyncio
async def test_confirmation_policy_returns_feedback_without_terminating_turn():
    """用于验证确认 hook 将确认结果交还给模型继续 ReAct。"""
    policy = ToolConfirmationPolicy()
    queue: asyncio.Queue[bool] = asyncio.Queue()

    decision = policy.before_tool_call(
        confirmation_queue=queue,
        tool_name="update_bullet",
        auto_execute_tool_names=set(),
    )
    queue.put_nowait(False)
    confirmed = await policy.wait_for_decision(queue)
    result = policy.after_tool_decision(confirmed=confirmed)

    assert decision.requires_confirmation is True
    assert result.confirmed is False
    assert result.terminate_turn is False


@pytest.mark.asyncio
async def test_resume_tool_execution_stage_runs_confirmed_tool_independently():
    """用于验证工具执行确认阶段可以脱离 ResumeAgentRuntime 单独测试。"""
    agent = ResumeAgent()
    stage = ResumeToolExecutionStage()
    resume = {
        "work_experience": [
            {
                "id": "work_1",
                "company": "某科技公司",
                "position": "Python 开发工程师",
                "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
            }
        ]
    }
    confirmation_queue: asyncio.Queue[bool] = asyncio.Queue()
    confirmation_queue.put_nowait(True)
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    stream_state = {
        "visible_tool_call_ids": set(),
        "confirmed_diff_items": [],
        "confirmation_wait_ms": 0.0,
        "chunk_index": 0,
        "response_parts": [],
    }
    executed_tools: list[dict[str, Any]] = []

    result = await stage.execute_tool_result(
        agent=agent.definition,
        run_id="run_test",
        call_id="call_stage_1",
        tool_name="update_bullet",
        tool_input={
            "section": "work_experience",
            "item_id": "work_1",
            "bullet_id": "hl_1",
            "text": "维护多个后台服务，支撑日活 10 万用户",
            "reason": "补充业务规模",
        },
        context={"resume_content": resume, "allowed_sections": {"work_experience"}},
        confirmation_queue=confirmation_queue,
        event_queue=event_queue,
        event_callback=None,
        executed_tools=executed_tools,
        stream_state=stream_state,
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    assert "支撑日活 10 万用户" in str(result.details)
    assert resume["work_experience"][0]["highlights"][0]["text"] == (
        "维护多个后台服务，支撑日活 10 万用户"
    )
    assert any(event.get("tool_pending") for event in events)
    assert any(event.get("tool_confirmed") for event in events)
    assert executed_tools[0]["success"] is True
    assert stream_state["confirmed_diff_items"]


@pytest.mark.asyncio
async def test_read_memory_auto_executes_without_confirmation(tmp_path):
    """用于验证读取记忆不需要人类确认即可直接执行。"""
    agent = ResumeAgent()
    agent.tool_executor.execute(
        tool_name="update_memory",
        tool_input={
            "operation": "append",
            "scope": "user",
            "kind": "preference",
            "content": "优化简历时保持简洁，不写冗长 bullet。",
            "reason": "用户明确表达长期偏好",
        },
        context={"resume_content": {}, "user_id": 42, "memory_dir": str(tmp_path)},
    )
    stage = ResumeToolExecutionStage()
    confirmation_queue: asyncio.Queue[bool] = asyncio.Queue()
    confirmation_queue.put_nowait(False)
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    stream_state = {
        "visible_tool_call_ids": set(),
        "confirmed_diff_items": [],
        "confirmation_wait_ms": 0.0,
        "chunk_index": 0,
        "response_parts": [],
    }
    executed_tools: list[dict[str, Any]] = []

    result = await stage.execute_tool_result(
        agent=agent.definition,
        run_id="run_memory_read_auto",
        call_id="call_memory_read_auto",
        tool_name="read_memory",
        tool_input={"scope": "user"},
        context={
            "resume_content": {},
            "user_id": 42,
            "memory_dir": str(tmp_path),
        },
        confirmation_queue=confirmation_queue,
        event_queue=event_queue,
        event_callback=None,
        executed_tools=executed_tools,
        stream_state=stream_state,
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    assert "不写冗长 bullet" in str(result.details)
    assert not any(event.get("tool_pending") for event in events)
    assert not any(event.get("tool_confirmed") for event in events)
    assert executed_tools[0]["success"] is True
    assert stream_state["confirmation_wait_ms"] == 0.0


@pytest.mark.asyncio
async def test_update_memory_auto_executes_without_confirmation(tmp_path):
    """用于验证更新记忆不需要人类确认即可直接执行。"""
    agent = ResumeAgent()
    stage = ResumeToolExecutionStage()
    confirmation_queue: asyncio.Queue[bool] = asyncio.Queue()
    confirmation_queue.put_nowait(False)
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    stream_state = {
        "visible_tool_call_ids": set(),
        "confirmed_diff_items": [],
        "confirmation_wait_ms": 0.0,
        "chunk_index": 0,
        "response_parts": [],
    }
    executed_tools: list[dict[str, Any]] = []

    result = await stage.execute_tool_result(
        agent=agent.definition,
        run_id="run_memory_auto",
        call_id="call_memory_auto",
        tool_name="update_memory",
        tool_input={
            "operation": "append",
            "scope": "user",
            "kind": "preference",
            "content": "优化简历时保持简洁，不写冗长 bullet。",
            "reason": "用户明确表达长期偏好",
        },
        context={
            "resume_content": {},
            "user_id": 42,
            "memory_dir": str(tmp_path),
        },
        confirmation_queue=confirmation_queue,
        event_queue=event_queue,
        event_callback=None,
        executed_tools=executed_tools,
        stream_state=stream_state,
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    memory_file = tmp_path / "42" / "resume_memory.md"
    assert "不写冗长 bullet" in memory_file.read_text(encoding="utf-8")
    assert "记忆已更新" in str(result.details)
    assert not any(event.get("tool_pending") for event in events)
    assert not any(event.get("tool_confirmed") for event in events)
    assert executed_tools[0]["success"] is True
    assert stream_state["confirmation_wait_ms"] == 0.0


@pytest.mark.asyncio
async def test_update_memory_terminates_after_tool_result_without_second_llm(tmp_path):
    """用于验证记忆更新成功后采用 Pi-style tool result 直接结束。"""
    agent = ResumeAgent()
    stream = FakeLoopStream(
        [
            fake_loop_tool_call(
                name="update_memory",
                args={
                    "operation": "append",
                    "scope": "user",
                    "kind": "preference",
                    "content": "我喜欢可读性高的简历。",
                    "reason": "用户明确表达长期偏好",
                },
                call_id="call_memory_update",
            ),
            fake_loop_text("这轮不应该被请求。"),
        ]
    )
    stage = ResumeToolExecutionStage()
    loop = ResumeAgentLoop(stream_fn=stream, tool_stage=stage)
    state = _new_test_stream_state()
    context = {
        "resume_content": {},
        "user_id": 42,
        "memory_dir": str(tmp_path),
    }
    pi_context, prompts, config = _build_test_turn_inputs(
        agent,
        user_message="我喜欢可读性高的简历",
        context=context,
        state=state,
    )
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    executed_tools: list[dict[str, Any]] = []

    await loop.run(
        agent=agent.definition,
        run_id="run_memory_terminate",
        pi_context=pi_context,
        prompts=prompts,
        config=config,
        context=context,
        confirmation_queue=None,
        event_queue=event_queue,
        event_callback=None,
        state=state,
        executed_tools=executed_tools,
        model_name="test-model",
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    memory_file = tmp_path / "42" / "resume_memory.md"
    assert stream.calls == 1
    assert "可读性高" in memory_file.read_text(encoding="utf-8")
    assert "".join(state["response_parts"]) == "记忆已更新"
    assert any(event.get("display_message") == "记忆已更新" for event in events)
    assert executed_tools[0]["success"] is True


@pytest.mark.asyncio
async def test_resume_tool_preview_allows_hidden_section_additions():
    """用于验证隐藏模块不阻止新增技能条目进入确认预览。"""
    agent = ResumeAgent()
    stage = ResumeToolExecutionStage()
    resume = {
        "projects": [{"id": "proj_1", "name": "Chat Resume"}],
        "skills": [{"id": "skill_1", "category": "AI", "items": ["Agent"]}],
    }
    confirmation_queue: asyncio.Queue[bool] = asyncio.Queue()
    confirmation_queue.put_nowait(True)
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    stream_state = {
        "visible_tool_call_ids": set(),
        "confirmed_diff_items": [],
        "confirmation_wait_ms": 0.0,
        "chunk_index": 0,
        "response_parts": [],
    }
    executed_tools: list[dict[str, Any]] = []

    result = await stage.execute_tool_result(
        agent=agent.definition,
        run_id="run_hidden_preview",
        call_id="call_hidden_skills",
        tool_name="add_resume_item",
        tool_input={
            "section": "skills",
            "item": {"category": "AI & Agent", "items": ["ReAct"]},
            "source": "用户要求补充技能",
            "reason": "补充技能板块",
        },
        context={"resume_content": resume, "allowed_sections": {"projects"}},
        confirmation_queue=confirmation_queue,
        event_queue=event_queue,
        event_callback=None,
        executed_tools=executed_tools,
        stream_state=stream_state,
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    assert result.details["success"] is True
    assert result.details["updated_section"] == "skills"
    assert any(event.get("tool_pending") for event in events)
    assert not any(event.get("tool_call_failed") for event in events)
    assert executed_tools[0]["success"] is True
    assert resume["skills"][0] == {"id": "skill_1", "category": "AI", "items": ["Agent"]}
    assert resume["skills"][1]["category"] == "AI & Agent"


@pytest.mark.asyncio
async def test_resume_agent_loop_runs_react_turns_independently():
    """用于验证 ReAct loop 可以脱离 ResumeAgentRuntime 单独测试。"""
    agent = ResumeAgent()
    stream = FakeLoopStream(
        [
            fake_loop_tool_call(
                name="update_bullet",
                args={
                    "section": "work_experience",
                    "item_id": "work_1",
                    "bullet_id": "hl_1",
                    "text": "维护多个后台服务，支撑日活 10 万用户",
                    "reason": "补充业务规模",
                },
                call_id="call_loop_1",
            ),
            fake_loop_text("已完成优化。"),
        ]
    )
    stage = ResumeToolExecutionStage()
    loop = ResumeAgentLoop(stream_fn=stream, tool_stage=stage)
    resume = {
        "work_experience": [
            {
                "id": "work_1",
                "company": "某科技公司",
                "position": "Python 开发工程师",
                "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
            }
        ]
    }
    state = _new_test_stream_state()
    context = {"resume_content": resume, "allowed_sections": {"work_experience"}}
    pi_context, prompts, config = _build_test_turn_inputs(
        agent,
        user_message="优化这段工作经历",
        context=context,
        state=state,
    )
    confirmation_queue: asyncio.Queue[bool] = asyncio.Queue()
    confirmation_queue.put_nowait(True)
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    executed_tools: list[dict[str, Any]] = []

    await loop.run(
        agent=agent.definition,
        run_id="run_loop_test",
        pi_context=pi_context,
        prompts=prompts,
        config=config,
        context=context,
        confirmation_queue=confirmation_queue,
        event_queue=event_queue,
        event_callback=None,
        state=state,
        executed_tools=executed_tools,
        model_name="test-model",
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    assert stream.calls == 2
    assert any(event.get("event_type") == "llm_request" for event in events)
    assert any(event.get("tool_pending") for event in events)
    assert any(event.get("tool_confirmed") for event in events)
    assert any(event.get("content") == "已完成优化。" for event in events)
    assert resume["work_experience"][0]["highlights"][0]["text"] == (
        "维护多个后台服务，支撑日活 10 万用户"
    )


def test_openrouter_adapter_preserves_business_model_defaults():
    """用于验证 provider 配置从 runtime 中拆出且保留模型默认值。"""
    agent = ResumeAgent()

    config = build_openrouter_config(agent.definition)

    assert config.model.provider == "deepseek"
    assert config.model.api == "openai-compatible"
    assert config.temperature == agent.prompt_spec.model_defaults["temperature"]
    assert config.max_tokens == agent.prompt_spec.model_defaults["max_tokens"]


def test_long_resume_context_compacts_with_jd_and_confirmed_changes():
    """用于验证长简历上下文摘要保留 JD 和已确认改动。"""
    resume = {
        "job_application": {"jd_text": "需要 Python、Agent、性能优化"},
        "projects": [
            {
                "id": "proj_1",
                "name": "Chat Resume",
                "overview": "负责 Agent 简历优化" * 300,
                "highlights": [{"id": "hl_1", "text": "实现流式优化"}],
            }
        ],
    }

    compacted = maybe_compact_resume_context(
        resume_content=resume,
        confirmed_diff_items=[
            {"before": "实现流式优化", "after": "实现低延迟流式优化", "reason": "突出性能"}
        ],
        conversation_history=[{"role": "user", "content": "优化项目"}],
        threshold_chars=100,
    )

    assert compacted["summary_mode"] is True
    assert "性能优化" in compacted["jd_text"]
    assert "低延迟" in compacted["confirmed_changes"][0]
    assert compacted["resume_snapshot"]["projects"][0]["id"] == "proj_1"


def test_resume_agent_session_rebuilds_transcript_model_and_summary():
    """用于验证业务版 ResumeAgentSession 可从事件重建下一轮上下文。"""
    events = [
        SimpleNamespace(
            event_type="user_message",
            payload={"content": "优化项目"},
        ),
        SimpleNamespace(
            event_type="stream_event",
            payload={
                "event_type": "llm_request",
                "model": "openrouter/test",
                "tool_profile": "resume_edit",
                "tool_names": ["update_bullet"],
            },
        ),
        SimpleNamespace(
            event_type="tool_call_previewed",
            payload={"tool_call": {"id": "call_1"}},
        ),
        SimpleNamespace(
            event_type="agent_response",
            payload={"content": "已完成优化。"},
        ),
        SimpleNamespace(
            event_type="stream_event",
            payload={
                "event_type": "llm_response",
                "usage": {"input": 1, "output": 2, "total_tokens": 3},
            },
        ),
    ]

    session = ResumeAgentSession.from_events(
        events,
        resume_content={"projects": [{"id": "proj_1", "name": "Chat Resume"}]},
    )

    assert session.to_conversation_history() == [
        {"role": "user", "content": "优化项目"},
        {"role": "assistant", "content": "已完成优化。"},
    ]
    assert session.model_config is not None
    assert session.model_config.tool_profile == "resume_edit"
    assert session.pending_tool_call == {"id": "call_1"}
    assert session.usage["total_tokens"] == 3
    assert session.context_summary is not None


@pytest.mark.asyncio
async def test_stream_assistant_turn_only_publishes_first_tool_call_event():
    """用于验证每轮流式只向前端发布第一个工具调用事件，防止幽灵"运行中"卡片。"""
    agent = ResumeAgent()
    multi_tool_message = AssistantMessage(
        content=[
            ToolCall(id="call_first", name="read_memory", arguments={"key": "profile"}),
            ToolCall(id="call_second", name="read_memory", arguments={"key": "summary"}),
        ],
        stop_reason="toolUse",
    )
    stream_fn = FakeLoopStream([multi_tool_message])
    stage = ResumeToolExecutionStage()
    loop = ResumeAgentLoop(stream_fn=stream_fn, tool_stage=stage)
    state = _new_test_stream_state()
    context: dict[str, Any] = {"resume_content": {}}
    pi_context, _prompts, config = _build_test_turn_inputs(
        agent,
        user_message="分析",
        context=context,
        state=state,
    )
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    assistant_message, _deltas = await loop.stream_assistant_turn(
        run_id="test",
        llm_context=pi_context,
        config=config,
        event_queue=event_queue,
        event_callback=None,
        state=state,
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    tool_call_events = [e for e in events if e.get("event_type") == "tool_call"]
    assert len(tool_call_events) == 1, f"期望只发布1个工具调用事件，实际: {len(tool_call_events)}"
    assert tool_call_events[0]["call_id"] == "call_first"
    assert state["visible_tool_call_ids"] == {"call_first"}
    tool_calls_in_message = [b for b in assistant_message.content if isinstance(b, ToolCall)]
    assert len(tool_calls_in_message) == 1
    assert tool_calls_in_message[0].id == "call_first"


@pytest.mark.asyncio
async def test_model_stream_error_publishes_visible_message():
    """用于验证模型供应商错误不会让前端只收到空完成事件。"""
    agent = ResumeAgent()
    error_message = AssistantMessage(
        content=[],
        stop_reason="error",
        error_message="OpenRouter error 402: insufficient credits",
    )
    stream_fn = FakeLoopStream([error_message])
    stage = ResumeToolExecutionStage()
    loop = ResumeAgentLoop(stream_fn=stream_fn, tool_stage=stage)
    state = _new_test_stream_state()
    context: dict[str, Any] = {"resume_content": {}}
    pi_context, prompts, config = _build_test_turn_inputs(
        agent,
        user_message="你好",
        context=context,
        state=state,
    )
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    await loop.run(
        agent=agent.definition,
        run_id="test",
        pi_context=pi_context,
        prompts=prompts,
        config=config,
        context=context,
        confirmation_queue=None,
        event_queue=event_queue,
        event_callback=None,
        state=state,
        executed_tools=[],
        model_name="deepseek/deepseek-v4-pro",
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    visible_text = [event for event in events if event.get("event_type") == "text_delta"]
    assert visible_text
    assert visible_text[-1]["content"] == "AI服务暂时不可用，请稍后重试。"
    assert state["response_parts"] == ["AI服务暂时不可用，请稍后重试。"]


@pytest.mark.asyncio
async def test_stream_error_closes_visible_early_tool_call_event():
    """用于验证模型断流时已提前展示的工具卡片会收到失败收尾事件。"""
    agent = ResumeAgent()
    error_message = AssistantMessage(
        content=[
            ToolCall(id="call_interrupted", name="update_bullet", arguments={}),
        ],
        stop_reason="error",
        error_message="peer closed connection",
    )
    stream_fn = FakeLoopStream([error_message])
    stage = ResumeToolExecutionStage()
    loop = ResumeAgentLoop(stream_fn=stream_fn, tool_stage=stage)
    state = _new_test_stream_state()
    context: dict[str, Any] = {"resume_content": {}}
    pi_context, _prompts, config = _build_test_turn_inputs(
        agent,
        user_message="优化",
        context=context,
        state=state,
    )
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    assistant_message, _deltas = await loop.stream_assistant_turn(
        run_id="test",
        llm_context=pi_context,
        config=config,
        event_queue=event_queue,
        event_callback=None,
        state=state,
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    assert assistant_message.stop_reason == "error"
    assert [event.get("event_type") for event in events] == [
        "tool_call",
        "tool_call_failed",
    ]
    failed_event = events[1]
    assert failed_event["call_id"] == "call_interrupted"
    assert failed_event["tool_id"] == "update_bullet"
    assert failed_event["display_message"] == "peer closed connection"
