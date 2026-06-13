"""用于把 OpenAI Agents SDK 原生工具循环适配到 Resume Agent 运行时。"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import AsyncIterator
from typing import Any, cast

from agents import Agent as OpenAIAgent
from agents import FunctionTool, ModelSettings, RunConfig, Runner, ToolsToFinalOutputResult
from agents.items import TResponseInputItem, ToolApprovalItem
from agents.models.interface import Model as OpenAIAgentsModel
from agents.models.openai_provider import OpenAIProvider
from agents.result import RunResultStreaming
from agents.run_state import RunState
from agents.stream_events import RawResponsesStreamEvent
from agents.usage import Usage as OpenAIAgentsUsage
from pi_agent_core import (
    AgentContext,
    AgentLoopConfig,
    AssistantMessage,
    Model,
    SimpleStreamOptions,
    StreamDoneEvent,
    StreamResult,
    StreamTextDeltaEvent,
    TextContent,
    ToolCall,
    Usage,
)
from pi_agent_core.types import Message

from app.agents.resume.message_conversion import convert_resume_messages_to_llm
from app.infra.config import settings
from app.runtime.contracts import AgentDefinition
from app.runtime.openai_agents_eval import current_openai_agents_trace_config
from app.runtime.openai_agents_tools import (
    compact_tool_arguments,
    strict_tool_params_schema,
    tool_input_guardrail,
    tool_output_guardrail,
)

OPENAI_AGENTS_PROVIDER_OPENAI = "openai"
OPENAI_AGENTS_PROVIDER_DEEPSEEK = "deepseek"
OPENAI_AGENTS_MODEL_PROVIDER_OPENAI = "openai-agents"
OPENAI_AGENTS_RESUME_MAX_TURNS = 40


def normalized_openai_agents_provider() -> str:
    """用于规范化 OpenAI Agents SDK 的模型供应商配置。"""
    provider = settings.OPENAI_AGENTS_PROVIDER.strip().lower()
    if provider == OPENAI_AGENTS_PROVIDER_DEEPSEEK:
        return OPENAI_AGENTS_PROVIDER_DEEPSEEK
    return OPENAI_AGENTS_PROVIDER_OPENAI


def build_openai_agents_loop_config(
    agent: AgentDefinition,
) -> AgentLoopConfig:
    """用于创建现有 ReAct loop 可消费的 OpenAI Agents SDK 配置。"""
    provider = normalized_openai_agents_provider()
    return AgentLoopConfig(
        model=Model(
            api="chat_completions" if provider == OPENAI_AGENTS_PROVIDER_DEEPSEEK else "responses",
            provider=model_provider_name(provider),
            id=settings.OPENAI_AGENTS_MODEL,
        ),
        api_key=provider_api_key(provider),
        temperature=agent.prompt_spec.model_defaults.get("temperature", 0.3),
        max_tokens=agent.prompt_spec.model_defaults.get("max_tokens", 1500),
        convert_to_llm=convert_resume_messages_to_llm,
    )


def openai_agents_chat_model_name() -> str:
    """用于返回当前 OpenAI Agents SDK 聊天模型名称。"""
    return settings.OPENAI_AGENTS_MODEL


def provider_api_key(provider: str) -> str:
    """用于按 provider 读取对应 API key。"""
    if provider == OPENAI_AGENTS_PROVIDER_DEEPSEEK:
        return settings.DEEPSEEK_API_KEY
    return settings.OPENAI_API_KEY


def model_provider_name(provider: str) -> str:
    """用于保持 OpenAI 默认 provider 标识并暴露 DeepSeek 分支。"""
    if provider == OPENAI_AGENTS_PROVIDER_DEEPSEEK:
        return OPENAI_AGENTS_PROVIDER_DEEPSEEK
    return OPENAI_AGENTS_MODEL_PROVIDER_OPENAI


def deepseek_extra_body(model: Model) -> dict[str, Any] | None:
    """用于关闭 DeepSeek thinking mode 以避免工具回放缺失 reasoning_content。"""
    if model.provider != OPENAI_AGENTS_PROVIDER_DEEPSEEK:
        return None
    thinking_type = settings.DEEPSEEK_THINKING_TYPE.strip().lower()
    if thinking_type not in {"enabled", "disabled"}:
        thinking_type = "disabled"
    return {"thinking": {"type": thinking_type}}


async def stream_openai_agents(
    model: Model,
    context: AgentContext,
    options: SimpleStreamOptions,
) -> StreamResult:
    """用于通过 OpenAI Agents SDK 执行一轮 SDK 原生工具循环。"""
    adapter = OpenAIAgentsStreamAdapter()
    return await adapter(model, context, options)


class OpenAIAgentsStreamAdapter:
    """用于把 SDK Agent 结果转换成 pi-agent-core 流式结果。"""

    def __init__(self, sdk_model: OpenAIAgentsModel | None = None):
        """用于保存测试可注入的 SDK model。"""
        self.sdk_model = sdk_model

    async def __call__(
        self,
        model: Model,
        context: AgentContext,
        options: SimpleStreamOptions,
    ) -> StreamResult:
        """用于返回现有 ResumeAgentLoop 期望的 StreamResult。"""
        bridge = OpenAIAgentsStreamBridge(self, model, context, options)
        return {"events": bridge.events(), "result": bridge.result}

    def run_sdk_streamed(
        self,
        sdk_agent: OpenAIAgent[Any],
        input_items: list[TResponseInputItem] | RunState[Any],
        run_config: RunConfig,
    ) -> RunResultStreaming:
        """用于通过 SDK 原生 streaming runner 启动或恢复一次 run。"""
        return Runner.run_streamed(
            sdk_agent,
            input_items,
            max_turns=OPENAI_AGENTS_RESUME_MAX_TURNS,
            run_config=run_config,
        )

    def build_sdk_agent(
        self,
        model: Model,
        context: AgentContext,
        options: SimpleStreamOptions,
    ) -> OpenAIAgent[Any]:
        """用于把 pi-agent-core 上下文转换成 OpenAI SDK Agent。"""
        return OpenAIAgent(
            name="Resume optimizer",
            instructions=context.system_prompt,
            model=self.sdk_model or model.id,
            model_settings=self.model_settings(model, options),
            tools=[self.function_tool(tool) for tool in context.tools],
            tool_use_behavior=self.tool_use_behavior,
        )

    @staticmethod
    def tool_use_behavior(_context: Any, tool_results: list[Any]) -> ToolsToFinalOutputResult:
        """用于让 SDK 在终止型工具结果上直接结束运行。"""
        for tool_result in tool_results:
            output = getattr(tool_result, "output", None)
            parsed = OpenAIAgentsStreamAdapter.parse_tool_output(output)
            if isinstance(parsed, dict) and parsed.get("terminate") is True:
                message = parsed.get("message")
                return ToolsToFinalOutputResult(
                    is_final_output=True,
                    final_output=message if isinstance(message, str) else str(output or ""),
                )
        return ToolsToFinalOutputResult(is_final_output=False, final_output=None)
    @staticmethod
    async def resolve_tool_approval(
        context: AgentContext,
        interruption: ToolApprovalItem,
    ) -> tuple[bool, str | None]:
        """用于把 SDK ToolApprovalItem 分发给业务确认处理器。"""
        tool = OpenAIAgentsStreamAdapter.tool_for_approval(context.tools, interruption)
        handler = getattr(tool, "_sdk_handle_approval", None) if tool is not None else None
        if handler is None:
            return True, None
        result = handler(interruption)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, tuple) and len(result) == 2:
            approved, message = result
            return bool(approved), message if isinstance(message, str) else None
        return bool(result), None

    @staticmethod
    def tool_for_approval(
        tools: list[Any],
        interruption: ToolApprovalItem,
    ) -> Any | None:
        """用于按 interruption 工具名查找原始业务工具。"""
        name = interruption.name
        for tool in tools:
            if str(getattr(tool, "name", "")) == name:
                return tool
        return None

    @staticmethod
    def parse_tool_output(output: Any) -> Any:
        """用于把 SDK 工具输出解析为可能的 JSON 对象。"""
        if not isinstance(output, str):
            return output
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return output

    @staticmethod
    def model_settings(model: Model, options: SimpleStreamOptions) -> ModelSettings:
        """用于创建 provider-aware 的 SDK 模型参数。"""
        return ModelSettings(
            temperature=options.temperature,
            max_tokens=options.max_tokens,
            parallel_tool_calls=False,
            extra_body=deepseek_extra_body(model),
        )

    def run_config(self, model: Model, options: SimpleStreamOptions) -> RunConfig:
        """用于把 API key 显式交给 SDK provider。"""
        config = self.provider_run_config(model, options)
        self.apply_eval_trace_config(config)
        return config

    def provider_run_config(self, model: Model, options: SimpleStreamOptions) -> RunConfig:
        """用于按 provider 创建基础 SDK RunConfig。"""
        if self.sdk_model is not None:
            return RunConfig(tracing_disabled=True)
        if model.provider == OPENAI_AGENTS_PROVIDER_DEEPSEEK:
            return RunConfig(
                model=model.id,
                model_provider=OpenAIProvider(
                    api_key=options.api_key,
                    base_url=settings.DEEPSEEK_API_BASE,
                    use_responses=False,
                ),
                tracing_disabled=True,
            )
        if options.api_key:
            return RunConfig(model=model.id, model_provider=OpenAIProvider(api_key=options.api_key))
        return RunConfig(model=model.id)

    @staticmethod
    def apply_eval_trace_config(config: RunConfig) -> None:
        """用于把当前 eval trace 配置写入 SDK RunConfig。"""
        trace_config = current_openai_agents_trace_config()
        if trace_config is None:
            return
        config.workflow_name = trace_config.workflow_name
        config.trace_id = trace_config.trace_id
        config.group_id = trace_config.group_id
        config.trace_metadata = dict(trace_config.metadata)
        config.trace_include_sensitive_data = trace_config.trace_include_sensitive_data

    @staticmethod
    def function_tool(tool: Any) -> FunctionTool:
        """用于把现有 AgentTool schema 包装为 SDK 原生执行的 FunctionTool。"""

        async def on_invoke_tool(tool_context: Any, raw_input: str) -> str:
            """用于把 SDK 工具调用转交给现有业务工具执行器。"""
            params = compact_tool_arguments(
                OpenAIAgentsStreamAdapter.parse_tool_arguments(raw_input)
            )
            result = tool.execute(tool_context.tool_call_id, params)
            if inspect.isawaitable(result):
                result = await result
            if result is None:
                return ""
            return OpenAIAgentsStreamAdapter.text_from_content(result.content)
        required = list(tool.parameters.required or [])
        return FunctionTool(
            name=str(tool.name),
            description=str(tool.description),
            params_json_schema=strict_tool_params_schema({
                "type": str(tool.parameters.type or "object"),
                "properties": dict(tool.parameters.properties or {}),
                "required": required,
            }),
            on_invoke_tool=on_invoke_tool,
            strict_json_schema=True,
            tool_input_guardrails=[tool_input_guardrail(required)],
            tool_output_guardrails=[tool_output_guardrail()],
            needs_approval=getattr(tool, "_sdk_needs_approval", False),
        )

    @classmethod
    def input_items(cls, messages: list[Message]) -> list[TResponseInputItem]:
        """用于把现有消息链转换成 Responses API input item。"""
        items: list[TResponseInputItem] = []
        for message in messages:
            items.extend(cls.input_items_for_message(message))
        return items

    @classmethod
    def input_items_for_message(cls, message: Message) -> list[TResponseInputItem]:
        """用于转换单条 pi-agent-core 消息。"""
        role = getattr(message, "role", "")
        if role == "user":
            return [cls.user_message_item(cls.text_from_content(message.content))]
        if role == "assistant":
            return cls.assistant_items(message)
        if role == "toolResult":
            return [cls.tool_result_item(message)]
        return []

    @staticmethod
    def user_message_item(text: str) -> TResponseInputItem:
        """用于构建用户输入 item。"""
        return cast(
            TResponseInputItem,
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]},
        )

    @staticmethod
    def assistant_text_item(text: str) -> TResponseInputItem:
        """用于构建可回放的 assistant 文本 item。"""
        return cast(
            TResponseInputItem,
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            },
        )

    @staticmethod
    def assistant_tool_item(block: ToolCall) -> TResponseInputItem:
        """用于构建可回放的 assistant 工具调用 item。"""
        return cast(
            TResponseInputItem,
            {
                "type": "function_call",
                "call_id": block.id,
                "name": block.name,
                "arguments": json.dumps(block.arguments, ensure_ascii=False),
            },
        )

    @staticmethod
    def tool_result_item(message: Any) -> TResponseInputItem:
        """用于构建可回放的工具结果 item。"""
        return cast(
            TResponseInputItem,
            {
                "type": "function_call_output",
                "call_id": message.tool_call_id,
                "output": OpenAIAgentsStreamAdapter.text_from_content(message.content),
            },
        )

    @classmethod
    def assistant_items(cls, message: Message) -> list[TResponseInputItem]:
        """用于把 assistant 文本和工具调用拆成 Responses items。"""
        items: list[TResponseInputItem] = []
        text = cls.text_from_content(message.content)
        if text:
            items.append(cls.assistant_text_item(text))
        for block in message.content:
            if isinstance(block, ToolCall):
                items.append(cls.assistant_tool_item(block))
        return items

    @staticmethod
    def text_from_content(content: list[Any]) -> str:
        """用于从 pi-agent-core content block 拼接文本。"""
        return "".join(
            block.text for block in content if isinstance(block, TextContent) and block.text
        )

    @classmethod
    def text_message(
        cls,
        model: Model,
        text: str,
        usage: OpenAIAgentsUsage,
    ) -> AssistantMessage:
        """用于构建普通 assistant 文本消息。"""
        return AssistantMessage(
            api=model.api,
            provider=model.provider,
            model=model.id,
            content=[TextContent(text=text)] if text else [],
            stop_reason="stop",
            usage=cls.usage_to_pi_usage(usage),
        )

    @staticmethod
    def parse_tool_arguments(arguments: str) -> dict[str, Any]:
        """用于解析 SDK 工具参数 JSON。"""
        try:
            parsed = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return {"__tool_arguments_parse_error": arguments}
        return parsed if isinstance(parsed, dict) else {"value": parsed}

    @staticmethod
    def usage_to_pi_usage(usage: OpenAIAgentsUsage) -> Usage:
        """用于把 SDK usage 映射为 pi-agent-core usage。"""
        return Usage(
            input=usage.input_tokens,
            output=usage.output_tokens,
            total_tokens=usage.total_tokens,
        )

    @classmethod
    def text_delta_from_sdk_event(cls, event: Any) -> str:
        """用于从 SDK 原生 stream event 提取模型文本 delta。"""
        if not isinstance(event, RawResponsesStreamEvent):
            return ""
        data = event.data
        if str(getattr(data, "type", "") or "") != "response.output_text.delta":
            return ""
        return str(getattr(data, "delta", "") or "")

    @classmethod
    def text_delta_event_from_sdk_delta(cls, model: Model, delta: str) -> StreamTextDeltaEvent:
        """用于把 SDK 文本 delta 转成现有 ReAct loop 可消费的事件。"""
        partial = AssistantMessage(
            api=model.api,
            provider=model.provider,
            model=model.id,
            content=[TextContent(text=delta)],
            stop_reason="stop",
        )
        return StreamTextDeltaEvent(content_index=0, delta=delta, partial=partial)


class OpenAIAgentsStreamBridge:
    """用于把 SDK RunResultStreaming 桥接成现有 StreamResult 协议。"""

    _DONE = object()

    def __init__(
        self,
        adapter: OpenAIAgentsStreamAdapter,
        model: Model,
        context: AgentContext,
        options: SimpleStreamOptions,
    ):
        """用于启动后台 SDK streaming run 并保存桥接状态。"""
        self.adapter = adapter
        self.model = model
        self.context = context
        self.options = options
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.message: AssistantMessage | None = None
        self.task = asyncio.create_task(self.run())

    async def events(self) -> AsyncIterator[Any]:
        """用于把 SDK streaming delta 实时暴露给 ResumeAgentLoop。"""
        while True:
            item = await self.queue.get()
            if item is self._DONE:
                break
            if isinstance(item, BaseException):
                raise item
            yield item

    async def result(self) -> AssistantMessage:
        """用于等待 SDK run 完成并返回最终 assistant message。"""
        await self.task
        if self.message is None:
            return OpenAIAgentsStreamAdapter.text_message(
                self.model,
                "",
                OpenAIAgentsUsage(),
            )
        return self.message

    async def run(self) -> None:
        """用于执行 SDK streaming run、处理审批中断并完成最终消息。"""
        try:
            self.message = await self.run_until_final()
        except BaseException as exc:
            await self.queue.put(exc)
            raise
        finally:
            await self.queue.put(self._DONE)

    async def run_until_final(self) -> AssistantMessage:
        """用于按 SDK 官方 RunState 模式处理 streaming approval/resume。"""
        sdk_agent = self.adapter.build_sdk_agent(self.model, self.context, self.options)
        run_config = self.adapter.run_config(self.model, self.options)
        run_input: list[TResponseInputItem] | RunState[Any] = self.adapter.input_items(
            self.context.messages
        )
        streamed_text = ""
        usage = OpenAIAgentsUsage()

        while True:
            result = self.adapter.run_sdk_streamed(sdk_agent, run_input, run_config)
            async for event in result.stream_events():
                delta = self.adapter.text_delta_from_sdk_event(event)
                if not delta:
                    continue
                streamed_text += delta
                await self.queue.put(
                    self.adapter.text_delta_event_from_sdk_delta(self.model, delta)
                )

            usage = result.context_wrapper.usage
            if not result.interruptions:
                final_text = str(result.final_output or streamed_text or "")
                if final_text and not streamed_text:
                    await self.queue.put(
                        self.adapter.text_delta_event_from_sdk_delta(self.model, final_text)
                    )
                return self.adapter.text_message(self.model, final_text, usage)

            state = result.to_state()
            for interruption in result.interruptions:
                approved, rejection_message = await self.adapter.resolve_tool_approval(
                    self.context,
                    interruption,
                )
                if approved:
                    state.approve(interruption)
                else:
                    state.reject(interruption, rejection_message=rejection_message)
            run_input = state


__all__ = [
    "OpenAIAgentsStreamAdapter",
    "build_openai_agents_loop_config",
    "openai_agents_chat_model_name",
    "stream_openai_agents",
]
