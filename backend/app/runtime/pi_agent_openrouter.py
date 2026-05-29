"""用于把 OpenRouter 流式响应适配为 pi-agent-core 事件。"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from time import monotonic
from typing import Any
from urllib.parse import urlparse

import httpx
from pi_agent_core import (
    AgentContext,
    AssistantMessage,
    AssistantMessageEvent,
    Model,
    SimpleStreamOptions,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamResult,
    StreamStartEvent,
    StreamTextDeltaEvent,
    StreamTextEndEvent,
    StreamTextStartEvent,
    StreamToolCallEndEvent,
    StreamToolCallStartEvent,
    TextContent,
    ToolCall,
    StopReason,
    Usage,
)

from app.infra.config import settings


async def stream_openrouter(
    model: Model,
    context: AgentContext,
    options: SimpleStreamOptions,
) -> StreamResult:
    """用于处理流式OpenRouter。"""
    queue: asyncio.Queue[AssistantMessageEvent | None] = asyncio.Queue()
    done = asyncio.Event()
    state: dict[str, AssistantMessage | None] = {"final": None}
    partial = AssistantMessage(api=model.api, provider=model.provider, model=model.id)

    async def events_iter():
        """用于按顺序输出适配后的流式事件。"""
        while True:
            event = await queue.get()
            if event is None:
                return
            yield event

    async def result() -> AssistantMessage:
        """用于等待并返回最终助手消息。"""
        await done.wait()
        final = state["final"]
        if final is None:
            raise RuntimeError("OpenRouter stream ended without a final message")
        return final

    async def run_stream() -> None:
        """用于拉取模型流并写入本地事件队列。"""
        try:
            await _pump_with_retry(model, context, options, partial, queue)
            state["final"] = partial
        except Exception as exc:
            partial.stop_reason = "error"
            partial.error_message = str(exc)
            queue.put_nowait(StreamErrorEvent(reason="error", error=partial))
            state["final"] = partial
        finally:
            done.set()
            queue.put_nowait(None)

    asyncio.create_task(run_stream())
    return {"events": events_iter(), "result": result}


_logger = logging.getLogger(__name__)

# 需要重试的 HTTP 状态码
_RETRY_STATUS_CODES = {429, 502, 503, 504}
_RETRY_BASE_SECONDS = 1.0
_RETRY_MAX_WAIT_SECONDS = 30.0
_TOOL_ARGUMENTS_PARSE_ERROR_KEY = "__tool_arguments_parse_error"


class OpenRouterHTTPError(Exception):
    """携带 HTTP 状态码和可选 Retry-After 的 OpenRouter 错误。"""

    def __init__(self, status_code: int, message: str, retry_after: float | None = None) -> None:
        """初始化并保存状态码和 Retry-After 值。"""
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class OpenRouterCircuitOpenError(Exception):
    """表示 OpenRouter circuit breaker 已打开，当前请求被快速拒绝。"""


class OpenRouterFirstEventTimeoutError(TimeoutError):
    """表示 OpenRouter 已返回响应头但迟迟没有首条 SSE 事件。"""


class OpenRouterFirstTokenTimeoutError(TimeoutError):
    """表示 OpenRouter 已有 SSE 事件但迟迟没有文本或工具增量。"""


@dataclass(frozen=True)
class _ChunkApplication:
    """用于记录单个 OpenRouter chunk 应用后产生的可观测变化。"""

    text_started: bool
    text_delta_chars: int = 0
    tool_names: tuple[str, ...] = ()
    tool_arg_delta_chars: int = 0


@dataclass
class _OpenRouterStreamProgress:
    """用于跟踪 OpenRouter 单次流式响应的阶段状态。"""

    text_started: bool = False
    finish_reason: str = "stop"
    first_sse_seen: bool = False
    first_delta_seen: bool = False
    first_text_seen: bool = False
    first_tool_seen: bool = False
    text_chars: int = 0


@dataclass
class _OpenRouterCircuitBreaker:
    """用于记录 OpenRouter 调用失败状态并决定是否快速失败。"""

    failure_count: int = 0
    opened_at: float | None = None

    def before_request(self, *, enabled: bool, cooldown_seconds: float) -> None:
        """请求前检查 circuit 是否仍处于 open 冷却期。"""
        if not enabled or self.opened_at is None:
            return
        if monotonic() - self.opened_at >= cooldown_seconds:
            self.opened_at = None
            return
        raise OpenRouterCircuitOpenError("OpenRouter circuit breaker is open")

    def record_success(self) -> None:
        """请求成功后清空失败状态。"""
        self.failure_count = 0
        self.opened_at = None

    def record_failure(self, *, enabled: bool, threshold: int) -> None:
        """请求最终失败后累加失败次数并在达到阈值时打开 circuit。"""
        if not enabled:
            return
        self.failure_count += 1
        if self.failure_count >= threshold:
            self.opened_at = monotonic()


_OPENROUTER_CIRCUIT_BREAKER = _OpenRouterCircuitBreaker()


def _reset_openrouter_circuit_breaker() -> None:
    """用于测试或进程内恢复时重置 OpenRouter circuit breaker。"""
    _OPENROUTER_CIRCUIT_BREAKER.record_success()


def _retry_wait(attempt: int, retry_after: float | None) -> float:
    """根据重试次数计算指数退避等待时间，优先使用 Retry-After 头的值。"""
    if retry_after is not None:
        return min(retry_after, _RETRY_MAX_WAIT_SECONDS)
    backoff = _RETRY_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 1)
    return min(backoff, _RETRY_MAX_WAIT_SECONDS)


def _is_retryable_status(status_code: int) -> bool:
    """判断 HTTP 状态码是否应该触发重试。"""
    return status_code in _RETRY_STATUS_CODES


async def _pump_with_retry(
    model: Model,
    context: AgentContext,
    options: SimpleStreamOptions,
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
) -> None:
    """包装 _pump_openrouter_stream，对可重试错误执行指数退避重试。"""
    max_retries = settings.OPENROUTER_MAX_RETRIES
    circuit_enabled = settings.OPENROUTER_CIRCUIT_BREAKER_ENABLED
    circuit_failure_threshold = settings.OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD
    circuit_cooldown_seconds = settings.OPENROUTER_CIRCUIT_BREAKER_COOLDOWN_SECONDS
    last_exc: Exception | None = None

    _OPENROUTER_CIRCUIT_BREAKER.before_request(
        enabled=circuit_enabled,
        cooldown_seconds=circuit_cooldown_seconds,
    )

    for attempt in range(max_retries + 1):
        try:
            await _pump_openrouter_stream(model, context, options, partial, queue)
            _OPENROUTER_CIRCUIT_BREAKER.record_success()
            return
        except OpenRouterHTTPError as exc:
            if not _is_retryable_status(exc.status_code):
                raise
            last_exc = exc
            retry_after = exc.retry_after
            status_code: int | None = exc.status_code
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            last_exc = exc
            retry_after = None
            status_code = None

        if attempt >= max_retries:
            break

        wait = _retry_wait(attempt, retry_after)
        _logger.warning(
            "OpenRouter 请求失败，准备重试 attempt=%d/%d status=%s wait=%.1fs error=%s",
            attempt + 1,
            max_retries,
            status_code,
            wait,
            last_exc,
        )
        await asyncio.sleep(wait)

    assert last_exc is not None
    _OPENROUTER_CIRCUIT_BREAKER.record_failure(
        enabled=circuit_enabled,
        threshold=circuit_failure_threshold,
    )
    raise last_exc


async def _pump_openrouter_stream(
    model: Model,
    context: AgentContext,
    options: SimpleStreamOptions,
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
) -> None:
    """用于处理pumpOpenRouter流式。"""
    body = _openrouter_body(model, context, options)
    headers = _openrouter_headers(options)
    text_index = 0
    text_buffer: list[str] = []
    tool_buffers: dict[int, dict[str, Any]] = {}
    allowed_tool_names = _context_tool_names(context)
    progress = _OpenRouterStreamProgress()
    started_at = monotonic()

    timeout = httpx.Timeout(
        connect=settings.OPENROUTER_CONNECT_TIMEOUT_SECONDS,
        read=settings.OPENROUTER_READ_TIMEOUT_SECONDS,
        write=settings.OPENROUTER_WRITE_TIMEOUT_SECONDS,
        pool=settings.OPENROUTER_CONNECT_TIMEOUT_SECONDS,
    )
    _log_openrouter_stage(
        "request_started",
        started_at=started_at,
        model=model.id,
        message_count=len(body.get("messages", [])),
        tool_count=len(body.get("tools", [])),
    )
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.OPENROUTER_API_BASE.rstrip('/')}/chat/completions",
                headers=headers,
                json=body,
            ) as response:
                _log_openrouter_stage(
                    "headers_received",
                    started_at=started_at,
                    model=model.id,
                    status_code=response.status_code,
                )
                await _raise_for_openrouter_error(response)
                await _consume_openrouter_response(
                    response=response,
                    model=model,
                    options=options,
                    partial=partial,
                    queue=queue,
                    tool_buffers=tool_buffers,
                    allowed_tool_names=allowed_tool_names,
                    text_buffer=text_buffer,
                    progress=progress,
                    started_at=started_at,
                    text_index=text_index,
                )
    except Exception as exc:
        _log_openrouter_stage(
            "error",
            started_at=started_at,
            model=model.id,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise

    if progress.text_started:
        queue.put_nowait(
            StreamTextEndEvent(
                content_index=text_index,
                content="".join(text_buffer),
                partial=partial,
            )
        )
    if tool_buffers:
        _log_openrouter_stage(
            "tool_args_complete",
            started_at=started_at,
            model=model.id,
            finish_reason=progress.finish_reason,
            usage_output=getattr(partial.usage, "output", 0) if partial.usage else 0,
            tool_count=len(tool_buffers),
            tool_buffers=_tool_buffer_summary(tool_buffers),
        )
    _emit_tool_calls(
        tool_buffers,
        partial,
        queue,
        started_at=started_at,
        model=model,
    )
    partial.stop_reason = "toolUse" if tool_buffers else _stop_reason(progress.finish_reason)
    _log_openrouter_stage(
        "done",
        started_at=started_at,
        model=model.id,
        finish_reason=progress.finish_reason,
        stop_reason=partial.stop_reason,
        text_chars=progress.text_chars,
        tool_call_count=len(tool_buffers),
    )
    queue.put_nowait(StreamDoneEvent(reason=partial.stop_reason, message=partial))


async def _consume_openrouter_response(
    *,
    response: httpx.Response,
    model: Model,
    options: SimpleStreamOptions,
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
    tool_buffers: dict[int, dict[str, Any]],
    allowed_tool_names: set[str],
    text_buffer: list[str],
    progress: _OpenRouterStreamProgress,
    started_at: float,
    text_index: int,
) -> None:
    """用于消费 OpenRouter SSE 响应并更新本地 stream progress。"""
    queue.put_nowait(StreamStartEvent(partial=partial))
    line_iter = response.aiter_lines().__aiter__()
    while True:
        if _cancelled(options):
            raise RuntimeError("Request aborted by user")
        try:
            line = await _next_openrouter_line(
                line_iter=line_iter,
                first_sse_seen=progress.first_sse_seen,
                first_delta_seen=progress.first_delta_seen,
                started_at=started_at,
            )
        except StopAsyncIteration:
            return
        should_continue = _handle_openrouter_line(
            line=line,
            model=model,
            partial=partial,
            queue=queue,
            tool_buffers=tool_buffers,
            allowed_tool_names=allowed_tool_names,
            text_buffer=text_buffer,
            progress=progress,
            started_at=started_at,
            text_index=text_index,
        )
        if not should_continue:
            return


def _handle_openrouter_line(
    *,
    line: str,
    model: Model,
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
    tool_buffers: dict[int, dict[str, Any]],
    allowed_tool_names: set[str],
    text_buffer: list[str],
    progress: _OpenRouterStreamProgress,
    started_at: float,
    text_index: int,
) -> bool:
    """用于处理单行 OpenRouter SSE，返回是否继续读取。"""
    chunk = _decode_sse_line(line)
    if chunk is None:
        return True
    _mark_first_sse_if_needed(progress, started_at=started_at, model=model)
    if chunk == "[DONE]":
        return False
    if not isinstance(chunk, dict):
        return True
    applied = _apply_openrouter_chunk(
        chunk=chunk,
        partial=partial,
        queue=queue,
        tool_buffers=tool_buffers,
        allowed_tool_names=allowed_tool_names,
        text_buffer=text_buffer,
        text_started=progress.text_started,
        text_index=text_index,
        started_at=started_at,
        model=model,
    )
    _record_chunk_application(
        applied,
        progress=progress,
        tool_buffers=tool_buffers,
        started_at=started_at,
        model=model,
    )
    previous_finish_reason = progress.finish_reason
    progress.finish_reason = _finish_reason(chunk, progress.finish_reason)
    if progress.finish_reason != previous_finish_reason:
        _log_openrouter_stage(
            "finish_reason",
            started_at=started_at,
            model=model.id,
            finish_reason=progress.finish_reason,
            tool_count=len(tool_buffers),
        )
    return True


def _mark_first_sse_if_needed(
    progress: _OpenRouterStreamProgress,
    *,
    started_at: float,
    model: Model,
) -> None:
    """用于记录首条 SSE 行到达时间。"""
    if progress.first_sse_seen:
        return
    progress.first_sse_seen = True
    _log_openrouter_stage("first_sse_line", started_at=started_at, model=model.id)


def _record_chunk_application(
    applied: _ChunkApplication,
    *,
    progress: _OpenRouterStreamProgress,
    tool_buffers: dict[int, dict[str, Any]],
    started_at: float,
    model: Model,
) -> None:
    """用于记录 chunk 应用后的首文本和首工具增量。"""
    progress.text_started = applied.text_started
    progress.text_chars += applied.text_delta_chars
    if applied.text_delta_chars and not progress.first_text_seen:
        progress.first_text_seen = True
        progress.first_delta_seen = True
        _log_openrouter_stage(
            "first_text_delta",
            started_at=started_at,
            model=model.id,
            text_delta_chars=applied.text_delta_chars,
        )
    if applied.tool_names and not progress.first_tool_seen:
        progress.first_tool_seen = True
        progress.first_delta_seen = True
        _log_openrouter_stage(
            "first_tool_delta",
            started_at=started_at,
            model=model.id,
            tool_names=list(applied.tool_names),
        )
    if applied.tool_names or applied.tool_arg_delta_chars:
        _log_openrouter_stage(
            "tool_delta",
            started_at=started_at,
            model=model.id,
            tool_names=list(applied.tool_names),
            arg_delta_chars=applied.tool_arg_delta_chars,
            tool_buffers=_tool_buffer_summary(tool_buffers),
            log_level=logging.DEBUG,
        )


def _openrouter_body(
    model: Model,
    context: AgentContext,
    options: SimpleStreamOptions,
) -> dict[str, Any]:
    """用于处理OpenRouter请求体。"""
    body: dict[str, Any] = {
        "model": model.id,
        "messages": _openai_messages(context),
        "tools": _openai_tools(context),
        "reasoning": {"effort": "none"},
        "stream": True,
        "stream_options": {"include_usage": True},
        "parallel_tool_calls": False,
    }
    if options.temperature is not None:
        body["temperature"] = options.temperature
    if options.max_tokens is not None:
        body["max_tokens"] = options.max_tokens
    return body


def _context_tool_names(context: AgentContext) -> set[str]:
    """用于读取当前请求真正可用的工具名。"""
    return {
        str(tool_name)
        for tool in context.tools
        if (tool_name := getattr(tool, "name", None))
    }


def _openrouter_headers(options: SimpleStreamOptions) -> dict[str, str]:
    """用于处理OpenRouter请求头。"""
    api_key = options.api_key or settings.OPENROUTER_API_KEY
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://chat-resume.com",
        "X-Title": "Chat Resume AI Assistant",
    }


def _openrouter_host() -> str:
    """用于提取 OpenRouter base URL 的主机名，避免日志记录完整路径。"""
    parsed = urlparse(settings.OPENROUTER_API_BASE)
    return parsed.netloc or settings.OPENROUTER_API_BASE


def _elapsed_ms(started_at: float) -> float:
    """用于把 monotonic 起点转换成毫秒耗时。"""
    return round((monotonic() - started_at) * 1000, 2)


def _log_openrouter_stage(stage: str, *, started_at: float, **fields: Any) -> None:
    """用于记录 OpenRouter 流式请求的阶段性耗时。"""
    level = int(fields.pop("log_level", logging.INFO))
    _logger.log(
        level,
        "openrouter.stream.%s",
        stage,
        extra={
            "agent_trace": True,
            "stage": stage,
            "elapsed_ms": _elapsed_ms(started_at),
            "openrouter_host": _openrouter_host(),
            **fields,
        },
    )


def _first_event_timeout_seconds() -> float:
    """用于读取首条 SSE 事件超时配置。"""
    return max(float(settings.OPENROUTER_FIRST_EVENT_TIMEOUT_SECONDS), 0.001)


def _first_token_timeout_seconds() -> float:
    """用于读取首个模型文本或工具增量超时配置。"""
    return float(settings.OPENROUTER_FIRST_TOKEN_TIMEOUT_SECONDS)


def _remaining_timeout_seconds(*, started_at: float, timeout_seconds: float) -> float:
    """用于计算从请求开始计时的剩余超时时间。"""
    remaining = timeout_seconds - (monotonic() - started_at)
    return max(remaining, 0.001)


async def _next_openrouter_line(
    *,
    line_iter: Any,
    first_sse_seen: bool,
    first_delta_seen: bool,
    started_at: float,
) -> str:
    """用于读取下一行 SSE，并对首事件和首增量设置明确超时。"""
    timeout_seconds = _line_wait_timeout_seconds(
        started_at=started_at,
        first_sse_seen=first_sse_seen,
        first_delta_seen=first_delta_seen,
    )
    try:
        line = await asyncio.wait_for(line_iter.__anext__(), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        _raise_openrouter_stream_timeout(
            first_sse_seen=first_sse_seen,
            first_delta_seen=first_delta_seen,
            started_at=started_at,
        )
        raise exc
    return str(line)


def _line_wait_timeout_seconds(
    *,
    started_at: float,
    first_sse_seen: bool,
    first_delta_seen: bool,
) -> float | None:
    """用于给下一次 SSE 读取选择当前阶段的超时。"""
    if not first_sse_seen:
        return _remaining_timeout_seconds(
            started_at=started_at,
            timeout_seconds=_first_event_timeout_seconds(),
        )
    if not first_delta_seen:
        timeout_seconds = _first_token_timeout_seconds()
        if timeout_seconds <= 0:
            return None
        return _remaining_timeout_seconds(
            started_at=started_at,
            timeout_seconds=timeout_seconds,
        )
    return None


def _raise_openrouter_stream_timeout(
    *,
    first_sse_seen: bool,
    first_delta_seen: bool,
    started_at: float,
) -> None:
    """用于将阶段性超时转换成可读异常并写入日志。"""
    elapsed_ms = _elapsed_ms(started_at)
    if not first_sse_seen:
        timeout = _first_event_timeout_seconds()
        _logger.warning(
            "openrouter.stream.first_event_timeout",
            extra={
                "agent_trace": True,
                "elapsed_ms": elapsed_ms,
                "timeout_seconds": timeout,
            },
        )
        raise OpenRouterFirstEventTimeoutError(
            f"OpenRouter first SSE event timed out after {timeout:.1f}s"
        )
    if not first_delta_seen:
        timeout = _first_token_timeout_seconds()
        _logger.warning(
            "openrouter.stream.first_token_timeout",
            extra={
                "agent_trace": True,
                "elapsed_ms": elapsed_ms,
                "timeout_seconds": timeout,
            },
        )
        raise OpenRouterFirstTokenTimeoutError(
            f"OpenRouter first token timed out after {timeout:.1f}s"
        )


def _openai_messages(context: AgentContext) -> list[dict[str, Any]]:
    """用于处理OpenAI 兼容消息列表。"""
    messages: list[dict[str, Any]] = []
    if context.system_prompt:
        messages.append({"role": "system", "content": context.system_prompt})
    for message in context.messages:
        converted = _openai_message(message)
        if converted is not None:
            messages.append(converted)
    return messages


def _openai_message(message: Any) -> dict[str, Any] | None:
    """用于处理OpenAI 兼容消息。"""
    role = getattr(message, "role", "")
    if role == "user":
        return {"role": "user", "content": _text_content(message)}
    if role == "assistant":
        return _openai_assistant_message(message)
    if role == "toolResult":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "name": message.tool_name,
            "content": _text_content(message),
        }
    return None


def _openai_assistant_message(message: Any) -> dict[str, Any]:
    """用于处理OpenAI 兼容助手消息。"""
    tool_calls = []
    for block in getattr(message, "content", []):
        if isinstance(block, ToolCall):
            tool_calls.append(
                {
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(
                            block.arguments,
                            ensure_ascii=False,
                        ),
                    },
                }
            )
    content = _text_content(message)
    payload: dict[str, Any] = {"role": "assistant"}
    if content or not tool_calls:
        payload["content"] = content
    if tool_calls:
        payload["tool_calls"] = tool_calls
    return payload


def _text_content(message: Any) -> str:
    """用于处理文本content。"""
    parts: list[str] = []
    for block in getattr(message, "content", []):
        if isinstance(block, TextContent):
            parts.append(block.text)
    return "".join(parts)


def _openai_tools(context: AgentContext) -> list[dict[str, Any]]:
    """用于处理OpenAI 兼容工具列表。"""
    tools = []
    for tool in context.tools:
        parameters = _normalize_tool_schema(tool.parameters.model_dump())
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": parameters,
                },
            }
        )
    return tools


def _normalize_tool_schema(schema: Any) -> Any:
    """用于补齐 OpenAI 兼容 provider 需要的 JSON Schema type 字段。"""
    if isinstance(schema, list):
        return [_normalize_tool_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    normalized = {key: _normalize_tool_schema(value) for key, value in schema.items()}
    if "type" not in normalized and (schema_type := _infer_schema_type(normalized)):
        normalized["type"] = schema_type
    return normalized


def _infer_schema_type(schema: dict[str, Any]) -> str | None:
    """用于从 schema 结构或 enum 值推断缺失的 type。"""
    if isinstance(schema.get("properties"), dict):
        return "object"
    if "items" in schema:
        return "array"
    enum_values = schema.get("enum")
    if not isinstance(enum_values, list) or not enum_values:
        return None
    return _infer_enum_schema_type(enum_values)


def _infer_enum_schema_type(values: list[Any]) -> str | None:
    """用于从 enum 值类型推断 JSON Schema type。"""
    if all(isinstance(value, bool) for value in values):
        return "boolean"
    if all(isinstance(value, str) for value in values):
        return "string"
    if all(_is_json_number(value) for value in values):
        return "number"
    return None


def _is_json_number(value: Any) -> bool:
    """用于判断 enum 值是否应按 JSON number 处理。"""
    return isinstance(value, int | float) and not isinstance(value, bool)


async def _raise_for_openrouter_error(response: httpx.Response) -> None:
    """读取错误响应体并抛出携带状态码和 Retry-After 的 OpenRouterHTTPError。"""
    if response.status_code == 200:
        return
    retry_after_header = response.headers.get("Retry-After")
    retry_after: float | None = None
    if retry_after_header is not None:
        try:
            retry_after = float(retry_after_header)
        except ValueError:
            pass
    body = await response.aread()
    message = body.decode("utf-8", errors="replace")
    raise OpenRouterHTTPError(
        status_code=response.status_code,
        message=f"OpenRouter error {response.status_code}: {message}",
        retry_after=retry_after,
    )


def _decode_sse_line(line: str) -> dict[str, Any] | str | None:
    """用于处理decodesseline。"""
    if not line.startswith("data: "):
        return None
    data = line[6:].strip()
    if not data:
        return None
    if data == "[DONE]":
        return data
    return json.loads(data)


def _apply_openrouter_chunk(
    *,
    chunk: dict[str, Any],
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
    tool_buffers: dict[int, dict[str, Any]],
    allowed_tool_names: set[str],
    text_buffer: list[str],
    text_started: bool,
    text_index: int,
    started_at: float,
    model: Model,
) -> _ChunkApplication:
    """用于应用OpenRouterchunk。"""
    choice = _first_choice(chunk)
    if not choice:
        _apply_usage(chunk, partial)
        return _ChunkApplication(text_started=text_started)
    delta = choice.get("delta") or {}
    text_delta_chars = _text_delta_chars(delta)
    text_started = _apply_text_delta(
        delta=delta,
        partial=partial,
        queue=queue,
        text_buffer=text_buffer,
        text_started=text_started,
        text_index=text_index,
    )
    tool_names, tool_arg_delta_chars = _apply_tool_delta(delta, tool_buffers)
    _emit_early_tool_call_starts(
        tool_buffers=tool_buffers,
        allowed_tool_names=allowed_tool_names,
        partial=partial,
        queue=queue,
        started_at=started_at,
        model=model,
    )
    _apply_usage(chunk, partial)
    return _ChunkApplication(
        text_started=text_started,
        text_delta_chars=text_delta_chars,
        tool_names=tuple(tool_names),
        tool_arg_delta_chars=tool_arg_delta_chars,
    )


def _first_choice(chunk: dict[str, Any]) -> dict[str, Any] | None:
    """用于处理firstchoice。"""
    choices = chunk.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0]
        return choice if isinstance(choice, dict) else None
    return None


def _apply_text_delta(
    *,
    delta: dict[str, Any],
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
    text_buffer: list[str],
    text_started: bool,
    text_index: int,
) -> bool:
    """用于应用文本增量。"""
    content = delta.get("content")
    if not isinstance(content, str) or not content:
        return text_started
    if not text_started:
        partial.content.append(TextContent())
        queue.put_nowait(StreamTextStartEvent(content_index=text_index, partial=partial))
        text_started = True
    text_block = partial.content[text_index]
    if isinstance(text_block, TextContent):
        text_block.text += content
    text_buffer.append(content)
    queue.put_nowait(
        StreamTextDeltaEvent(
            content_index=text_index,
            delta=content,
            partial=partial,
        )
    )
    return text_started


def _text_delta_chars(delta: dict[str, Any]) -> int:
    """用于计算文本增量字符数。"""
    content = delta.get("content")
    return len(content) if isinstance(content, str) else 0


def _apply_tool_delta(
    delta: dict[str, Any],
    tool_buffers: dict[int, dict[str, Any]],
) -> tuple[list[str], int]:
    """用于应用工具增量。"""
    tool_calls = delta.get("tool_calls")
    if not isinstance(tool_calls, list):
        return [], 0
    tool_names: list[str] = []
    arg_delta_chars = 0
    for raw_call in tool_calls:
        if not isinstance(raw_call, dict):
            continue
        index = int(raw_call.get("index") or 0)
        buffer = tool_buffers.setdefault(index, {"id": "", "name": "", "args": ""})
        if isinstance(raw_call.get("id"), str) and not buffer["id"]:
            buffer["id"] = raw_call["id"]
        function = raw_call.get("function")
        if not isinstance(function, dict):
            continue
        if isinstance(function.get("name"), str) and not buffer["name"]:
            buffer["name"] = function["name"]
            if buffer["name"]:
                tool_names.append(str(buffer["name"]))
        if isinstance(function.get("arguments"), str):
            args_delta = function["arguments"]
            buffer["args"] += args_delta
            arg_delta_chars += len(args_delta)
    return tool_names, arg_delta_chars


def _emit_early_tool_call_starts(
    *,
    tool_buffers: dict[int, dict[str, Any]],
    allowed_tool_names: set[str],
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
    started_at: float,
    model: Model,
) -> None:
    """在工具名首次完整可识别时提前发送轻量 start 事件。"""
    for index in sorted(tool_buffers):
        raw_call = tool_buffers[index]
        if raw_call.get("early_start_emitted"):
            continue
        tool_name = str(raw_call.get("name") or "")
        call_id = str(raw_call.get("id") or "")
        if not tool_name or tool_name not in allowed_tool_names or not call_id:
            continue
        raw_call["early_start_emitted"] = True
        preview_partial = AssistantMessage(
            api=partial.api,
            provider=partial.provider,
            model=partial.model,
        )
        preview_partial.content.append(
            ToolCall(id=call_id, name=tool_name, arguments={})
        )
        _log_openrouter_stage(
            "tool_call_start_emitted_early",
            started_at=started_at,
            model=model.id,
            tool_index=index,
            tool_name=tool_name,
        )
        queue.put_nowait(
            StreamToolCallStartEvent(content_index=0, partial=preview_partial)
        )


def _emit_tool_calls(
    tool_buffers: dict[int, dict[str, Any]],
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
    *,
    started_at: float,
    model: Model,
) -> None:
    """用于发送工具calls。"""
    for index in sorted(tool_buffers):
        raw_call = tool_buffers[index]
        args = _parse_tool_arguments_with_log(
            raw_call.get("args"),
            index=index,
            tool_name=str(raw_call.get("name") or ""),
            started_at=started_at,
            model=model,
        )
        tool_call = ToolCall(
            id=raw_call.get("id") or f"tool_{index}",
            name=raw_call.get("name") or "",
            arguments=args,
        )
        content_index = len(partial.content)
        partial.content.append(tool_call)
        _log_openrouter_stage(
            "tool_call_emitted",
            started_at=started_at,
            model=model.id,
            tool_index=index,
            tool_name=tool_call.name,
            args_key_count=len(tool_call.arguments),
        )
        queue.put_nowait(
            StreamToolCallStartEvent(content_index=content_index, partial=partial)
        )
        queue.put_nowait(
            StreamToolCallEndEvent(
                content_index=content_index,
                tool_call=tool_call,
                partial=partial,
            )
        )


def _parse_tool_arguments(raw: Any) -> dict[str, Any]:
    """用于解析工具arguments。"""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    parsed = json.loads(raw, strict=False)
    return parsed if isinstance(parsed, dict) else {}


def _parse_tool_arguments_with_log(
    raw: Any,
    *,
    index: int,
    tool_name: str,
    started_at: float,
    model: Model,
) -> dict[str, Any]:
    """用于解析工具参数，并在解析失败时记录可定位的结构化信息。"""
    try:
        return _parse_tool_arguments(raw)
    except json.JSONDecodeError as exc:
        _log_openrouter_stage(
            "tool_args_parse_error",
            started_at=started_at,
            model=model.id,
            tool_index=index,
            tool_name=tool_name,
            args_chars=len(raw) if isinstance(raw, str) else 0,
            json_error=str(exc),
        )
        return {
            _TOOL_ARGUMENTS_PARSE_ERROR_KEY: {
                "type": "invalid_arguments_json",
                "message": str(exc),
                "raw_chars": len(raw) if isinstance(raw, str) else 0,
            }
        }


def _tool_buffer_summary(tool_buffers: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """用于生成工具流缓冲区的安全摘要，不记录完整参数内容。"""
    summary: list[dict[str, Any]] = []
    for index in sorted(tool_buffers):
        raw_call = tool_buffers[index]
        raw_args = raw_call.get("args")
        args_text = raw_args if isinstance(raw_args, str) else ""
        summary.append(
            {
                "index": index,
                "id_chars": len(str(raw_call.get("id") or "")),
                "name": str(raw_call.get("name") or ""),
                "args_chars": len(args_text),
                "args_json_status": _tool_args_json_status(args_text),
            }
        )
    return summary


def _tool_args_json_status(raw: str) -> str:
    """用于判断工具参数是否为空、完整 JSON 或仍是未闭合片段。"""
    if not raw.strip():
        return "empty"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return "invalid"
    return "object" if isinstance(parsed, dict) else "non_object"


def _apply_usage(chunk: dict[str, Any], partial: AssistantMessage) -> None:
    """用于应用用量。"""
    usage = chunk.get("usage")
    if not isinstance(usage, dict):
        return
    partial.usage = Usage(
        input=int(usage.get("prompt_tokens") or 0),
        output=int(usage.get("completion_tokens") or 0),
        total_tokens=int(usage.get("total_tokens") or 0),
    )


def _finish_reason(chunk: dict[str, Any], current: str) -> str:
    """用于完成原因。"""
    choice = _first_choice(chunk)
    if not choice:
        return current
    reason = choice.get("finish_reason")
    return reason if isinstance(reason, str) and reason else current


def _stop_reason(finish_reason: str) -> StopReason:
    """用于处理stop原因。"""
    if finish_reason == "length":
        return "length"
    return "stop"


def _cancelled(options: SimpleStreamOptions) -> bool:
    """用于处理取消状态。"""
    return bool(options.cancel_event and options.cancel_event.is_set())


__all__ = ["stream_openrouter", "OpenRouterHTTPError"]
