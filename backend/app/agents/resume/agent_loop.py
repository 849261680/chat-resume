"""用于承接 Resume Agent 的 ReAct 执行循环。"""

from __future__ import annotations

import asyncio
import inspect
import logging
from itertools import count
from time import perf_counter
from typing import Any

from pi_agent_core import (
    AgentContext,
    AgentLoopConfig,
    AssistantMessage,
    SimpleStreamOptions,
    TextContent,
    ToolCall,
    ToolExecutionStartEvent,
    ToolResultMessage,
    UserMessage,
)
from pi_agent_core.types import Message, StreamFn

from app.agents.resume.stream_events import (
    llm_request_event,
    text_delta_event,
    tool_call_failed_event,
)
from app.agents.resume.tool_execution import ResumeToolExecutionStage
from app.agents.resume.event_publisher import publish_resume_runtime_event
from app.infra.config import settings
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.types.stream import ResumeStreamEvent

logger = logging.getLogger("app.agents.resume.runtime")

_UNEXECUTED_MUTATION_RETRY_PROMPT = (
    "上一轮回复声称已经修改简历，但没有发出结构化工具调用。"
    "如果要新增、修改、删除、拆分、精简或优化简历内容，"
    "必须立即调用一个可用的简历工具；不能只用自然语言声称完成。"
)
_UNEXECUTED_MUTATION_FALLBACK = (
    "我还没有通过简历工具完成修改，因此不能声称已完成改动。请明确要修改的具体条目。"
)
_MODEL_STREAM_ERROR_MESSAGE = "AI服务暂时不可用，请稍后重试。"
_MUTATION_CLAIM_MARKERS = (
    "已新增",
    "已更新",
    "已修改",
    "已删除",
    "已拆分",
    "已精简",
    "已优化",
    "已经新增",
    "已经更新",
    "已经修改",
    "已经删除",
    "已经拆分",
    "已经精简",
    "已经优化",
)
_MUTATION_COMPLETION_WORDS = (
    "已完成",
    "已经完成",
    "完成。",
    "完成，",
    "完成：",
    "优化总结",
    "修改总结",
    "改动总结",
)
_MUTATION_ACTION_WORDS = (
    "新增",
    "更新",
    "修改",
    "删除",
    "拆分",
    "精简",
    "优化",
    "改写",
    "重写",
    "bullet",
    "要点",
)


