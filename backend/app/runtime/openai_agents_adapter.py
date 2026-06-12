"""用于把 OpenAI Agents SDK 原生工具循环适配到 Resume Agent 运行时。"""

from __future__ import annotations

import inspect
import json
from collections.abc import AsyncIterator
from typing import Any, cast

from agents import Agent as OpenAIAgent
from agents import FunctionTool, ModelSettings, RunConfig, Runner, ToolsToFinalOutputResult
from agents.items import TResponseInputItem, ToolApprovalItem
from agents.models.interface import Model as OpenAIAgentsModel
from agents.models.openai_provider import OpenAIProvider
from agents.usage import Usage as OpenAIAgentsUsage
from openai.types.responses import ResponseFunctionToolCall
from pi_agent_core import (
    AgentContext,
    AgentLoopConfig,
    AssistantMessage,
    Model,
    SimpleStreamOptions,
    StreamDoneEvent,
    StreamResult,
    StreamStartEvent,
    StreamTextDeltaEvent,
    StreamTextEndEvent,
    StreamTextStartEvent,
    StreamToolCallEndEvent,
    StreamToolCallStartEvent,
    TextContent,
    ToolCall,
    Usage,
)
from pi_agent_core.types import Message

from app.agents.resume.message_conversion import convert_resume_messages_to_llm
from app.infra.config import settings
from app.runtime.contracts import AgentDefinition
from app.runtime.openai_agents_eval import current_openai_agents_trace_config

OPENAI_AGENTS_PROVIDER_OPENAI = "openai"
OPENAI_AGENTS_PROVIDER_DEEPSEEK = "deepseek"
OPENAI_AGENTS_MODEL_PROVIDER_OPENAI = "openai-agents"


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
        message = await self.run_sdk_turn(model, context, options)
        events = self.events_for_message(message)

        async def events_iter() -> AsyncIterator[Any]:
            """用于按顺序回放转换后的单轮事件。"""
            for event in events:
                yield event

        async def result() -> AssistantMessage:
            """用于返回单轮最终 assistant message。"""
            return message

        return {"events": events_iter(), "result": result}

    async def run_sdk_turn(
        self,
        model: Model,
        context: AgentContext,
        options: SimpleStreamOptions,
    ) -> AssistantMessage:
        """用于构建 SDK Agent，并让 SDK 原生驱动工具调用直到最终回复。"""
        sdk_agent = self.build_sdk_agent(model, context, options)
        run_config = self.run_config(model, options)
        result = await Runner.run(
            sdk_agent,
            self.input_items(context.messages),
            max_turns=10,
            run_config=run_config,
        )
        return self.text_message(model, str(result.final_output or ""), result.context_wrapper.usage)

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
            return RunConfig()
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
            params = OpenAIAgentsStreamAdapter.parse_tool_arguments(raw_input)
            result = tool.execute(tool_context.tool_call_id, params)
            if inspect.isawaitable(result):
                result = await result
            if result is None:
                return ""
            return OpenAIAgentsStreamAdapter.text_from_content(result.content)
        return FunctionTool(
            name=str(tool.name),
            description=str(tool.description),
            params_json_schema={
                "type": str(tool.parameters.type or "object"),
                "properties": dict(tool.parameters.properties or {}),
                "required": list(tool.parameters.required or []),
            },
            on_invoke_tool=on_invoke_tool,
            strict_json_schema=False,
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

    @staticmethod
    def first_interrupted_tool_call(
        interruptions: list[ToolApprovalItem],
    ) -> ResponseFunctionToolCall | None:
        """用于读取 SDK approval interruption 中的第一个函数工具调用。"""
        for interruption in interruptions:
            raw_item = interruption.raw_item
            if isinstance(raw_item, ResponseFunctionToolCall):
                return raw_item
        return None

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

    @classmethod
    def tool_call_message(
        cls,
        model: Model,
        tool_call: ResponseFunctionToolCall,
        usage: OpenAIAgentsUsage,
    ) -> AssistantMessage:
        """用于构建包含工具调用的 assistant 消息。"""
        return AssistantMessage(
            api=model.api,
            provider=model.provider,
            model=model.id,
            content=[
                ToolCall(
                    id=tool_call.call_id,
                    name=tool_call.name,
                    arguments=cls.parse_tool_arguments(tool_call.arguments),
                )
            ],
            stop_reason="toolUse",
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
    def events_for_message(cls, message: AssistantMessage) -> list[Any]:
        """用于把完整 assistant message 转换成现有流式事件。"""
        events: list[Any] = [StreamStartEvent(partial=message)]
        for index, block in enumerate(message.content):
            events.extend(cls.events_for_block(index, block, message))
        events.append(StreamDoneEvent(reason=message.stop_reason, message=message))
        return events

    @staticmethod
    def events_for_block(index: int, block: Any, message: AssistantMessage) -> list[Any]:
        """用于把单个 assistant content block 转换成事件列表。"""
        if isinstance(block, TextContent):
            return [
                StreamTextStartEvent(content_index=index, partial=message),
                StreamTextDeltaEvent(content_index=index, delta=block.text, partial=message),
                StreamTextEndEvent(content_index=index, content=block.text, partial=message),
            ]
        if isinstance(block, ToolCall):
            return [
                StreamToolCallStartEvent(content_index=index, partial=message),
                StreamToolCallEndEvent(content_index=index, tool_call=block, partial=message),
            ]
        return []


__all__ = [
    "OpenAIAgentsStreamAdapter",
    "build_openai_agents_loop_config",
    "openai_agents_chat_model_name",
    "stream_openai_agents",
]
