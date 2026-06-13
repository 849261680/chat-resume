"""用于覆盖后端日志输出目标配置。"""

from __future__ import annotations

import logging
import re

from app.infra import logging_setup
from app.infra.config import settings

_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def test_text_logging_colors_terminal_but_not_file(tmp_path, monkeypatch, capsys):
    """用于验证终端彩色输出而日志文件保持纯文本。"""
    log_file = tmp_path / "backend.log"
    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(settings, "BACKEND_LOG_FILE", str(log_file))

    logging_setup.configure_logging()
    logging.getLogger("app.main").info("app.ready")

    terminal_output = capsys.readouterr().err
    file_output = log_file.read_text(encoding="utf-8")

    assert _ANSI_PATTERN.search(terminal_output)
    assert "app.ready" in terminal_output
    assert "app.ready" in file_output
    assert not _ANSI_PATTERN.search(file_output)


def test_text_request_logs_include_client_request_id(tmp_path, monkeypatch):
    """用于验证本地文本日志可以按前端请求 ID grep。"""
    log_file = tmp_path / "backend.log"
    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(settings, "BACKEND_LOG_FILE", str(log_file))

    logging_setup.configure_logging()
    logging.getLogger("app.main").info(
        "request.finished",
        extra={
            "http_method": "POST",
            "http_path": "/api/ai/chat/stream",
            "http_status": 500,
            "request_ms": 1200.0,
            "client_request_id": "ai_client_visible_123",
        },
    )

    file_output = log_file.read_text(encoding="utf-8")

    assert "request.finished POST /api/ai/chat/stream 500 1200.0ms" in file_output
    assert "client=ai_client_visible_123" in file_output


def test_text_sse_tool_event_log_includes_core_fields(tmp_path, monkeypatch):
    """用于验证 SSE 工具事件日志默认可读。"""
    log_file = tmp_path / "backend.log"
    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(settings, "BACKEND_LOG_FILE", str(log_file))

    logging_setup.configure_logging()
    logging.getLogger("app.entrypoints.http.resume_agent").info(
        "resume_agent.sse.tool_event.sent",
        extra={
            "event_type": "tool_call",
            "tool_name": "update_bullet",
            "call_id": "call_123456789",
            "client_request_id": "ai_client_visible_123",
            "has_result": False,
        },
    )

    file_output = log_file.read_text(encoding="utf-8")

    assert "sse.tool_event sent" in file_output
    assert "event=tool_call" in file_output
    assert "tool=update_bullet" in file_output
    assert "call=call_123456789" in file_output
    assert "client=ai_clien" in file_output
    assert "client=ai_client_visible_123" not in file_output


def test_text_run_summary_log_includes_observability_fields(tmp_path, monkeypatch):
    """用于验证 run summary 文本日志包含本地验收指标。"""
    log_file = tmp_path / "backend.log"
    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(settings, "BACKEND_LOG_FILE", str(log_file))

    logging_setup.configure_logging()
    logging.getLogger("app.agents.resume.runtime").info(
        "resume_agent.run.summary",
        extra={
            "agent_trace": True,
            "run_id": "345c127b099999999",
            "client_request_id": "ai_client_visible_123",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "prompt_chars": 4670,
            "message_count": 2,
            "tool_count": 16,
            "first_token_ms": 120.5,
            "llm_total_ms": 820.25,
            "approval_wait_ms": 300.0,
            "total_ms": 1300.75,
            "tool_requested": 1,
            "tool_executed": 1,
            "tool_confirmed": 0,
            "tool_rejected": 1,
            "guardrail_rejected": 0,
            "final_status": "completed",
            "error": "-",
        },
    )

    file_output = log_file.read_text(encoding="utf-8")

    assert "run.summary client=ai_clien run=345c127b status=completed" in file_output
    assert "provider=deepseek model=deepseek-v4-pro prompt=4670 msgs=2 tools=16" in file_output
    assert "first=120.5ms llm=820.25ms approve=300.0ms total=1300.75ms" in file_output
    assert "requested=1 executed=1 confirmed=0 rejected=1 guardrail=0 error=-" in file_output


def test_text_openrouter_stream_log_uses_compact_mainline(tmp_path, monkeypatch):
    """用于验证 OpenRouter text 日志只展示人读主线。"""
    log_file = tmp_path / "backend.log"
    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(settings, "BACKEND_LOG_FILE", str(log_file))

    logging_setup.configure_logging()
    logging.getLogger("app.runtime.pi_agent_openrouter").info(
        "openrouter.stream.tool_args_complete",
        extra={
            "agent_trace": True,
            "client_request_id": "ai_client_visible_123",
            "model": "moonshotai/kimi-k2.6",
            "elapsed_ms": 8215.54,
            "finish_reason": "tool_calls",
            "openrouter_host": "openrouter.ai",
            "stage": "tool_args_complete",
            "tool_buffers": [
                {
                    "args_chars": 137,
                    "args_json_status": "object",
                    "id_chars": 25,
                    "index": 0,
                    "name": "remove_bullet",
                }
            ],
            "tool_count": 1,
            "usage_output": 94,
        },
    )

    file_output = log_file.read_text(encoding="utf-8")

    assert (
        "openrouter tool_args client=ai_clien tool=remove_bullet "
        "args=137 json=object tools=1 ms=8215.54ms"
    ) in file_output
    assert "tool_buffers=" not in file_output
    assert "openrouter_host=" not in file_output
    assert "stage=tool_args_complete" not in file_output


def test_text_agent_tool_trace_uses_compact_mainline(tmp_path, monkeypatch):
    """用于验证工具 trace text 日志不再展开所有 extra。"""
    log_file = tmp_path / "backend.log"
    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(settings, "BACKEND_LOG_FILE", str(log_file))

    logging_setup.configure_logging()
    logging.getLogger("app.agents.resume.runtime").info(
        "agent.trace.tool.executed",
        extra={
            "agent_trace": True,
            "agent_name": "resume_agent",
            "client_request_id": "ai_client_visible_123",
            "run_id": "345c127b099999999",
            "call_id": "functions.remove_bullet:1",
            "tool_name": "remove_bullet",
            "tool_display_name": "删除要点",
            "result_success": True,
            "display_message": "项目经历 / Chat Resume - AI驱动的求职辅导平台 删除要点 改前：基于SSE实现...",
            "result_summary": {"diff_item_count": 1, "success": True},
            "latency_ms": 1256.71,
        },
    )

    file_output = log_file.read_text(encoding="utf-8")

    assert "tool.executed client=ai_clien run=345c127b tool=remove_bullet" in file_output
    assert "ok=true ms=1256.71ms diffs=1" in file_output
    assert "agent=resume_agent" not in file_output
    assert "result=" not in file_output
