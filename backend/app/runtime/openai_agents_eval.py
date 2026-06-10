"""用于在 eval 运行期间向 OpenAI Agents SDK 传递 trace 配置。"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class OpenAIAgentsTraceConfig:
    """用于描述一次 OpenAI Agents SDK eval run 的 trace 元数据。"""

    workflow_name: str
    trace_id: str
    group_id: str
    metadata: dict[str, Any]
    trace_include_sensitive_data: bool = False


_CURRENT_TRACE_CONFIG: ContextVar[OpenAIAgentsTraceConfig | None] = ContextVar(
    "chat_resume_openai_agents_trace_config",
    default=None,
)


def current_openai_agents_trace_config() -> OpenAIAgentsTraceConfig | None:
    """用于读取当前异步上下文里的 OpenAI Agents SDK trace 配置。"""
    return _CURRENT_TRACE_CONFIG.get()


@contextmanager
def use_openai_agents_trace_config(
    config: OpenAIAgentsTraceConfig | None,
) -> Iterator[None]:
    """用于在一段 eval 调用内临时启用 SDK trace 配置。"""
    token = _CURRENT_TRACE_CONFIG.set(config)
    try:
        yield
    finally:
        _CURRENT_TRACE_CONFIG.reset(token)


__all__ = [
    "OpenAIAgentsTraceConfig",
    "current_openai_agents_trace_config",
    "use_openai_agents_trace_config",
]
