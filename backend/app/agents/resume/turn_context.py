"""用于构建 Resume Agent 每轮 ReAct 输入和可用工具。"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from pi_agent_core import (
    AgentContext,
    AgentLoopConfig,
    AgentTool,
    AgentToolResult,
    AgentToolSchema,
    TextContent,
    UserMessage,
)
from pi_agent_core.types import Message

from app.agents.resume.tool_execution import ResumeToolExecutionStage
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.agents.resume.message_conversion import (
    resume_chat_history_to_messages,
)
from app.runtime.openai_agents_adapter import build_openai_agents_loop_config

class ResumeTurnContextBuilder:
    """用于按 Pi Harness 的 turn-state 边界准备模型上下文和工具。"""

    def __init__(self, *, tool_stage: ResumeToolExecutionStage):
        """用于保存工具执行阶段协作者。"""
        self.tool_stage = tool_stage

    def build_loop_inputs(
        self,
        *,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None,
        run_id: str,
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> tuple[AgentContext, list[Message], AgentLoopConfig]:
        """用于生成一次 ReAct loop 的上下文、prompt 和配置。"""
        context["user_message"] = user_message
        context["conversation_history"] = conversation_history or []
        context["confirmed_diff_items"] = stream_state["confirmed_diff_items"]
        tool_profile = self.tool_profile(agent, context)
        context["tool_profile"] = tool_profile
        tools_schema = self.profiled_tool_schemas(agent, tool_profile)
        context["available_tool_names"] = self.tool_names_from_schemas(tools_schema)
        prompt_context = agent.prompt_context_builder(context)
        system_prompt = agent.prompt_spec.render(**prompt_context)
        tools = self.build_tools(
            agent=agent,
            tools_schema=tools_schema,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            run_id=run_id,
            executed_tools=executed_tools,
            stream_state=stream_state,
        )
        pi_context = AgentContext(
            system_prompt=system_prompt,
            messages=self.history_messages(
                conversation_history,
                agent.max_history_messages,
            ),
            tools=tools,
        )
        stream_state["tool_profile"] = tool_profile
        stream_state["tool_names"] = self.tool_names_from_schemas(tools_schema)
        stream_state["prompt_chars"] = len(system_prompt)
        prompts: list[Message] = [UserMessage(content=[TextContent(text=user_message)])]
        config = build_openai_agents_loop_config(agent)
        stream_state["provider"] = config.model.provider
        stream_state["model"] = config.model.id
        return pi_context, prompts, config

    def build_tools(
        self,
        *,
        agent: AgentDefinition,
        tools_schema: list[dict[str, Any]],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        run_id: str,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> list[AgentTool]:
        """用于根据当前 profile 构建模型可见工具。"""
        tools: list[AgentTool] = []
        lock = asyncio.Lock()
        for schema in tools_schema:
            function = schema.get("function", {})
            tool_name = function.get("name")
            if not isinstance(tool_name, str) or not tool_name:
                continue
            tools.append(
                self.build_tool(
                    agent=agent,
                    tool_name=tool_name,
                    function=function,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    run_id=run_id,
                    executed_tools=executed_tools,
                    lock=lock,
                    stream_state=stream_state,
                )
            )
        return tools

    def build_tool(
        self,
        *,
        agent: AgentDefinition,
        tool_name: str,
        function: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        run_id: str,
        executed_tools: list[dict[str, Any]],
        lock: asyncio.Lock,
        stream_state: dict[str, Any],
    ) -> AgentTool:
        """用于构建单个 pi-agent-core 工具对象。"""

        async def execute(
            tool_call_id: str,
            params: dict[str, Any],
            *_args: Any,
        ) -> AgentToolResult:
            """用于执行一次 SDK 原生工具调用。"""
            stream_state["tool_call_count"] += 1
            if tool_name in agent.auto_execute_tool_names:
                return await self.tool_stage.execute_tool_result(
                    agent=agent,
                    run_id=run_id,
                    call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_input=params,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    executed_tools=executed_tools,
                    stream_state=stream_state,
                )
            async with lock:
                return await self.tool_stage.execute_tool_result(
                    agent=agent,
                    run_id=run_id,
                    call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_input=params,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    executed_tools=executed_tools,
                    stream_state=stream_state,
                )
        async def needs_sdk_approval(
            _run_context: Any,
            params: dict[str, Any],
            tool_call_id: str,
        ) -> bool:
            """用于把 SDK needs_approval 接入现有 dry-run 预览。"""
            if tool_name in agent.auto_execute_tool_names:
                return False
            async with lock:
                return await self.tool_stage.prepare_sdk_tool_approval(
                    agent=agent,
                    run_id=run_id,
                    call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_input=params,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    executed_tools=executed_tools,
                    stream_state=stream_state,
                )

        async def handle_sdk_approval(interruption: Any) -> tuple[bool, str | None]:
            """用于处理 SDK interruption 并等待前端确认。"""
            call_id = getattr(interruption, "call_id", None)
            if not isinstance(call_id, str) or not call_id:
                return True, None
            async with lock:
                return await self.tool_stage.handle_sdk_tool_approval(
                    agent=agent,
                    run_id=run_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    executed_tools=executed_tools,
                    stream_state=stream_state,
                )

        built_tool = AgentTool(
            name=tool_name,
            description=str(function.get("description", "")),
            parameters=self.tool_schema(function.get("parameters")),
            execute=execute,
        )
        setattr(built_tool, "_sdk_needs_approval", needs_sdk_approval)
        setattr(built_tool, "_sdk_handle_approval", handle_sdk_approval)
        return built_tool

    @staticmethod
    def tool_schema(value: Any) -> AgentToolSchema:
        """用于把 OpenAI tool schema 参数转为 pi-agent-core schema。"""
        if not isinstance(value, dict):
            return AgentToolSchema()
        properties = value.get("properties")
        required = value.get("required")
        return AgentToolSchema(
            type=str(value.get("type") or "object"),
            properties=properties if isinstance(properties, dict) else {},
            required=required if isinstance(required, list) else [],
        )

    @staticmethod
    def history_messages(
        conversation_history: list[dict[str, Any]] | None,
        max_history_messages: int,
    ) -> list[Message]:
        """用于把历史消息转为 pi-agent-core 消息，保留工具流水账。"""
        return resume_chat_history_to_messages((conversation_history or [])[-max_history_messages:])

    @staticmethod
    def tool_profile(agent: AgentDefinition, context: dict[str, Any]) -> str:
        """用于选择当前轮次实际使用的工具 profile。"""
        requested = context.get("tool_profile")
        if isinstance(requested, str) and requested in agent.tool_profiles:
            return requested
        return agent.default_tool_profile

    @staticmethod
    def profiled_tool_schemas(
        agent: AgentDefinition,
        tool_profile: str,
    ) -> list[dict[str, Any]]:
        """用于按工具 profile 过滤暴露给模型的工具 schema。"""
        allowed = agent.tool_profiles.get(tool_profile)
        if allowed is None:
            allowed = agent.tool_profiles.get(agent.default_tool_profile)
        if not allowed:
            return []
        return [
            deepcopy(schema)
            for schema in agent.tools_schema
            if schema.get("function", {}).get("name") in allowed
        ]

    @staticmethod
    def tool_names_from_schemas(schemas: list[dict[str, Any]]) -> list[str]:
        """用于从工具 schema 列表读取工具名。"""
        names: list[str] = []
        for schema in schemas:
            name = schema.get("function", {}).get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return names


__all__ = ["ResumeTurnContextBuilder"]
