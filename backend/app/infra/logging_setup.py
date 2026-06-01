"""用于配置应用日志格式、脱敏和上下文注入。"""

from __future__ import annotations

import json
import logging
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger as loguru_logger

from app.infra.config import settings
from app.infra.request_context import get_log_context

_SENSITIVE_KEYS = re.compile(
    r"(authorization|access[_-]?key|api[_-]?key|token|secret|password|cookie)",
    re.IGNORECASE,
)
_STANDARD_LOG_RECORD_KEYS = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
)
_NOISY_LOGGERS = (
    "httpcore",
    "httpx",
    "openai",
    "multipart",
    "passlib",
    "pdfminer",
    "urllib3",
    "websockets",
)
_INTERCEPTED_LOGGERS = (
    "",
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
)
_TRACE_VALUE_LIMIT = 48
_TRACE_KEY_LABELS = {
    "agent_name": "agent",
    "call_id": "call",
    "client_request_id": "client",
    "confirmed": "confirmed",
    "diff_item_count": "diffs",
    "diff_summary": "diff",
    "display_message": "msg",
    "latency_ms": "ms",
    "requires_confirmation": "confirm",
    "result_success": "ok",
    "result_summary": "result",
    "run_id": "run",
    "tool_display_name": "display",
    "tool_input": "input",
    "tool_name": "tool",
}
_TEXT_LOG_FORMAT = (
    "{time:HH:mm:ss} {level} {extra[logger_label]} "
    "{extra[message_label]}{extra[agent_trace_suffix]}"
    "{exception}"
)
_COLOR_TEXT_LOG_FORMAT = (
    "<green>{time:HH:mm:ss}</green> <level>{level}</level> "
    "<cyan>{extra[logger_label]}</cyan> "
    "<level>{extra[message_label]}</level>{extra[agent_trace_suffix]}"
    "{exception}"
)


def _sanitize(value: Any) -> Any:
    """用于处理sanitize。"""
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]" if _SENSITIVE_KEYS.search(str(key)) else _sanitize(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value[:20]]
    if isinstance(value, str):
        return value if len(value) <= 500 else f"{value[:500]}..."
    return value


def _context_defaults() -> dict[str, str]:
    """用于处理上下文默认值。"""
    context = get_log_context()
    return {
        "request_id": context["request_id"] or "-",
        "session_id": context["session_id"] or "-",
        "tool_call_id": context["tool_call_id"] or "-",
        "client_request_id": context["client_request_id"] or "-",
    }


