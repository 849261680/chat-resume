"""用于组装 Resume Agent 的 OpenAI Agents SDK 运行时适配器。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from pi_agent_core.types import StreamFn

from app.agents.resume.agent_loop import ResumeAgentLoop
from app.agents.resume.run_lifecycle import ResumeRunLifecycle
from app.agents.resume.runner import ResumeAgentRunner
from app.agents.resume.stream_adapter import ResumeReActStreamAdapter
from app.agents.resume.tool_execution import ResumeToolExecutionStage
from app.agents.resume.turn_context import ResumeTurnContextBuilder
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.runtime.openai_agents_adapter import (
    openai_agents_chat_model_name,
    stream_openai_agents,
)
from app.runtime.tool_confirmation import ToolConfirmationPolicy
from app.types.stream import ResumeStreamEvent


class ResumeAgentRuntime:
    """用于把 Resume Agent 组件组装成公开 run/run_stream 接口。"""

    def __init__(
        self,
        stream_fn: StreamFn | None = None,
        confirmation_policy: ToolConfirmationPolicy | None = None,
    ):
        """用于初始化 Resume Agent 运行时依赖图。"""
        self.stream_fn = ResumeReActStreamAdapter(stream_fn or stream_openai_agents)
        self.tool_stage = ResumeToolExecutionStage(
            confirmation_policy=confirmation_policy or ToolConfirmationPolicy()
        )
        self.agent_loop = ResumeAgentLoop(
            stream_fn=self.stream_fn,
            tool_stage=self.tool_stage,
        )
        self.lifecycle = ResumeRunLifecycle(
            model_name_provider=openai_agents_chat_model_name,
        )
        self.turn_context_builder = ResumeTurnContextBuilder(
            tool_stage=self.tool_stage,
        )
        self.runner = ResumeAgentRunner(
            agent_loop=self.agent_loop,
            turn_context_builder=self.turn_context_builder,
            lifecycle=self.lifecycle,
            model_name_provider=openai_agents_chat_model_name,
        )

    async def run(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> dict[str, Any]:
        """用于兼容 runtime 接口，并委托 Resume Agent runner 执行。"""
        return await self.runner.run(
            agent=agent,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            event_callback=event_callback,
        )

    async def run_stream(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        confirmation_queue: asyncio.Queue | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> AsyncGenerator[ResumeStreamEvent, None]:
        """用于兼容 runtime 接口，并委托 Resume Agent runner 返回事件流。"""
        async for event in self.runner.run_stream(
            agent=agent,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            confirmation_queue=confirmation_queue,
            event_callback=event_callback,
        ):
            yield event


__all__ = ["ResumeAgentRuntime"]
