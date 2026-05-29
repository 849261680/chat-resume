"""用于承接 Resume Agent 的单次 run 和流式 run 编排。"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Callable
from typing import Any
from uuid import uuid4

from pi_agent_core import AgentContext, AgentLoopConfig
from pi_agent_core.types import Message

from app.agents.resume.agent_loop import ResumeAgentLoop
from app.agents.resume.run_lifecycle import ResumeRunLifecycle
from app.agents.resume.turn_context import ResumeTurnContextBuilder
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.types.stream import ResumeStreamEvent

_SENTINEL = object()


class ResumeAgentRunner:
    """用于按 Resume Agent 层职责编排同步和 SSE 流式运行。"""

    def __init__(
        self,
        *,
        agent_loop: ResumeAgentLoop,
        turn_context_builder: ResumeTurnContextBuilder,
        lifecycle: ResumeRunLifecycle,
        model_name_provider: Callable[[], str],
    ):
        """用于保存 run 编排所需的 loop、context builder 和 lifecycle。"""
        self.agent_loop = agent_loop
        self.turn_context_builder = turn_context_builder
        self.lifecycle = lifecycle
        self.model_name_provider = model_name_provider

    async def run(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> dict[str, Any]:
        """用于执行一次同步 Resume Agent run 并返回最终内容。"""
        run_id = uuid4().hex
        executed_tools: list[dict[str, Any]] = []
        state = self.lifecycle.new_stream_state()
        error_type: str | None = None
        pi_context, prompts, config = self.turn_context_builder.build_loop_inputs(
            agent=agent,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            run_id=run_id,
            confirmation_queue=None,
            event_queue=None,
            event_callback=event_callback,
            executed_tools=executed_tools,
            stream_state=state,
        )
        self.lifecycle.trace_run_start(
            agent,
            run_id,
            "sync",
            user_message,
            conversation_history,
        )
        self.lifecycle.trace_prompt(agent, run_id, pi_context.system_prompt)
        self.lifecycle.emit_event(
            event_callback,
            self.lifecycle.prompt_rendered_event(agent, pi_context.system_prompt, user_message),
        )
        try:
            await self.agent_loop.run(
                agent=agent,
                run_id=run_id,
                pi_context=pi_context,
                prompts=prompts,
                config=config,
                context=context,
                confirmation_queue=None,
                event_queue=None,
                event_callback=event_callback,
                state=state,
                executed_tools=executed_tools,
                model_name=self.model_name_provider(),
            )
            response_event = self.lifecycle.llm_response_event(agent, state)
            self.lifecycle.trace_llm_response(agent, run_id, response_event)
            self.lifecycle.emit_event(event_callback, response_event)
            self.lifecycle.trace_run_completed(agent, run_id, "sync", state)
            return {"content": "".join(state["response_parts"]), "tool_calls": executed_tools}
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            state_error_type = state.get("error_type")
            if not isinstance(state_error_type, str):
                state_error_type = None
            self.lifecycle.log_run_summary(
                agent=agent,
                run_id=run_id,
                mode="sync",
                state=state,
                success=error_type is None and state_error_type is None,
                error_type=error_type or state_error_type,
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
        """用于执行一次 Resume Agent run 并按 SSE 事件流式返回。"""
        run_id = uuid4().hex
        executed_tools: list[dict[str, Any]] = []
        event_queue: asyncio.Queue[Any] = asyncio.Queue()
        state = self.lifecycle.new_stream_state()
        pi_context, prompts, config = self.turn_context_builder.build_loop_inputs(
            agent=agent,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            run_id=run_id,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            stream_state=state,
        )
        self.lifecycle.trace_run_start(
            agent,
            run_id,
            "stream",
            user_message,
            conversation_history,
        )
        self.lifecycle.trace_prompt(agent, run_id, pi_context.system_prompt)
        prompt_event = self.lifecycle.prompt_rendered_event(
            agent,
            pi_context.system_prompt,
            user_message,
        )
        self.lifecycle.emit_event(event_callback, prompt_event)
        yield prompt_event

        producer = asyncio.create_task(
            self._produce_stream_events(
                agent=agent,
                run_id=run_id,
                pi_context=pi_context,
                prompts=prompts,
                config=config,
                context=context,
                confirmation_queue=confirmation_queue,
                event_queue=event_queue,
                event_callback=event_callback,
                state=state,
                executed_tools=executed_tools,
            )
        )
        try:
            while True:
                event = await event_queue.get()
                if event is _SENTINEL:
                    break
                yield event
            await producer
        finally:
            if not producer.done():
                producer.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await producer
        self.lifecycle.trace_run_completed(agent, run_id, "stream", state)

    async def _produce_stream_events(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        pi_context: AgentContext,
        prompts: list[Message],
        config: AgentLoopConfig,
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any],
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
        executed_tools: list[dict[str, Any]],
    ) -> None:
        """用于在后台任务中执行 loop 并发布最终响应事件。"""
        try:
            await self.agent_loop.run(
                agent=agent,
                run_id=run_id,
                pi_context=pi_context,
                prompts=prompts,
                config=config,
                context=context,
                confirmation_queue=confirmation_queue,
                event_queue=event_queue,
                event_callback=event_callback,
                state=state,
                executed_tools=executed_tools,
                model_name=self.model_name_provider(),
            )
        except Exception as exc:
            state["error_type"] = type(exc).__name__
            raise
        finally:
            response_event = self.lifecycle.llm_response_event(agent, state)
            self.lifecycle.trace_llm_response(agent, run_id, response_event)
            await self.lifecycle.publish_event(
                event_queue=event_queue,
                event_callback=event_callback,
                event=response_event,
            )
            error_type = state.get("error_type")
            self.lifecycle.log_run_summary(
                agent=agent,
                run_id=run_id,
                mode="stream",
                state=state,
                success=not isinstance(error_type, str),
                error_type=error_type if isinstance(error_type, str) else None,
            )
            await event_queue.put(_SENTINEL)