class JsonFormatter(logging.Formatter):
    def _sanitize(self, value: Any) -> Any:
        """用于处理sanitize。"""
        return _sanitize(value)

    def format(self, record: logging.LogRecord) -> str:
        """用于处理format。"""
        context = _context_defaults()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self._sanitize(record.getMessage()),
            "request_id": getattr(record, "request_id", context["request_id"]),
            "session_id": getattr(record, "session_id", context["session_id"]),
            "tool_call_id": getattr(
                record,
                "tool_call_id",
                context["tool_call_id"],
            ),
            "client_request_id": getattr(
                record,
                "client_request_id",
                context["client_request_id"],
            ),
        }
        for key, value in record.__dict__.items():
            if (
                key.startswith("_")
                or key in payload
                or key in _STANDARD_LOG_RECORD_KEYS
            ):
                continue
            payload[key] = (
                "[REDACTED]"
                if _SENSITIVE_KEYS.search(str(key))
                else self._sanitize(value)
            )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class InterceptHandler(logging.Handler):
    """Forward standard-library logging records into Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """用于发送当前数据。"""
        try:
            level: str | int = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        depth = 2
        frame = logging.currentframe()
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        extra = {
            key: value
            for key, value in record.__dict__.items()
            if not key.startswith("_") and key not in _STANDARD_LOG_RECORD_KEYS
        }
        extra["logger_name"] = record.name
        for key, value in _context_defaults().items():
            extra.setdefault(key, value)

        loguru_logger.bind(**extra).opt(
            depth=depth,
            exception=record.exc_info,
        ).log(level, record.getMessage())


def _patch_loguru_record(record: Any) -> None:
    """用于处理patchlogururecord。"""
    extra = record["extra"]
    extra.setdefault("logger_name", record["name"])
    for key, value in _context_defaults().items():
        extra.setdefault(key, value)
    extra["logger_label"] = _logger_label(str(extra["logger_name"]))
    extra["request_id_short"] = _short_identifier(extra["request_id"])
    extra["session_id_short"] = _short_identifier(extra["session_id"])
    extra["tool_call_id_short"] = _short_identifier(extra["tool_call_id"])
    extra["message_label"] = _message_label(record["message"], extra)
    extra["agent_trace_suffix"] = _agent_trace_suffix(extra)


def _logger_label(logger_name: str) -> str:
    """用于处理日志器标签。"""
    if logger_name == "app.agents.resume.runtime":
        return "piagent"
    if logger_name.startswith("app."):
        parts = logger_name.split(".")
        return ".".join(parts[-2:])
    return logger_name


def _short_identifier(value: Any, limit: int = 6) -> str:
    """用于处理short标识。"""
    text = str(value or "-")
    if text == "-" or len(text) <= limit:
        return text
    return text[:limit]


def _message_label(message: str, extra: dict[str, Any]) -> str:
    """用于处理消息标签。"""
    if message.startswith("openrouter.stream."):
        return _openrouter_message_label(message, extra)
    if message == "resume_agent.run.summary":
        return _run_summary_message_label(extra)
    if extra.get("agent_trace") and message.startswith("agent.trace."):
        compact_label = _agent_trace_message_label(message, extra)
        if compact_label:
            return compact_label
        return message.removeprefix("agent.")
    if message == "request.finished":
        method = extra.get("http_method", "-")
        path = extra.get("http_path", "-")
        status = extra.get("http_status", "-")
        request_ms = extra.get("request_ms", "-")
        client_request_id = extra.get("client_request_id", "-")
        return (
            f"request.finished {method} {path} {status} {request_ms}ms "
            f"client={client_request_id}"
        )
    if message == "request.failed":
        client_request_id = extra.get("client_request_id", "-")
        return f"request.failed client={client_request_id}"
    if message == "resume_agent.sse.tool_event.sent":
        event_type = extra.get("event_type", "-")
        tool_name = extra.get("tool_name") or extra.get("tool_display_name") or "-"
        call_id = extra.get("call_id", "-")
        client_request_id = _compact_client(extra)
        has_result = extra.get("has_result", "-")
        return _compact_label(
            "sse.tool_event sent",
            f"event={event_type}",
            f"tool={tool_name}",
            f"call={call_id}",
            f"client={client_request_id}",
            f"result={has_result}",
        )
    return message


def _openrouter_message_label(message: str, extra: dict[str, Any]) -> str:
    """用于把 OpenRouter 流式日志压缩成人读主线。"""
    extra["_compact_text"] = True
    stage = message.removeprefix("openrouter.stream.")
    client = _compact_client(extra)
    elapsed = _compact_ms(extra.get("elapsed_ms"))
    if stage == "request_started":
        return _compact_label(
            "openrouter request",
            f"client={client}",
            f"model={extra.get('model', '-')}",
            f"msgs={extra.get('message_count', '-')}",
            f"tools={extra.get('tool_count', '-')}",
            elapsed,
        )
    if stage == "headers_received":
        return _compact_label(
            "openrouter headers",
            f"client={client}",
            f"status={extra.get('status_code', '-')}",
            elapsed,
        )
    if stage in {"first_sse_line", "first_text_delta", "first_tool_delta"}:
        return _openrouter_first_event_label(stage, client, elapsed, extra)
    if stage == "pre_delta_line":
        return _openrouter_pre_delta_label(client, elapsed, extra)
    if stage == "tool_call_start_emitted_early":
        return _compact_label(
            "openrouter tool_start",
            f"client={client}",
            f"tool={extra.get('tool', '-')}",
            f"index={extra.get('tool_index', '-')}",
            elapsed,
        )
    if stage == "finish_reason":
        return _compact_label(
            "openrouter finish",
            f"client={client}",
            f"reason={extra.get('finish_reason', '-')}",
            f"tools={extra.get('tool_count', '-')}",
            elapsed,
        )
    if stage == "tool_args_complete":
        tool = _first_tool_buffer(extra.get("tool_buffers"))
        return _compact_label(
            "openrouter tool_args",
            f"client={client}",
            f"tool={tool.get('name', '-')}",
            f"args={tool.get('args_chars', '-')}",
            f"json={tool.get('args_json_status', '-')}",
            f"tools={extra.get('tool_count', '-')}",
            elapsed,
        )
    if stage == "tool_call_emitted":
        return _compact_label(
            "openrouter tool_emit",
            f"client={client}",
            f"tool={extra.get('tool', '-')}",
            f"keys={extra.get('args_key_count', '-')}",
            elapsed,
        )
    if stage == "done":
        return _compact_label(
            "openrouter done",
            f"client={client}",
            f"stop={extra.get('stop_reason', '-')}",
            f"finish={extra.get('finish_reason', '-')}",
            f"text={extra.get('text_chars', '-')}",
            f"tools={extra.get('tool_call_count', '-')}",
            elapsed,
        )
    if stage == "error":
        return _compact_label(
            "openrouter error",
            f"client={client}",
            f"type={extra.get('error_type', '-')}",
            f"error={_compact_string(extra.get('error'))}",
            elapsed,
        )
    return _compact_label(f"openrouter {stage}", f"client={client}", elapsed)


def _openrouter_pre_delta_label(
    client: str,
    elapsed: str | None,
    extra: dict[str, Any],
) -> str:
    """用于压缩首有效 delta 前的 OpenRouter 行摘要。"""
    delta_keys = extra.get("delta_keys")
    delta_label = ",".join(delta_keys) if isinstance(delta_keys, list) else "-"
    if not delta_label:
        delta_label = "-"
    return _compact_label(
        "openrouter pre_delta",
        f"client={client}",
        f"n={extra.get('line_count', '-')}",
        f"kind={extra.get('line_kind', '-')}",
        _compact_ms(extra.get("wait_ms"), label="wait"),
        f"delta={delta_label}",
        f"text={extra.get('content_chars', '-')}",
        f"tools={extra.get('tool_call_count', '-')}",
        f"args={extra.get('tool_arg_delta_chars', '-')}",
        f"finish={extra.get('finish_reason', '-')}",
        elapsed,
    )


def _openrouter_first_event_label(
    stage: str,
    client: str,
    elapsed: str | None,
    extra: dict[str, Any],
) -> str:
    """用于压缩 OpenRouter 首事件日志。"""
    if stage == "first_sse_line":
        return _compact_label("openrouter first_sse", f"client={client}", elapsed)
    if stage == "first_text_delta":
        return _compact_label(
            "openrouter first_text",
            f"client={client}",
            f"chars={extra.get('text_delta_chars', '-')}",
            elapsed,
        )
    tool_names = _compact_list(extra.get("tool_names"))
    return _compact_label("openrouter first_tool", f"client={client}", tool_names, elapsed)


def _agent_trace_message_label(message: str, extra: dict[str, Any]) -> str | None:
    """用于把 Agent trace 日志压缩成人读主线。"""
    trace_name = message.removeprefix("agent.trace.")
    extra["_compact_text"] = True
    client = _compact_client(extra)
    run_id = _compact_id(extra.get("run_id"))
    elapsed = _compact_ms(extra.get("latency_ms"))
    if trace_name == "run.started":
        return _compact_label(
            "trace.run started",
            f"client={client}",
            f"run={run_id}",
            f"mode={extra.get('mode', '-')}",
            f"history={extra.get('history_count', '-')}",
            _tool_names_label(extra.get("tool_names")),
            f"user={_compact_string(extra.get('user_message_preview'))}",
        )
    if trace_name == "prompt.rendered":
        return _compact_label(
            "trace.prompt rendered",
            f"client={client}",
            f"run={run_id}",
            f"chars={extra.get('prompt_chars', '-')}",
        )
    if trace_name == "llm.request":
        return _compact_label(
            "llm.request",
            f"client={client}",
            f"run={run_id}",
            f"model={extra.get('model', '-')}",
            f"msgs={extra.get('message_count', '-')}",
            f"tools={extra.get('tool_count', '-')}",
            f"prompt={extra.get('prompt_chars', '-')}",
        )
    if trace_name == "llm.response":
        return _compact_label(
            "llm.response",
            f"client={client}",
            f"run={run_id}",
            elapsed,
            _compact_ms(extra.get("first_token_latency_ms"), label="first"),
            _compact_ms(extra.get("confirmation_wait_ms"), label="wait"),
            f"chars={extra.get('response_chars', '-')}",
            f"preview={_compact_string(extra.get('response_preview'))}",
        )
    if trace_name == "run.completed":
        return _compact_label(
            "trace.run completed",
            f"client={client}",
            f"run={run_id}",
            elapsed,
        )
    if trace_name.startswith("tool."):
        return _tool_trace_message_label(trace_name, client, run_id, elapsed, extra)
    if trace_name.startswith("reasoning."):
        return _reasoning_trace_message_label(trace_name, client, run_id, extra)
    if trace_name == "run.max_iterations_reached":
        return _compact_label(
            "trace.run max_iterations",
            f"client={client}",
            f"run={run_id}",
            f"reason={extra.get('reason', '-')}",
        )
    return None


def _tool_trace_message_label(
    trace_name: str,
    client: str,
    run_id: str,
    elapsed: str | None,
    extra: dict[str, Any],
) -> str:
    """用于压缩工具 trace 日志。"""
    if trace_name == "tool.requested":
        return _compact_label(
            "tool.requested",
            f"client={client}",
            f"run={run_id}",
            f"tool={extra.get('tool_name', '-')}",
            f"call={_compact_id(extra.get('call_id'))}",
            f"confirm={_compact_bool(extra.get('requires_confirmation'))}",
            _tool_input_label(extra.get("tool_input")),
        )
    if trace_name in {"tool.preview", "tool.preview_failed"}:
        label = "tool.preview_failed" if trace_name.endswith("failed") else "tool.preview"
        return _compact_label(
            label,
            f"client={client}",
            f"run={run_id}",
            f"tool={extra.get('tool_name', '-')}",
            f"ok={_compact_bool(extra.get('result_success'))}",
            f"diffs={extra.get('diff_item_count', '-')}",
            f"diff={_compact_string(extra.get('diff_summary'))}",
        )
    if trace_name == "tool.confirmation":
        return _compact_label(
            "tool.confirmation",
            f"client={client}",
            f"run={run_id}",
            f"tool={extra.get('tool_name', '-')}",
            f"confirmed={_compact_bool(extra.get('confirmed'))}",
            _compact_ms(extra.get("confirmation_wait_ms"), label="wait"),
        )
    if trace_name == "tool.executed":
        result = extra.get("result_summary")
        diff_count = result.get("diff_item_count", "-") if isinstance(result, dict) else "-"
        return _compact_label(
            "tool.executed",
            f"client={client}",
            f"run={run_id}",
            f"tool={extra.get('tool_name', '-')}",
            f"ok={_compact_bool(extra.get('result_success'))}",
            elapsed,
            f"diffs={diff_count}",
            f"msg={_compact_string(extra.get('display_message'))}",
        )
    if trace_name == "tool.rejected":
        return _compact_label(
            "tool.rejected",
            f"client={client}",
            f"run={run_id}",
            f"tool={extra.get('tool_name', '-')}",
            elapsed,
        )
    return _compact_label(trace_name, f"client={client}", f"run={run_id}", elapsed)


def _reasoning_trace_message_label(
    trace_name: str,
    client: str,
    run_id: str,
    extra: dict[str, Any],
) -> str:
    """用于压缩 reasoning trace 日志。"""
    if trace_name == "reasoning.tool_call_detected":
        return _compact_label(
            "reasoning.tool_call",
            f"client={client}",
            f"run={run_id}",
            _tool_names_label(extra.get("tool_names")),
            f"count={extra.get('tool_call_count', '-')}",
        )
    if trace_name == "reasoning.unexpected_tool_call":
        return _compact_label(
            "reasoning.unexpected_tool",
            f"client={client}",
            f"run={run_id}",
            f"tool={extra.get('tool_name', '-')}",
            f"reason={extra.get('reason', '-')}",
        )
    if trace_name == "reasoning.extra_tool_calls_ignored":
        return _compact_label(
            "reasoning.extra_tools_ignored",
            f"client={client}",
            f"run={run_id}",
            f"tool={extra.get('tool_name', '-')}",
            f"count={extra.get('tool_call_count', '-')}",
        )
    return _compact_label(trace_name, f"client={client}", f"run={run_id}")


def _run_summary_message_label(extra: dict[str, Any]) -> str:
    """用于压缩单次 run 摘要日志。"""
    extra["_compact_text"] = True
    return _compact_label(
        "run.summary",
        f"client={_compact_client(extra)}",
        f"run={_compact_id(extra.get('run_id'))}",
        f"ok={_compact_bool(extra.get('success'))}",
        f"tools={extra.get('tool_call_count', '-')}",
        _compact_ms(extra.get("confirmation_wait_ms"), label="wait"),
        _compact_ms(extra.get("elapsed_ms"), label="total"),
        f"error={extra.get('error_type', '-')}",
    )


def _compact_label(prefix: str, *parts: str | None) -> str:
    """用于拼接紧凑 text 日志片段。"""
    return " ".join([prefix, *(part for part in parts if part)])


def _compact_client(extra: dict[str, Any]) -> str:
    """用于返回短 client_request_id。"""
    return _short_identifier(extra.get("client_request_id", "-"), limit=8)


def _compact_id(value: Any) -> str:
    """用于返回短业务标识。"""
    return _short_identifier(value, limit=8)


def _compact_bool(value: Any) -> str:
    """用于输出紧凑布尔值。"""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value if value is not None else "-")


def _compact_ms(value: Any, *, label: str = "ms") -> str | None:
    """用于格式化毫秒耗时字段。"""
    if value in {None, "-"}:
        return None
    return f"{label}={value}ms"


def _compact_string(value: Any, *, limit: int = 48) -> str:
    """用于输出短字符串并保留空格文本的引号。"""
    if value in {None, ""}:
        return "-"
    text = " ".join(str(value).split())
    if len(text) > limit:
        text = f"{text[:limit]}..."
    if re.fullmatch(r"[\w.\-:/]+", text):
        return text
    return json.dumps(text, ensure_ascii=False, default=str)


def _compact_list(value: Any) -> str:
    """用于输出短列表。"""
    if not isinstance(value, list):
        return "items=-"
    names = ",".join(str(item) for item in value[:3])
    suffix = ",..." if len(value) > 3 else ""
    return f"items={names}{suffix}"


def _tool_names_label(value: Any) -> str:
    """用于输出工具名列表。"""
    if not isinstance(value, list):
        return "tools=-"
    names = ",".join(str(item) for item in value[:5])
    suffix = ",..." if len(value) > 5 else ""
    return f"tools={names}{suffix}"


def _first_tool_buffer(value: Any) -> dict[str, Any]:
    """用于读取第一个工具参数摘要。"""
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}


def _tool_input_label(value: Any) -> str:
    """用于输出紧凑工具入参摘要。"""
    if not isinstance(value, dict):
        return f"input={_compact_string(value)}"
    label_map = {
        "section": "section",
        "item_id": "item",
        "bullet_id": "bullet",
        "text_chars": "text",
        "text_preview": "preview",
        "reason": "reason",
    }
    parts = [
        f"{label_map[key]}={_compact_string(item)}"
        for key, item in value.items()
        if key in label_map
    ]
    return f"input={{{' '.join(parts)}}}" if parts else "input={}"


def _agent_trace_suffix(extra: dict[str, Any]) -> str:
    """用于处理agent追踪后缀。"""
    if not extra.get("agent_trace"):
        return ""
    if extra.get("_compact_text"):
        return ""
    trace_fields = {
        key: value
        for key, value in extra.items()
        if key
        not in {
            "agent_trace",
            "agent_trace_suffix",
            "logger_name",
            "logger_label",
            "message_label",
            "request_id",
            "request_id_short",
            "session_id",
            "session_id_short",
            "tool_call_id",
            "tool_call_id_short",
            "_compact_text",
        }
    }
    if not trace_fields:
        return ""
    ordered_keys = [
        "client_request_id",
        "run_id",
        "agent_name",
        "mode",
        "model",
        "tool_name",
        "tool_display_name",
        "call_id",
        "confirmed",
        "requires_confirmation",
        "result_success",
        "reason",
        "chunk_index",
        "chunk_count",
        "latency_ms",
    ]
    parts: list[str] = []
    for key in ordered_keys:
        if key in trace_fields:
            parts.append(_format_trace_pair(key, trace_fields.pop(key)))
    for key in sorted(trace_fields):
        parts.append(_format_trace_pair(key, trace_fields[key]))
    return " | " + " ".join(parts)


def _format_trace_pair(key: str, value: Any) -> str:
    """用于处理format追踪键值对。"""
    label = _TRACE_KEY_LABELS.get(key, key)
    return f"{label}={_format_trace_value(key, value)}"


def _format_trace_value(key: str, value: Any) -> str:
    """用于处理format追踪值。"""
    sanitized = _compact_trace_value(_sanitize(value))
    if key.endswith("_id") and isinstance(sanitized, str):
        sanitized = _short_identifier(sanitized, limit=8)
    if isinstance(sanitized, str):
        if re.fullmatch(r"[\w.\-:/]+", sanitized):
            return sanitized
        return json.dumps(sanitized, ensure_ascii=False, default=str)
    if isinstance(sanitized, bool):
        return str(sanitized).lower()
    if isinstance(sanitized, (int, float)) or sanitized is None:
        return json.dumps(sanitized, ensure_ascii=False, default=str)
    return json.dumps(
        sanitized,
        ensure_ascii=False,
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    )


def _compact_trace_value(value: Any) -> Any:
    """用于处理压缩结果追踪值。"""
    if isinstance(value, str):
        normalized = " ".join(value.split())
        if len(normalized) <= _TRACE_VALUE_LIMIT:
            return normalized
        return f"{normalized[:_TRACE_VALUE_LIMIT]}..."
    if isinstance(value, dict):
        return {
            str(key): _compact_trace_value(item)
            for key, item in list(value.items())[:8]
        }
    if isinstance(value, list):
        return [_compact_trace_value(item) for item in value[:5]]
    return value


def _json_sink(message: Any) -> None:
    """用于处理JSON输出端。"""
    record = message.record
    extra = record["extra"]
    payload: dict[str, Any] = {
        "timestamp": record["time"].astimezone(timezone.utc).isoformat(),
        "level": record["level"].name,
        "logger": extra.get("logger_name", record["name"]),
        "message": _sanitize(record["message"]),
        "request_id": extra.get("request_id", "-"),
        "session_id": extra.get("session_id", "-"),
        "tool_call_id": extra.get("tool_call_id", "-"),
        "client_request_id": extra.get("client_request_id", "-"),
    }
    for key, value in extra.items():
        if key in payload or key.startswith("_"):
            continue
        payload[key] = "[REDACTED]" if _SENSITIVE_KEYS.search(str(key)) else _sanitize(
            value
        )

    exception = record["exception"]
    if exception:
        payload["exception"] = "".join(
            traceback.format_exception(
                exception.type,
                exception.value,
                exception.traceback,
            )
        )

    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stderr.flush()


def _ensure_log_parent(log_file: str) -> str:
    """用于确保日志文件所在目录存在。"""
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def configure_logging() -> None:
    """用于配置日志。"""
    log_level_name = settings.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_file = _ensure_log_parent(settings.BACKEND_LOG_FILE)

    loguru_logger.remove()
    loguru_logger.configure(patcher=_patch_loguru_record)
    if settings.LOG_FORMAT.strip().lower() == "json":
        loguru_logger.add(
            _json_sink,
            level=log_level_name,
            backtrace=False,
            diagnose=False,
        )
        loguru_logger.add(
            log_file,
            level=log_level_name,
            format="{message}",
            backtrace=False,
            diagnose=False,
            colorize=False,
        )
    else:
        loguru_logger.add(
            sys.stderr,
            level=log_level_name,
            format=_COLOR_TEXT_LOG_FORMAT,
            backtrace=False,
            diagnose=False,
            colorize=True,
        )
        loguru_logger.add(
            log_file,
            level=log_level_name,
            format=_TEXT_LOG_FORMAT,
            backtrace=False,
            diagnose=False,
            colorize=False,
        )

    intercept_handler = InterceptHandler()
    for logger_name in _INTERCEPTED_LOGGERS:
        intercepted_logger = logging.getLogger(logger_name)
        intercepted_logger.handlers.clear()
        intercepted_logger.setLevel(
            logging.WARNING if logger_name.startswith("uvicorn") else log_level
        )
        intercepted_logger.addHandler(intercept_handler)
        intercepted_logger.propagate = False

    for logger_name in _NOISY_LOGGERS:
        library_logger = logging.getLogger(logger_name)
        library_logger.handlers.clear()
        library_logger.setLevel(logging.WARNING)
        library_logger.propagate = True