class ResumeAgentLoop:
    """用于执行 Resume Agent 的 ReAct turn 和工具回灌循环。"""

    def __init__(
        self,
        *,
        stream_fn: StreamFn,
        tool_stage: ResumeToolExecutionStage,
    ):
        """用于保存模型流函数和工具执行阶段。"""
        self.stream_fn = stream_fn
        self.tool_stage = tool_stage

    async def run(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        pi_context: AgentContext,
        prompts: list[Message],
        config: AgentLoopConfig,
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
        executed_tools: list[dict[str, Any]],
        model_name: str,
    ) -> None:
        """用于显式执行 Claude Code 风格的 ReAct 循环。"""
        messages = [*pi_context.messages, *prompts]
        iteration_limit = (
            max(1, agent.max_iterations)
            if agent.max_iterations is not None
            else None
        )
        for turn_index in count():
            if iteration_limit is not None and turn_index >= iteration_limit:
                self.trace(
                    "agent.trace.run.max_iterations_reached",
                    run_id=run_id,
                    agent_name=agent.prompt_spec.name,
                    tool_call_count=state.get("tool_call_count"),
                    reason="react_loop_limit",
                )
                return
            llm_context = await self.llm_context_for_turn(
                pi_context=pi_context,
                messages=messages,
                config=config,
            )
            request_event = self.llm_request_event(
                agent,
                llm_context,
                [],
                state,
                model_name,
            )
            self.trace_llm_request(agent, run_id, request_event, model_name)
            await self.publish_event(
                event_queue=event_queue,
                event_callback=event_callback,
                event=request_event,
            )
            assistant_message, text_deltas = await self.stream_assistant_turn(
                run_id=run_id,
                llm_context=llm_context,
                config=config,
                event_queue=event_queue,
                event_callback=event_callback,
                state=state,
            )
            messages.append(assistant_message)
            if assistant_message.stop_reason in ("error", "aborted"):
                await self.publish_model_stream_error(
                    agent=agent,
                    run_id=run_id,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    state=state,
                )
                return

            tool_calls = self.assistant_tool_calls(assistant_message)
            if not tool_calls:
                should_retry = await self.retry_or_publish_unexecuted_mutation_claim(
                    agent=agent,
                    run_id=run_id,
                    messages=messages,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    state=state,
                    text_deltas=text_deltas,
                    executed_tools=executed_tools,
                )
                if should_retry:
                    continue
                return
            tool_call = tool_calls[0]
            if len(tool_calls) > 1:
                self.trace(
                    "agent.trace.reasoning.extra_tool_calls_ignored",
                    run_id=run_id,
                    agent_name=agent.prompt_spec.name,
                    tool_name=tool_call.name,
                    tool_call_count=len(tool_calls),
                    reason="one_tool_per_react_turn",
                )
            tool_result = await self.execute_react_tool(
                agent=agent,
                run_id=run_id,
                tool_call=tool_call,
                context=context,
                confirmation_queue=confirmation_queue,
                event_queue=event_queue,
                event_callback=event_callback,
                state=state,
                executed_tools=executed_tools,
            )
            messages.append(tool_result)
            if self.should_terminate_after_tool_result(tool_result):
                self.trace_tool_result_terminated(agent, run_id, tool_result)
                await self.publish_text_deltas(
                    agent=agent,
                    run_id=run_id,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    state=state,
                    text_deltas=[self.tool_result_terminal_text(tool_result)],
                )
                return

    async def llm_context_for_turn(
        self,
        *,
        pi_context: AgentContext,
        messages: list[Message],
        config: AgentLoopConfig,
    ) -> AgentContext:
        """用于把当前 ReAct 消息链转换成供应商请求上下文。"""
        convert_result = config.convert_to_llm(messages)
        if inspect.isawaitable(convert_result):
            llm_messages = await convert_result
        else:
            llm_messages = convert_result
        return AgentContext(
            system_prompt=pi_context.system_prompt,
            messages=list(llm_messages),
            tools=pi_context.tools,
        )

    async def stream_assistant_turn(
        self,
        *,
        run_id: str,
        llm_context: AgentContext,
        config: AgentLoopConfig,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
    ) -> tuple[AssistantMessage, list[str]]:
        """用于拉取一轮 assistant 流，并暂存文本直到确认没有工具调用。"""
        del run_id
        cancel_event = asyncio.Event()
        response = self.stream_fn(
            config.model,
            llm_context,
            SimpleStreamOptions(
                api_key=config.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                reasoning=config.reasoning,
                session_id=config.session_id,
                transport=config.transport,
                thinking_budgets=config.thinking_budgets,
                max_retry_delay_ms=config.max_retry_delay_ms,
                cancel_event=cancel_event,
            ),
        )
        text_deltas: list[str] = []
        early_tool_call_published = False
        visible_early_tool_call: ToolCall | None = None
        try:
            if inspect.isawaitable(response):
                response = await response
            if not isinstance(response, dict) or "events" not in response or "result" not in response:
                raise TypeError("StreamFn must return {'events': AsyncIterator, 'result': async callable}")

            async for raw_event in response["events"]:
                early_tool_call = self.early_tool_call_from_event(raw_event)
                if (
                    early_tool_call is not None
                    and not early_tool_call_published
                    and self.tool_stage.remember_visible_tool_call(state, early_tool_call.id)
                ):
                    early_tool_call_published = True
                    visible_early_tool_call = early_tool_call
                    await self.tool_stage.publish_visible_tool_call(
                        call_id=early_tool_call.id,
                        tool_name=early_tool_call.name,
                        tool_input={},
                        event_queue=event_queue,
                        event_callback=event_callback,
                    )
                delta = self.text_delta_from_event(raw_event)
                if delta:
                    if state["first_token_latency_ms"] is None:
                        state["first_token_latency_ms"] = round(
                            (perf_counter() - state["started_at"]) * 1000,
                            2,
                        )
                    text_deltas.append(delta)

            result = response["result"]()
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, AssistantMessage):
                raise TypeError("StreamFn result must be an AssistantMessage")
            assistant_message = self.single_tool_message(result)
            state["last_assistant_text"] = self.assistant_text(assistant_message)
            state["usage"] = self.usage_to_dict(getattr(assistant_message, "usage", None))
            await self.publish_failed_visible_tool_call_on_stream_error(
                assistant_message=assistant_message,
                tool_call=visible_early_tool_call,
                event_queue=event_queue,
                event_callback=event_callback,
            )
            return assistant_message, text_deltas
        finally:
            cancel_event.set()

    async def publish_model_stream_error(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
    ) -> None:
        """用于把模型供应商或断流错误转成前端可见消息。"""
        state["error_type"] = "model_stream_error"
        await self.publish_text_deltas(
            agent=agent,
            run_id=run_id,
            event_queue=event_queue,
            event_callback=event_callback,
            state=state,
            text_deltas=[_MODEL_STREAM_ERROR_MESSAGE],
        )

    @classmethod
    async def publish_failed_visible_tool_call_on_stream_error(
        cls,
        *,
        assistant_message: AssistantMessage,
        tool_call: ToolCall | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
    ) -> None:
        """用于在模型断流时关闭已提前展示的工具卡片。"""
        if tool_call is None:
            return
        if assistant_message.stop_reason not in ("error", "aborted"):
            return
        message = assistant_message.error_message or "模型工具调用中断，请重试。"
        await cls.publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=tool_call_failed_event(
                call_id=tool_call.id,
                tool_id=tool_call.name,
                tool_display_name=tool_call.name,
                tool_calls=[],
                result={
                    "success": False,
                    "error": {
                        "type": "model_stream_interrupted",
                        "message": message,
                        "recoverable": True,
                    },
                    "message": message,
                },
                display_message=message,
            ),
        )

    @staticmethod
    def assistant_tool_calls(message: AssistantMessage) -> list[ToolCall]:
        """用于从 assistant 消息中提取本轮工具调用。"""
        return [block for block in message.content if isinstance(block, ToolCall)]

    async def retry_or_publish_unexecuted_mutation_claim(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        messages: list[Message],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
        text_deltas: list[str],
        executed_tools: list[dict[str, Any]],
    ) -> bool:
        """用于处理没有真实工具调用的简历修改完成声明。"""
        assistant_text = "".join(text_deltas) or str(state.get("last_assistant_text") or "")
        if not self.is_unexecuted_mutation_claim(assistant_text, executed_tools):
            await self.publish_text_deltas(
                agent=agent,
                run_id=run_id,
                event_queue=event_queue,
                event_callback=event_callback,
                state=state,
                text_deltas=text_deltas,
            )
            return False

        retry_count = int(state.get("mutation_claim_retry_count") or 0)
        if retry_count >= 1:
            await self.publish_text_deltas(
                agent=agent,
                run_id=run_id,
                event_queue=event_queue,
                event_callback=event_callback,
                state=state,
                text_deltas=[_UNEXECUTED_MUTATION_FALLBACK],
            )
            return False

        state["mutation_claim_retry_count"] = retry_count + 1
        self.trace(
            "agent.trace.reasoning.unexecuted_mutation_claim_retry",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            reason="no_tool_call_before_mutation_claim",
        )
        messages.append(UserMessage(content=[TextContent(text=_UNEXECUTED_MUTATION_RETRY_PROMPT)]))
        return True

    @staticmethod
    def is_unexecuted_mutation_claim(
        assistant_text: str,
        executed_tools: list[dict[str, Any]],
    ) -> bool:
        """用于判断回复是否在没有工具结果时声称已修改简历。"""
        if executed_tools:
            return False
        text = assistant_text.strip()
        if not text:
            return False
        if any(marker in text for marker in _MUTATION_CLAIM_MARKERS):
            return True
        has_completion = any(word in text for word in _MUTATION_COMPLETION_WORDS)
        return has_completion and any(word in text for word in _MUTATION_ACTION_WORDS)

    @staticmethod
    def early_tool_call_from_event(raw_event: Any) -> ToolCall | None:
        """用于从底层 toolcall_start 事件中读取可提前展示的工具名。"""
        if str(getattr(raw_event, "type", "") or "") != "toolcall_start":
            return None
        content_index = getattr(raw_event, "content_index", None)
        if not isinstance(content_index, int):
            return None
        partial = getattr(raw_event, "partial", None)
        content = getattr(partial, "content", None)
        if not isinstance(content, list) or content_index < 0 or content_index >= len(content):
            return None
        block = content[content_index]
        if not isinstance(block, ToolCall) or not block.id or not block.name:
            return None
        return block

    @staticmethod
    def text_delta_from_event(raw_event: Any) -> str:
        """用于从底层流式事件中提取纯文本增量。"""
        if str(getattr(raw_event, "type", "") or "") != "text_delta":
            return ""
        return str(getattr(raw_event, "delta", "") or "")

    async def publish_text_deltas(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
        text_deltas: list[str],
    ) -> None:
        """用于把已确认可见的 assistant 文本增量发布给前端。"""
        for content in text_deltas:
            if not content:
                continue
            state["chunk_index"] += 1
            state["response_parts"].append(content)
            self.trace_chunk(
                "agent.trace.intermediate.chunk",
                run_id=run_id,
                agent_name=agent.prompt_spec.name,
                chunk_index=state["chunk_index"],
                content_preview=ResumeToolExecutionStage.preview_text(content),
                content_chars=len(content),
            )
            await self.publish_event(
                event_queue=event_queue,
                event_callback=event_callback,
                event=text_delta_event(content=content),
            )

    async def execute_react_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        tool_call: ToolCall,
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
        executed_tools: list[dict[str, Any]],
    ) -> ToolResultMessage:
        """用于执行一个 ReAct 工具调用并返回可追加消息链的结果。"""
        state["tool_call_count"] += 1
        self.trace_tool_call_detected(
            agent,
            run_id,
            ToolExecutionStartEvent(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                args=tool_call.arguments,
            ),
            state,
        )
        result = await self.tool_stage.execute_tool_result(
            agent=agent,
            run_id=run_id,
            call_id=tool_call.id,
            tool_name=tool_call.name,
            tool_input=tool_call.arguments,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            stream_state=state,
        )
        return ToolResultMessage(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            content=result.content,
            details=result.details,
            is_error=False,
        )

    @staticmethod
    def should_terminate_after_tool_result(message: ToolResultMessage) -> bool:
        """用于识别 Pi-style 终止型工具结果。"""
        details = message.details
        return isinstance(details, dict) and details.get("terminate") is True

    @staticmethod
    def tool_result_terminal_text(message: ToolResultMessage) -> str:
        """用于从终止型工具结果里提取确定性回复文本。"""
        details = message.details
        if not isinstance(details, dict):
            return ""
        message_text = details.get("message")
        return message_text if isinstance(message_text, str) else ""

    @classmethod
    def trace_tool_result_terminated(
        cls,
        agent: AgentDefinition,
        run_id: str,
        message: ToolResultMessage,
    ) -> None:
        """用于记录工具结果直接结束 ReAct loop。"""
        cls.trace(
            "agent.trace.reasoning.tool_result_terminated",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            tool_name=message.tool_name,
            reason="pi_style_tool_result_terminate",
        )

    @staticmethod
    def llm_request_event(
        agent: AgentDefinition,
        context: AgentContext,
        prompts: list[Message],
        state: dict[str, Any],
        model_name: str,
    ) -> ResumeStreamEvent:
        """用于生成 LLM 请求事件。"""
        messages = [ResumeAgentLoop.message_to_dict(message) for message in context.messages + prompts]
        tool_names: list[str | None] = [tool.name for tool in context.tools]
        return llm_request_event(
            agent_name=agent.prompt_spec.name,
            model=model_name,
            messages=[{"role": "system", "content": context.system_prompt}, *messages],
            params={
                "temperature": agent.prompt_spec.model_defaults.get("temperature", 0.3),
                "max_tokens": agent.prompt_spec.model_defaults.get("max_tokens", 1500),
            },
            tool_names=tool_names,
            tool_profile=str(state.get("tool_profile") or ""),
            prompt_chars=int(state.get("prompt_chars") or len(context.system_prompt)),
        )

    @classmethod
    def trace_llm_request(
        cls,
        agent: AgentDefinition,
        run_id: str,
        event: ResumeStreamEvent,
        model_name: str,
    ) -> None:
        """用于记录 LLM 请求 trace。"""
        cls.trace(
            "agent.trace.llm.request",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            model=model_name,
            message_count=len(event.get("messages", [])),
            tool_profile=event.get("tool_profile"),
            tool_count=event.get("tool_count"),
            prompt_chars=event.get("prompt_chars"),
            tool_names=event.get("tool_names", []),
            params=event.get("params", {}),
        )

    @classmethod
    def trace_tool_call_detected(
        cls,
        agent: AgentDefinition,
        run_id: str,
        event: ToolExecutionStartEvent,
        state: dict[str, Any],
    ) -> None:
        """用于记录模型工具调用是否在暴露工具集中。"""
        allowed_tool_names = {
            str(tool_name)
            for tool_name in state.get("tool_names", [])
            if isinstance(tool_name, str)
        }
        if event.tool_name not in allowed_tool_names:
            cls.trace_unexpected_tool_call(agent, run_id, event, state)
            return
        cls.trace(
            "agent.trace.reasoning.tool_call_detected",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            tool_call_count=1,
            tool_call_chunk_count=1,
            tool_names=[event.tool_name],
        )

    @classmethod
    def trace_unexpected_tool_call(
        cls,
        agent: AgentDefinition,
        run_id: str,
        event: ToolExecutionStartEvent,
        state: dict[str, Any],
    ) -> None:
        """用于记录未暴露工具被模型调用的异常 trace。"""
        logged = state.get("unexpected_tool_call_names")
        if not isinstance(logged, set):
            logged = set()
            state["unexpected_tool_call_names"] = logged
        if event.tool_name in logged:
            return
        logged.add(event.tool_name)
        cls.trace(
            "agent.trace.reasoning.unexpected_tool_call",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            tool_name=event.tool_name,
            tool_profile=str(state.get("tool_profile") or ""),
            allowed_tool_names=list(state.get("tool_names", [])),
            reason="tool_not_exposed",
        )

    @staticmethod
    def message_to_dict(message: Message) -> dict[str, Any]:
        """用于把 pi-agent-core 消息转换成事件载荷。"""
        role = getattr(message, "role", "unknown")
        content = ResumeAgentLoop.assistant_text(message)
        return {"role": role, "content": content}

    @staticmethod
    def assistant_text(message: Any) -> str:
        """用于提取 assistant 或通用消息里的文本内容。"""
        parts = []
        for block in getattr(message, "content", []):
            if isinstance(block, TextContent):
                parts.append(block.text)
        return "".join(parts)

    @staticmethod
    def single_tool_message(message: AssistantMessage) -> AssistantMessage:
        """用于保留文本和首个工具调用，丢弃同一轮后续工具调用。"""
        seen_tool = False
        content: list[Any] = []
        for block in message.content:
            if not isinstance(block, ToolCall):
                content.append(block)
                continue
            if seen_tool:
                continue
            seen_tool = True
            content.append(block)
        return message.model_copy(update={"content": content})

    @staticmethod
    async def publish_event(
        *,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        event: ResumeStreamEvent,
    ) -> None:
        """用于发布 runtime 事件。"""
        await publish_resume_runtime_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=event,
        )

    @staticmethod
    def usage_to_dict(usage: Any) -> dict[str, Any]:
        """用于把 pi-agent-core usage 转换成日志友好的字典。"""
        if usage is None:
            return {}
        return {
            "input": int(getattr(usage, "input", 0) or 0),
            "output": int(getattr(usage, "output", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
            "cache_read": int(getattr(usage, "cache_read", 0) or 0),
            "cache_write": int(getattr(usage, "cache_write", 0) or 0),
        }

    @staticmethod
    def trace(message: str, **fields: Any) -> None:
        """用于写入 Agent loop trace 日志。"""
        if not settings.AGENT_TRACE_LOG_ENABLED:
            return
        level = int(fields.pop("log_level", logging.INFO))
        logger.log(level, message, extra={"agent_trace": True, **fields})

    @classmethod
    def trace_chunk(cls, message: str, **fields: Any) -> None:
        """用于按配置写入流式 chunk trace。"""
        if not settings.AGENT_TRACE_CHUNK_LOG_ENABLED:
            return
        cls.trace(message, **fields)


__all__ = ["ResumeAgentLoop"]
