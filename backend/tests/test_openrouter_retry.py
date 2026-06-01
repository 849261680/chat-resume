"""测试 OpenRouter 指数退避重试逻辑。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pi_agent_core import (
    AgentContext,
    AgentTool,
    AgentToolResult,
    AgentToolSchema,
    AssistantMessage,
    Model,
    SimpleStreamOptions,
    TextContent,
    ToolCall,
)

from app.runtime import pi_agent_openrouter as openrouter
from app.runtime.pi_agent_openrouter import (
    OpenRouterCircuitOpenError,
    OpenRouterFirstEventTimeoutError,
    OpenRouterFirstTokenTimeoutError,
    OpenRouterHTTPError,
    _is_retryable_status,
    _openai_message,
    _openai_tools,
    _openrouter_body,
    _pump_openrouter_stream,
    _pump_with_retry,
    _retry_wait,
    _reset_openrouter_circuit_breaker,
)


# ---------------------------------------------------------------------------
# 单元测试：辅助函数
# ---------------------------------------------------------------------------


def test_retry_wait_uses_retry_after_when_provided():
    """Retry-After header 存在时应优先使用该值。"""
    wait = _retry_wait(attempt=0, retry_after=5.0)
    assert wait == 5.0


def test_retry_wait_caps_at_max():
    """Retry-After 超出上限时应被截断到 max_wait。"""
    wait = _retry_wait(attempt=0, retry_after=999.0)
    assert wait == 30.0


def test_retry_wait_exponential_without_retry_after():
    """无 Retry-After 时等待时间应在 [base*2^attempt, base*2^attempt + 1 + max_wait] 范围内。"""
    wait = _retry_wait(attempt=1, retry_after=None)
    # base=1, 2^1=2, jitter in [0,1) → 期望 2.0 ~ 3.0
    assert 2.0 <= wait < 4.0


def test_is_retryable_status_true():
    """429/502/503/504 应被视为可重试。"""
    for code in (429, 502, 503, 504):
        assert _is_retryable_status(code) is True


def test_is_retryable_status_false():
    """400/401/403/500 不应触发重试。"""
    for code in (400, 401, 403, 500):
        assert _is_retryable_status(code) is False


# ---------------------------------------------------------------------------
# 集成测试：_pump_with_retry 行为
# ---------------------------------------------------------------------------


def _make_args():
    """构造调用 _pump_with_retry 所需的最简 mock 参数。"""
    model = MagicMock()
    context = MagicMock()
    options = MagicMock()
    partial = MagicMock()
    queue: asyncio.Queue = asyncio.Queue()
    return model, context, options, partial, queue


class _FakeOpenRouterResponse:
    """用于模拟 httpx stream response。"""

    status_code = 200
    headers: dict[str, str] = {}

    def __init__(self, lines: list[str], *, delay_seconds: float = 0.0) -> None:
        """初始化响应行和每行前的延迟。"""
        self._lines = lines
        self._delay_seconds = delay_seconds

    async def __aenter__(self) -> "_FakeOpenRouterResponse":
        """进入异步响应上下文。"""
        return self

    async def __aexit__(self, *args: object) -> None:
        """退出异步响应上下文。"""

    async def aread(self) -> bytes:
        """返回错误响应体。"""
        return b""

    async def aiter_lines(self) -> AsyncIterator[str]:
        """逐行返回 SSE 内容。"""
        for line in self._lines:
            if self._delay_seconds:
                await asyncio.sleep(self._delay_seconds)
            yield line


class _FakeOpenRouterClient:
    """用于模拟 httpx.AsyncClient。"""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """接收并忽略 httpx.AsyncClient 参数。"""

    async def __aenter__(self) -> "_FakeOpenRouterClient":
        """进入异步 client 上下文。"""
        return self

    async def __aexit__(self, *args: object) -> None:
        """退出异步 client 上下文。"""

    def stream(self, *args: object, **kwargs: object) -> _FakeOpenRouterResponse:
        """返回可配置的假流式响应。"""
        return _FakeOpenRouterResponse(self.lines, delay_seconds=self.delay_seconds)

    lines: list[str] = []
    delay_seconds = 0.0


def _make_openrouter_stream_args() -> tuple[
    Model,
    AgentContext,
    SimpleStreamOptions,
    AssistantMessage,
    asyncio.Queue,
]:
    """构造调用 _pump_openrouter_stream 所需的最小参数。"""
    model = Model(api="openai-compatible", provider="openrouter", id="test/model")
    async def execute_tool(**_: object) -> AgentToolResult:
        """用于构造测试工具。"""
        return AgentToolResult(content=[])

    context = AgentContext(
        system_prompt="system",
        messages=[],
        tools=[
            AgentTool(
                name="update_bullet",
                description="Update bullet",
                execute=execute_tool,
            )
        ],
    )
    options = SimpleStreamOptions(api_key="test-key", temperature=0.1, max_tokens=8)
    partial = AssistantMessage(api=model.api, provider=model.provider, model=model.id)
    queue: asyncio.Queue = asyncio.Queue()
    return model, context, options, partial, queue


def test_openrouter_body_disables_reasoning_explicitly():
    """OpenRouter 请求体应显式关闭 reasoning，避免 provider 默认开启深度推理。"""
    model, context, options, _, _ = _make_openrouter_stream_args()

    body = _openrouter_body(model, context, options)

    assert body["reasoning"] == {"effort": "none", "exclude": True}
    assert body["reasoning_effort"] == "none"
    assert body["include_reasoning"] is False
    assert body["parallel_tool_calls"] is False


def test_openai_assistant_tool_call_omits_empty_content():
    """assistant 只有工具调用时不发送空 content，兼容 Kimi 类接口。"""
    message = AssistantMessage(api="openai-compatible", provider="openrouter", model="m")
    message.content.append(ToolCall(id="call_1", name="update_bullet", arguments={}))

    payload = _openai_message(message)

    assert payload is not None
    assert "content" not in payload
    assert payload["tool_calls"][0]["id"] == "call_1"


def test_openai_assistant_tool_call_keeps_non_empty_content():
    """assistant 工具调用带可见文本时保留 content。"""
    message = AssistantMessage(api="openai-compatible", provider="openrouter", model="m")
    message.content.append(TextContent(text="我会更新。"))
    message.content.append(ToolCall(id="call_1", name="update_bullet", arguments={}))

    payload = _openai_message(message)

    assert payload is not None
    assert payload["content"] == "我会更新。"


def test_openai_tools_normalizes_enum_property_types():
    """工具 schema 中 enum-only 字段应补 type，避免兼容层拒绝。"""
    async def execute_tool() -> AgentToolResult:
        """用于构造测试工具。"""
        return AgentToolResult(content=[])

    context = AgentContext(
        system_prompt="system",
        messages=[],
        tools=[
            AgentTool(
                name="update_profile",
                description="Update profile",
                parameters=AgentToolSchema(
                    properties={
                        "tone": {"enum": ["formal", "direct"]},
                        "count": {"enum": [1, 2]},
                        "confirmed": {"enum": [True, False]},
                        "meta": {
                            "properties": {"level": {"enum": [1, 2]}},
                        },
                    },
                    required=["tone"],
                ),
                execute=execute_tool,
            )
        ],
    )

    tool = _openai_tools(context)[0]
    properties = tool["function"]["parameters"]["properties"]

    assert properties["tone"]["type"] == "string"
    assert properties["count"]["type"] == "number"
    assert properties["confirmed"]["type"] == "boolean"
    assert properties["meta"]["type"] == "object"
    assert properties["meta"]["properties"]["level"]["type"] == "number"


def test_resume_update_skills_schema_uses_provider_safe_field_name():
    """update_skills 不应暴露 items 作为参数名，避免 provider 误判 schema。"""
    from app.tools.resume.registry import RESUME_TOOLS_SCHEMA

    schema = next(
        item
        for item in RESUME_TOOLS_SCHEMA
        if item.get("function", {}).get("name") == "update_skills"
    )
    parameters = schema["function"]["parameters"]
    properties = parameters["properties"]

    assert "skills" in properties
    assert "items" not in properties
    assert "skills" in parameters["required"]


@pytest.mark.asyncio
async def test_openrouter_stream_logs_latency_stages(caplog: pytest.LogCaptureFixture):
    """OpenRouter 流式请求应记录关键阶段，便于定位慢在哪一段。"""
    model, context, options, partial, queue = _make_openrouter_stream_args()
    _FakeOpenRouterClient.lines = [
        'data: {"choices":[{"delta":{"content":"你好"}}]}',
        "data: [DONE]",
    ]
    _FakeOpenRouterClient.delay_seconds = 0.0

    with caplog.at_level(logging.DEBUG, logger="app.runtime.pi_agent_openrouter"), patch(
        "app.runtime.pi_agent_openrouter.httpx.AsyncClient",
        _FakeOpenRouterClient,
    ):
        await _pump_openrouter_stream(model, context, options, partial, queue)

    messages = [record.getMessage() for record in caplog.records]
    assert "openrouter.stream.request_started" in messages
    assert "openrouter.stream.headers_received" in messages
    assert "openrouter.stream.first_sse_line" in messages
    assert "openrouter.stream.first_text_delta" in messages
    assert "openrouter.stream.done" in messages
    done_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "openrouter.stream.done"
    )
    assert getattr(done_record, "text_chars") == 2
    assert getattr(done_record, "tool_call_count") == 0


@pytest.mark.asyncio
async def test_openrouter_stream_logs_safe_pre_delta_summaries(
    caplog: pytest.LogCaptureFixture,
):
    """首有效 delta 前应记录脱敏 SSE 结构，便于判断 70 秒卡在哪。"""
    model, context, options, partial, queue = _make_openrouter_stream_args()
    _FakeOpenRouterClient.lines = [
        'data: {"choices":[{"delta":{}}]}',
        'data: {"choices":[{"delta":{"role":"assistant"}}]}',
        (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
            '"function":{"arguments":"{\\"section\\""}}]}}]}'
        ),
        'data: {"choices":[{"delta":{"content":"好"}}]}',
        "data: [DONE]",
    ]
    _FakeOpenRouterClient.delay_seconds = 0.0

    with caplog.at_level(logging.INFO, logger="app.runtime.pi_agent_openrouter"), patch(
        "app.runtime.pi_agent_openrouter.httpx.AsyncClient",
        _FakeOpenRouterClient,
    ):
        await _pump_openrouter_stream(model, context, options, partial, queue)

    records = [
        record
        for record in caplog.records
        if record.getMessage() == "openrouter.stream.pre_delta_line"
    ]
    messages = "\n".join(record.getMessage() for record in records)

    assert len(records) == 4
    assert getattr(records[0], "delta_keys") == []
    assert getattr(records[1], "delta_keys") == ["role"]
    assert getattr(records[2], "tool_call_count") == 1
    assert getattr(records[2], "tool_arg_delta_chars") == len('{"section"')
    assert getattr(records[3], "content_chars") == 1
    assert all(hasattr(record, "wait_ms") for record in records)
    assert "section" not in messages
    assert "好" not in messages


@pytest.mark.asyncio
async def test_openrouter_stream_logs_first_tool_delta(
    caplog: pytest.LogCaptureFixture,
):
    """工具流式增量应记录首个 delta、累计参数状态和最终 emit。"""
    model, context, options, partial, queue = _make_openrouter_stream_args()
    _FakeOpenRouterClient.lines = [
        (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
            '"id":"call_1","function":{"name":"update_bullet",'
            '"arguments":"{}"}}]},"finish_reason":"tool_calls"}]}'
        ),
        "data: [DONE]",
    ]
    _FakeOpenRouterClient.delay_seconds = 0.0

    with caplog.at_level(logging.DEBUG, logger="app.runtime.pi_agent_openrouter"), patch(
        "app.runtime.pi_agent_openrouter.httpx.AsyncClient",
        _FakeOpenRouterClient,
    ):
        await _pump_openrouter_stream(model, context, options, partial, queue)

    info_messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.INFO
    ]
    assert "openrouter.stream.tool_delta" not in info_messages
    delta_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "openrouter.stream.tool_delta"
    )
    assert delta_record.levelno == logging.DEBUG
    assert getattr(delta_record, "arg_delta_chars") == 2
    tool_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "openrouter.stream.first_tool_delta"
    )
    assert getattr(tool_record, "tool_names") == ["update_bullet"]
    finish_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "openrouter.stream.finish_reason"
    )
    assert getattr(finish_record, "tool_count") == 1
    assert not hasattr(finish_record, "tool_buffers")
    complete_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "openrouter.stream.tool_args_complete"
    )
    assert getattr(complete_record, "tool_count") == 1
    assert getattr(complete_record, "tool_buffers") == [
        {
            "index": 0,
            "id_chars": 6,
            "name": "update_bullet",
            "args_chars": 2,
            "args_json_status": "object",
        }
    ]


@pytest.mark.asyncio
async def test_openrouter_stream_emits_early_tool_call_start():
    """工具名可识别时应先发送 start 事件，参数完整后再发送 end 事件。"""
    model, context, options, partial, queue = _make_openrouter_stream_args()
    _FakeOpenRouterClient.lines = [
        (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
            '"id":"call_1","function":{"name":"update_bullet"}}]}}]}'
        ),
        (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
            '"function":{"arguments":"{\\"section\\":\\"work_experience\\"}"}}]}}]}'
        ),
        "data: [DONE]",
    ]
    _FakeOpenRouterClient.delay_seconds = 0.0

    with patch(
        "app.runtime.pi_agent_openrouter.httpx.AsyncClient",
        _FakeOpenRouterClient,
    ):
        await _pump_openrouter_stream(model, context, options, partial, queue)

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    tool_starts = [
        event for event in events if getattr(event, "type", "") == "toolcall_start"
    ]
    tool_ends = [
        event for event in events if getattr(event, "type", "") == "toolcall_end"
    ]

    assert len(tool_starts) == 2
    assert len(tool_ends) == 1
    early_tool = tool_starts[0].partial.content[0]
    assert isinstance(early_tool, ToolCall)
    assert early_tool.id == "call_1"
    assert early_tool.name == "update_bullet"
    assert early_tool.arguments == {}
    assert tool_ends[0].tool_call.arguments == {"section": "work_experience"}


@pytest.mark.asyncio
async def test_openrouter_stream_cuts_off_after_first_complete_tool_call(
    caplog: pytest.LogCaptureFixture,
):
    """首个工具参数完整后应停止读取后续工具调用。"""
    model, context, options, partial, queue = _make_openrouter_stream_args()
    _FakeOpenRouterClient.lines = [
        (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
            '"id":"call_1","function":{"name":"update_bullet",'
            '"arguments":"{\\"section\\":\\"work_experience\\"}"}}]}}]}'
        ),
        (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":1,'
            '"id":"call_2","function":{"name":"update_bullet",'
            '"arguments":"{\\"section\\":\\"projects\\"}"}}]},'
            '"finish_reason":"tool_calls"}]}'
        ),
        "data: [DONE]",
    ]
    _FakeOpenRouterClient.delay_seconds = 0.0

    with caplog.at_level(logging.INFO, logger="app.runtime.pi_agent_openrouter"), patch(
        "app.runtime.pi_agent_openrouter.httpx.AsyncClient",
        _FakeOpenRouterClient,
    ):
        await _pump_openrouter_stream(model, context, options, partial, queue)

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    tool_ends = [
        event for event in events if getattr(event, "type", "") == "toolcall_end"
    ]
    cutoff_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "openrouter.stream.single_tool_cutoff"
    )
    done_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "openrouter.stream.done"
    )

    assert partial.stop_reason == "toolUse"
    assert [tool.tool_call.id for tool in tool_ends] == ["call_1"]
    assert getattr(cutoff_record, "tool_name") == "update_bullet"
    assert getattr(done_record, "tool_call_count") == 1


@pytest.mark.asyncio
async def test_openrouter_stream_does_not_concatenate_repeated_tool_id_or_name():
    """同一 index 的重复 id/name 只设置一次，arguments 才累加。"""
    model, context, options, partial, queue = _make_openrouter_stream_args()
    _FakeOpenRouterClient.lines = [
        (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
            '"id":"call_1","function":{"name":"update_bullet",'
            '"arguments":"{\\"section\\":"}}]}}]}'
        ),
        (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
            '"id":"call_1","function":{"name":"update_bullet",'
            '"arguments":"\\"work_experience\\"}"}}]},'
            '"finish_reason":"tool_calls"}]}'
        ),
        "data: [DONE]",
    ]
    _FakeOpenRouterClient.delay_seconds = 0.0

    with patch(
        "app.runtime.pi_agent_openrouter.httpx.AsyncClient",
        _FakeOpenRouterClient,
    ):
        await _pump_openrouter_stream(model, context, options, partial, queue)

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    tool_ends = [
        event for event in events if getattr(event, "type", "") == "toolcall_end"
    ]

    assert len(tool_ends) == 1
    assert tool_ends[0].tool_call.id == "call_1"
    assert tool_ends[0].tool_call.name == "update_bullet"
    assert tool_ends[0].tool_call.arguments == {"section": "work_experience"}


@pytest.mark.asyncio
async def test_openrouter_stream_keeps_invalid_tool_arguments_recoverable():
    """工具参数 JSON 损坏时应生成可恢复工具错误，而不是中断整条流。"""
    model, context, options, partial, queue = _make_openrouter_stream_args()
    _FakeOpenRouterClient.lines = [
        (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
            '"id":"call_bad","function":{"name":"update_bullet",'
            '"arguments":"{\\"section\\":\\"projects\\","}}]},'
            '"finish_reason":"tool_calls"}]}'
        ),
        "data: [DONE]",
    ]
    _FakeOpenRouterClient.delay_seconds = 0.0

    with patch(
        "app.runtime.pi_agent_openrouter.httpx.AsyncClient",
        _FakeOpenRouterClient,
    ):
        await _pump_openrouter_stream(model, context, options, partial, queue)

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    tool_ends = [
        event for event in events if getattr(event, "type", "") == "toolcall_end"
    ]

    assert partial.stop_reason == "toolUse"
    assert len(tool_ends) == 1
    assert tool_ends[0].tool_call.arguments["__tool_arguments_parse_error"]["type"] == (
        "invalid_arguments_json"
    )


@pytest.mark.asyncio
async def test_openrouter_stream_ignores_tool_finish_reason_without_tool_call():
    """仅 finish_reason=tool_calls 不能让主循环进入工具调用分支。"""
    model, context, options, partial, queue = _make_openrouter_stream_args()
    _FakeOpenRouterClient.lines = [
        'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
        "data: [DONE]",
    ]
    _FakeOpenRouterClient.delay_seconds = 0.0

    with patch(
        "app.runtime.pi_agent_openrouter.httpx.AsyncClient",
        _FakeOpenRouterClient,
    ):
        await _pump_openrouter_stream(model, context, options, partial, queue)

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    tool_events = [
        event for event in events if str(getattr(event, "type", "")).startswith("toolcall")
    ]

    assert partial.stop_reason == "stop"
    assert partial.content == []
    assert tool_events == []


@pytest.mark.asyncio
async def test_openrouter_stream_times_out_before_first_event(
    monkeypatch: pytest.MonkeyPatch,
):
    """响应头后迟迟没有 SSE 时应快速失败，而不是等完整 read timeout。"""
    model, context, options, partial, queue = _make_openrouter_stream_args()
    _FakeOpenRouterClient.lines = ["data: [DONE]"]
    _FakeOpenRouterClient.delay_seconds = 0.05
    monkeypatch.setattr(openrouter.settings, "OPENROUTER_FIRST_EVENT_TIMEOUT_SECONDS", 0.01)

    with patch(
        "app.runtime.pi_agent_openrouter.httpx.AsyncClient",
        _FakeOpenRouterClient,
    ):
        with pytest.raises(OpenRouterFirstEventTimeoutError):
            await _pump_openrouter_stream(model, context, options, partial, queue)


@pytest.mark.asyncio
async def test_openrouter_stream_times_out_before_first_token(
    monkeypatch: pytest.MonkeyPatch,
):
    """首条 SSE 之后迟迟没有文本或工具增量时应快速失败。"""
    model, context, options, partial, queue = _make_openrouter_stream_args()
    _FakeOpenRouterClient.lines = [
        'data: {"choices":[{"delta":{}}]}',
        'data: {"choices":[{"delta":{"content":"晚了"}}]}',
    ]
    _FakeOpenRouterClient.delay_seconds = 0.05
    monkeypatch.setattr(openrouter.settings, "OPENROUTER_FIRST_EVENT_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(openrouter.settings, "OPENROUTER_FIRST_TOKEN_TIMEOUT_SECONDS", 0.01)

    with patch(
        "app.runtime.pi_agent_openrouter.httpx.AsyncClient",
        _FakeOpenRouterClient,
    ):
        with pytest.raises(OpenRouterFirstTokenTimeoutError):
            await _pump_openrouter_stream(model, context, options, partial, queue)


@pytest.mark.asyncio
async def test_openrouter_first_token_timeout_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
):
    """首 token 超时设为 0 时应关闭该阶段限制。"""
    model, context, options, partial, queue = _make_openrouter_stream_args()
    _FakeOpenRouterClient.lines = [
        'data: {"choices":[{"delta":{}}]}',
        'data: {"choices":[{"delta":{"content":"慢一点"}}]}',
        "data: [DONE]",
    ]
    _FakeOpenRouterClient.delay_seconds = 0.02
    monkeypatch.setattr(openrouter.settings, "OPENROUTER_FIRST_EVENT_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(openrouter.settings, "OPENROUTER_FIRST_TOKEN_TIMEOUT_SECONDS", 0.0)

    with patch(
        "app.runtime.pi_agent_openrouter.httpx.AsyncClient",
        _FakeOpenRouterClient,
    ):
        await _pump_openrouter_stream(model, context, options, partial, queue)

    assert partial.stop_reason == "stop"


@pytest.mark.asyncio
async def test_429_retry_then_success():
    """429 后重试，第二次成功，最终不抛出异常。"""
    model, context, options, partial, queue = _make_args()
    call_count = 0

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OpenRouterHTTPError(status_code=429, message="rate limited")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=3,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=False,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await _pump_with_retry(model, context, options, partial, queue)

    assert call_count == 2


@pytest.mark.asyncio
async def test_503_all_retries_exhausted_raises():
    """503 连续失败超过最大重试次数后应抛出最后一次异常。"""
    model, context, options, partial, queue = _make_args()

    async def fake_pump(*args, **kwargs):
        raise OpenRouterHTTPError(status_code=503, message="service unavailable")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=3,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=False,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        with pytest.raises(OpenRouterHTTPError) as exc_info:
            await _pump_with_retry(model, context, options, partial, queue)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_429_with_retry_after_header_uses_header_value():
    """429 含 Retry-After 时应以 header 值作为等待时间。"""
    model, context, options, partial, queue = _make_args()
    call_count = 0
    sleep_calls: list[float] = []

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OpenRouterHTTPError(status_code=429, message="rate limited", retry_after=7.0)

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=3,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=False,
    ), patch(
        "asyncio.sleep",
        side_effect=fake_sleep,
    ):
        await _pump_with_retry(model, context, options, partial, queue)

    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 7.0


@pytest.mark.asyncio
async def test_400_non_retryable_raises_immediately():
    """400 不属于可重试状态码，应立即抛出，不进行任何重试。"""
    model, context, options, partial, queue = _make_args()
    call_count = 0

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise OpenRouterHTTPError(status_code=400, message="bad request")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=3,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=False,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        with pytest.raises(OpenRouterHTTPError) as exc_info:
            await _pump_with_retry(model, context, options, partial, queue)

    assert call_count == 1
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_connect_error_retried():
    """httpx.ConnectError 应触发重试，最终全部失败时抛出。"""
    model, context, options, partial, queue = _make_args()
    call_count = 0

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.ConnectError("connection refused")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=2,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=False,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        with pytest.raises(httpx.ConnectError):
            await _pump_with_retry(model, context, options, partial, queue)

    # 初始 1 次 + 2 次重试 = 3 次总调用
    assert call_count == 3


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_repeated_failures():
    """连续请求失败达到阈值后应快速失败，不再调用 OpenRouter。"""
    _reset_openrouter_circuit_breaker()
    model, context, options, partial, queue = _make_args()
    call_count = 0

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise OpenRouterHTTPError(status_code=503, message="service unavailable")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=0,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=True,
        OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD=2,
        OPENROUTER_CIRCUIT_BREAKER_COOLDOWN_SECONDS=60,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        for _ in range(2):
            with pytest.raises(OpenRouterHTTPError):
                await _pump_with_retry(model, context, options, partial, queue)

        with pytest.raises(OpenRouterCircuitOpenError):
            await _pump_with_retry(model, context, options, partial, queue)

    assert call_count == 2


@pytest.mark.asyncio
async def test_circuit_breaker_allows_probe_after_cooldown():
    """open 冷却期结束后应允许一次探测请求，成功后恢复 closed。"""
    _reset_openrouter_circuit_breaker()
    model, context, options, partial, queue = _make_args()
    call_count = 0
    now = 1000.0

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise OpenRouterHTTPError(status_code=503, message="service unavailable")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=0,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=True,
        OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD=2,
        OPENROUTER_CIRCUIT_BREAKER_COOLDOWN_SECONDS=60,
    ), patch(
        "app.runtime.pi_agent_openrouter.monotonic",
        side_effect=lambda: now,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        for _ in range(2):
            with pytest.raises(OpenRouterHTTPError):
                await _pump_with_retry(model, context, options, partial, queue)

        with pytest.raises(OpenRouterCircuitOpenError):
            await _pump_with_retry(model, context, options, partial, queue)

        now = 1061.0
        await _pump_with_retry(model, context, options, partial, queue)
        await _pump_with_retry(model, context, options, partial, queue)

    assert call_count == 4
