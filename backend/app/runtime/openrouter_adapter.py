"""用于集中构建 OpenRouter provider 配置和 pi-agent-core loop 配置。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pi_agent_core import AgentLoopConfig, Model
from pi_agent_core.types import Message

from app.infra.config import settings
from app.runtime.contracts import AgentDefinition


@dataclass(frozen=True)
class OpenRouterAdapterConfig:
    """用于描述一次 OpenRouter LLM 请求的 provider 配置。"""

    model: Model
    api_key: str | None
    temperature: float | None
    max_tokens: int | None
    reasoning: str | None = None


def build_openrouter_config(agent: AgentDefinition) -> OpenRouterAdapterConfig:
    """用于从业务 Agent 默认值构造 OpenRouter 配置。"""
    return OpenRouterAdapterConfig(
        model=Model(
            api="openai-compatible",
            provider="openrouter",
            id=settings.OPENROUTER_MODEL,
        ),
        api_key=settings.OPENROUTER_API_KEY,
        temperature=agent.prompt_spec.model_defaults.get("temperature", 0.3),
        max_tokens=agent.prompt_spec.model_defaults.get("max_tokens", 1500),
    )


def build_openrouter_loop_config(
    agent: AgentDefinition,
    *,
    convert_to_llm: Callable[[list[Message]], list[Message]],
) -> AgentLoopConfig:
    """用于创建 pi-agent-core 可执行的 OpenRouter loop 配置。"""
    config = build_openrouter_config(agent)
    return AgentLoopConfig(
        model=config.model,
        reasoning=None,
        api_key=config.api_key,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        convert_to_llm=convert_to_llm,
    )


def openrouter_chat_model_name() -> str:
    """用于返回当前聊天模型名称。"""
    return settings.OPENROUTER_MODEL


__all__ = [
    "OpenRouterAdapterConfig",
    "build_openrouter_config",
    "build_openrouter_loop_config",
    "openrouter_chat_model_name",
]
