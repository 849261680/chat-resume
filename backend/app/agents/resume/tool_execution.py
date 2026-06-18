"""用于承接 Resume Agent 的工具执行和确认阶段。"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from copy import deepcopy
from time import perf_counter
from typing import Any

from pi_agent_core import AgentToolResult, TextContent

from app.agents.resume.observability import increment_unique_counter
from app.agents.resume.stream_events import (
    text_delta_event,
    tool_call_event,
    tool_call_failed_event,
    tool_confirmed_event,
    tool_pending_event,
    tool_rejected_event,
    tool_result_event,
    user_input_request_event,
)
from app.agents.resume.event_publisher import publish_resume_runtime_event
from app.agents.resume.sdk_tool_lifecycle import SdkToolApprovalState
from app.agents.resume.tool_lifecycle import (
    ResumeToolLifecycleRequest,
    ResumeToolLifecycleRunner,
)
from app.infra.config import settings
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.runtime.tool_confirmation import ToolConfirmationPolicy
from app.types.stream import ResumeStreamEvent

logger = logging.getLogger("app.agents.resume.runtime")

_TOOL_ARGUMENTS_PARSE_ERROR_KEY = "__tool_arguments_parse_error"


class ResumeToolExecutionStage:
    """用于独立执行 Resume Agent 的工具调用、确认和结果事件。"""

    def __init__(self, confirmation_policy: ToolConfirmationPolicy | None = None):
        """用于初始化工具确认策略。"""
        self.confirmation_policy = confirmation_policy or ToolConfirmationPolicy()

    async def execute_lifecycle(
        self,
        request: ResumeToolLifecycleRequest,
    ) -> AgentToolResult:
        """用于通过单一请求对象执行完整工具调用生命周期。"""
        output = await ResumeToolLifecycleRunner(self, self.confirmation_policy).run(request)
        return AgentToolResult(
            content=[TextContent(text=output)],
            details=self.tool_result_details(output),
        )

    async def execute_tool_result(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> AgentToolResult:
        """用于执行工具并包装成 pi-agent-core 的工具结果。"""
        return await self.execute_lifecycle(
            ResumeToolLifecycleRequest(
                agent=agent,
                run_id=run_id,
                call_id=call_id,
                tool_name=tool_name,
                tool_input=tool_input,
                context=context,
                confirmation_queue=confirmation_queue,
                event_queue=event_queue,
                event_callback=event_callback,
                executed_tools=executed_tools,
                stream_state=stream_state,
            )
        )

    @staticmethod
    def tool_result_details(output: str) -> Any:
        """用于把 JSON 工具输出转换成可读的 details。"""
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            return output
        if isinstance(parsed, dict):
            return parsed
        return output

    async def execute_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> str:
        """用于执行一次完整工具调用生命周期。"""
        return await ResumeToolLifecycleRunner(self, self.confirmation_policy).run(
            ResumeToolLifecycleRequest(
                agent=agent,
                run_id=run_id,
                call_id=call_id,
                tool_name=tool_name,
                tool_input=tool_input,
                context=context,
                confirmation_queue=confirmation_queue,
                event_queue=event_queue,
                event_callback=event_callback,
                executed_tools=executed_tools,
                stream_state=stream_state,
            )
        )

    async def prepare_sdk_tool_approval(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> bool:
        """用于在 SDK needs_approval 阶段生成预览并决定是否中断。"""
        sdk_state = SdkToolApprovalState(context)
        if sdk_state.has_approved(call_id):
            return False
        decision = self.confirmation_policy.before_tool_call(
            confirmation_queue=confirmation_queue,
            tool_name=tool_name,
            auto_execute_tool_names=agent.auto_execute_tool_names,
        )
        if not decision.requires_confirmation:
            return False
        tool_started_at = perf_counter()
        tool_call = self.tool_call_payload(call_id, tool_name, tool_input)
        self.record_tool_requested(stream_state, call_id)
        self.trace_tool_requested(agent, run_id, call_id, tool_name, tool_input, True)
        preview_result = await self.sdk_preview_result(agent, tool_call, context)
        result = preview_result.get("result", {})
        self.trace_tool_preview(agent, run_id, call_id, tool_name, preview_result)
        if self.is_tool_failure(preview_result):
            await self.publish_sdk_preapproval_failure(
                agent=agent,
                run_id=run_id,
                call_id=call_id,
                tool_name=tool_name,
                tool_input=tool_input,
                context=context,
                event_queue=event_queue,
                event_callback=event_callback,
                executed_tools=executed_tools,
                stream_state=stream_state,
                tool_started_at=tool_started_at,
                tool_result=preview_result,
            )
            return False
        sdk_state.store_preview(
            call_id,
            {
                "tool_call": tool_call,
                "tool_input": tool_input,
                "tool_result": preview_result,
                "tool_started_at": tool_started_at,
                "diff_summary": preview_result.get("display_message") or "执行完成",
                "diff_items": result.get("diff_items", []) if isinstance(result, dict) else [],
            },
        )
        return True

    async def handle_sdk_tool_approval(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """用于把 SDK interruption 接到现有前端确认卡片。"""
        assert confirmation_queue is not None
        preview = SdkToolApprovalState(context).preview(call_id)
        if preview is None:
            return True, None
        tool_call = preview["tool_call"]
        tool_input = preview["tool_input"]
        preview_result = preview["tool_result"]
        await self.publish_visible_tool_call_once(
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            event_queue=event_queue,
            event_callback=event_callback,
            stream_state=stream_state,
        )
        await self.publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=tool_pending_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_call=tool_call,
                tool_display_name=preview_result["tool_name"],
                tool_input=tool_input,
                diff_summary=preview["diff_summary"],
                diff_items=preview["diff_items"],
                tool_calls=executed_tools,
            ),
        )
        wait_started_at = perf_counter()
        decision = await self.confirmation_policy.wait_for_decision(confirmation_queue)
        confirmation_wait_ms = round((perf_counter() - wait_started_at) * 1000, 2)
        stream_state["confirmation_wait_ms"] += confirmation_wait_ms
        confirmation_result = self.confirmation_policy.after_tool_decision(
            confirmed=decision.confirmed,
            feedback=decision.feedback,
        )
        self.trace_tool_confirmation(
            agent,
            run_id,
            call_id,
            tool_name,
            preview_result["tool_name"],
            confirmation_result.confirmed,
            confirmation_wait_ms,
            confirmation_result.terminate_turn,
        )
        if confirmation_result.confirmed:
            SdkToolApprovalState(context).mark_approved(call_id)
            return True, None
        rejected_error = "用户拒绝了此修改"
        if confirmation_result.feedback:
            rejected_error = f"用户拒绝了此修改，并反馈：{confirmation_result.feedback}"
        rejected = {
            "success": False,
            "error": rejected_error,
            "feedback": confirmation_result.feedback,
            "recoverable": True,
        }
        await self.publish_rejected_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=preview_result["tool_name"],
            diff_summary=preview["diff_summary"],
            diff_items=preview["diff_items"],
            result=rejected,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            tool_started_at=preview["tool_started_at"],
            stream_state=stream_state,
        )
        await self.publish_terminal_text(
            agent=agent,
            run_id=run_id,
            stream_state=stream_state,
            event_queue=event_queue,
            event_callback=event_callback,
            content=(
                "已收到反馈，我会重新生成修改。"
                if confirmation_result.feedback
                else "已取消这处修改。"
            ),
        )
        return False, rejected_error

    async def publish_invalid_tool_arguments(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        tool_started_at: float,
        stream_state: dict[str, Any],
    ) -> str:
        """用于把坏工具参数发布为可恢复工具错误。"""
        parse_error = tool_input.get(_TOOL_ARGUMENTS_PARSE_ERROR_KEY)
        message = self.invalid_tool_arguments_message(tool_name, parse_error)
        result = {
            "success": False,
            "error": {
                "type": "invalid_arguments_json",
                "message": message,
                "recoverable": True,
            },
            "message": message,
        }
        tool_result = {
            "tool_name": tool_name,
            "result": result,
            "display_message": message,
            "qr_image": None,
            "updated_section_name": None,
        }
        self.trace_tool_executed(
            agent,
            run_id,
            call_id,
            tool_name,
            tool_result,
            tool_started_at,
        )
        self.record_tool_executed(stream_state, call_id)
        executed_tools.append(self.executed_tool_summary(tool_result, result))
        await self.publish_tool_result(
            call_id=call_id,
            tool_name=tool_name,
            tool_result=tool_result,
            result=result,
            display_message=message,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            context=context,
            needs_confirmation=False,
        )
        return json.dumps(result, ensure_ascii=False)

    async def maybe_confirm_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_call: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        needs_confirmation: bool,
        tool_started_at: float,
        stream_state: dict[str, Any],
    ) -> dict[str, Any] | str | None:
        """用于在需要时预览工具 diff 并等待用户确认。"""
        if not needs_confirmation:
            return None
        assert confirmation_queue is not None
        preview_context = dict(context)
        preview_context["resume_content"] = deepcopy(context.get("resume_content"))
        preview_context["dry_run"] = True
        preview_result = await self.call_tool_executor(
            agent=agent,
            tool_call=tool_call,
            context=preview_context,
        )
        diff_summary = preview_result.get("display_message") or "执行完成"
        result = preview_result.get("result", {})
        diff_items = result.get("diff_items", []) if isinstance(result, dict) else []
        self.trace_tool_preview(agent, run_id, call_id, tool_name, preview_result)
        if self.is_tool_failure(preview_result):
            display_message = preview_result.get("display_message")
            self.trace_tool_executed(
                agent,
                run_id,
                call_id,
                tool_name,
                preview_result,
                tool_started_at,
            )
            self.record_tool_executed(stream_state, call_id)
            if self.is_noop_preview_failure(preview_result):
                return json.dumps(result, ensure_ascii=False)
            await self.publish_visible_tool_call_once(
                call_id=call_id,
                tool_name=tool_name,
                tool_input=tool_input,
                event_queue=event_queue,
                event_callback=event_callback,
                stream_state=stream_state,
            )
            executed_tools.append(self.executed_tool_summary(preview_result, result))
            await self.publish_tool_result(
                call_id=call_id,
                tool_name=tool_name,
                tool_result=preview_result,
                result=result,
                display_message=display_message,
                event_queue=event_queue,
                event_callback=event_callback,
                executed_tools=executed_tools,
                context=context,
                needs_confirmation=False,
            )
            return json.dumps(result, ensure_ascii=False)
        await self.publish_visible_tool_call_once(
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            event_queue=event_queue,
            event_callback=event_callback,
            stream_state=stream_state,
        )
        await self.publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=tool_pending_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_call=tool_call,
                tool_display_name=preview_result["tool_name"],
                tool_input=tool_input,
                diff_summary=diff_summary,
                diff_items=diff_items,
                tool_calls=executed_tools,
            ),
        )
        wait_started_at = perf_counter()
        decision = await self.confirmation_policy.wait_for_decision(confirmation_queue)
        confirmation_wait_ms = round((perf_counter() - wait_started_at) * 1000, 2)
        stream_state["confirmation_wait_ms"] += confirmation_wait_ms
        confirmation_result = self.confirmation_policy.after_tool_decision(
            confirmed=decision.confirmed,
            feedback=decision.feedback,
        )
        self.trace_tool_confirmation(
            agent,
            run_id,
            call_id,
            tool_name,
            preview_result["tool_name"],
            confirmation_result.confirmed,
            confirmation_wait_ms,
            confirmation_result.terminate_turn,
        )
        if confirmation_result.confirmed:
            return preview_result
        rejected_error = "用户拒绝了此修改"
        if confirmation_result.feedback:
            rejected_error = f"用户拒绝了此修改，并反馈：{confirmation_result.feedback}"
        rejected = {
            "success": False,
            "error": rejected_error,
            "feedback": confirmation_result.feedback,
            "recoverable": True,
        }
        await self.publish_rejected_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=preview_result["tool_name"],
            diff_summary=diff_summary,
            diff_items=diff_items,
            result=rejected,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            tool_started_at=tool_started_at,
            stream_state=stream_state,
        )
        await self.publish_terminal_text(
            agent=agent,
            run_id=run_id,
            stream_state=stream_state,
            event_queue=event_queue,
            event_callback=event_callback,
            content=(
                "已收到反馈，我会重新生成修改。"
                if confirmation_result.feedback
                else "已取消这处修改。"
            ),
        )
        return json.dumps(rejected, ensure_ascii=False)

    async def maybe_block_auto_execute_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_call: dict[str, Any],
        context: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        needs_confirmation: bool,
        tool_started_at: float,
    ) -> str | None:
        """用于兼容旧的免确认预执行扩展点。"""
        return None

    async def run_confirmed_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_call: dict[str, Any],
        context: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        needs_confirmation: bool,
        tool_started_at: float,
        stream_state: dict[str, Any],
    ) -> str:
        """用于执行已确认或免确认的业务工具。"""
        tool_result = await self.call_tool_executor(
            agent=agent,
            tool_call=tool_call,
            context=context,
        )
        result = tool_result.get("result", {})
        if needs_confirmation:
            self.remember_confirmed_diff_items(stream_state, result)
        display_message = tool_result.get("display_message")
        self.trace_tool_executed(
            agent,
            run_id,
            call_id,
            tool_name,
            tool_result,
            tool_started_at,
        )
        self.record_tool_executed(stream_state, call_id)
        if needs_confirmation:
            self.record_tool_confirmed(stream_state, call_id)
        executed_tools.append(self.executed_tool_summary(tool_result, result))
        await self.publish_tool_result(
            call_id=call_id,
            tool_name=tool_name,
            tool_result=tool_result,
            result=result,
            display_message=display_message,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            context=context,
            needs_confirmation=needs_confirmation,
        )
        return json.dumps(result, ensure_ascii=False)

    async def call_tool_executor(
        self,
        *,
        agent: AgentDefinition,
        tool_call: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """用于兼容同步和异步业务工具执行器。"""
        result = agent.tool_executor(tool_call, context)
        if inspect.isawaitable(result):
            return await result
        return result

    async def publish_terminal_text(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        stream_state: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        content: str,
    ) -> None:
        """用于在拒绝后发布确定性终止文本。"""
        stream_state["chunk_index"] += 1
        stream_state["response_parts"].append(content)
        self.trace_chunk(
            "agent.trace.intermediate.chunk",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            chunk_index=stream_state["chunk_index"],
            content_preview=self.preview_text(content),
            content_chars=len(content),
        )
        await self.publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=text_delta_event(content=content),
        )

    async def publish_visible_tool_call(
        self,
        *,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
    ) -> None:
        """用于发布可见的工具开始事件。"""
        tool_call = self.tool_call_payload(call_id, tool_name, tool_input)
        await self.publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=tool_call_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_call=tool_call,
                tool_display_name=tool_name,
                tool_input=tool_call["function"]["arguments"],
                display_message=f"正在{tool_name}",
                tool_calls=[],
            ),
        )
    async def publish_visible_tool_call_once(
        self,
        *,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        stream_state: dict[str, Any],
    ) -> None:
        """用于确保同一个工具调用最多发布一次开始事件。"""
        if not self.remember_visible_tool_call(stream_state, call_id):
            return
        await self.publish_visible_tool_call(
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            event_queue=event_queue,
            event_callback=event_callback,
        )

    async def publish_tool_result(
        self,
        *,
        call_id: str,
        tool_name: str,
        tool_result: dict[str, Any],
        result: Any,
        display_message: str | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        context: dict[str, Any],
        needs_confirmation: bool,
    ) -> None:
        """用于发布确认、失败或免确认工具结果。"""
        tool_display_name = str(tool_result.get("tool_name") or tool_name)
        if self.is_tool_failure(tool_result):
            event = tool_call_failed_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_display_name=tool_display_name,
                tool_calls=executed_tools,
                result=result,
                display_message=display_message,
            )
        elif needs_confirmation:
            event = tool_confirmed_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_display_name=tool_display_name,
                tool_calls=executed_tools,
                qr_images=[tool_result["qr_image"]] if tool_result.get("qr_image") else [],
                result=result,
                display_message=display_message,
                diff_summary=result.get("diff_summary") if isinstance(result, dict) else None,
                diff_items=result.get("diff_items", []) if isinstance(result, dict) else [],
                context=context,
            )
        elif isinstance(result, dict) and isinstance(result.get("user_input_request"), dict):
            event = user_input_request_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_display_name=tool_display_name,
                tool_calls=executed_tools,
                result=result,
                display_message=display_message,
            )
        else:
            event = tool_result_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_display_name=tool_display_name,
                tool_calls=executed_tools,
                result=result,
                display_message=display_message,
                context=context,
            )
        await self.publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=event,
        )

    async def publish_rejected_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_display_name: str,
        diff_summary: str,
        diff_items: Any,
        result: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        tool_started_at: float,
        stream_state: dict[str, Any],
    ) -> None:
        """用于发布用户拒绝工具事件。"""
        self.record_tool_rejected(stream_state, call_id)
        self.trace(
            "agent.trace.tool.rejected",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=tool_display_name,
            latency_ms=round((perf_counter() - tool_started_at) * 1000, 2),
        )
        await self.publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=tool_rejected_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_display_name=tool_display_name,
                diff_summary=diff_summary,
                diff_items=diff_items,
                result=result,
                tool_calls=executed_tools,
            ),
        )

    @staticmethod
    def record_tool_requested(stream_state: dict[str, Any], call_id: str) -> None:
        """用于记录唯一工具请求次数。"""
        increment_unique_counter(
            stream_state,
            bucket_key="_tool_requested_call_ids",
            value=call_id,
            counter_key="tool_requested_count",
        )

    @staticmethod
    def record_tool_executed(stream_state: dict[str, Any], call_id: str) -> None:
        """用于记录唯一工具执行次数。"""
        increment_unique_counter(
            stream_state,
            bucket_key="_tool_executed_call_ids",
            value=call_id,
            counter_key="tool_executed_count",
        )

    @staticmethod
    def record_tool_confirmed(stream_state: dict[str, Any], call_id: str) -> None:
        """用于记录唯一工具确认次数。"""
        increment_unique_counter(
            stream_state,
            bucket_key="_tool_confirmed_call_ids",
            value=call_id,
            counter_key="tool_confirmed_count",
        )

    @staticmethod
    def record_tool_rejected(stream_state: dict[str, Any], call_id: str) -> None:
        """用于记录唯一工具拒绝次数。"""
        increment_unique_counter(
            stream_state,
            bucket_key="_tool_rejected_call_ids",
            value=call_id,
            counter_key="tool_rejected_count",
        )

    def trace_tool_requested(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        needs_confirmation: bool,
    ) -> None:
        """用于记录工具请求摘要。"""
        self.trace(
            "agent.trace.tool.requested",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_input=self.safe_tool_input(tool_input),
            requires_confirmation=needs_confirmation,
        )

    def trace_tool_preview(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        preview_result: dict[str, Any],
    ) -> None:
        """用于记录工具预览结果。"""
        result = preview_result.get("result", {})
        diff_items = result.get("diff_items", []) if isinstance(result, dict) else []
        result_success = self.tool_success(preview_result)
        message = (
            "agent.trace.tool.preview_failed"
            if result_success is False
            else "agent.trace.tool.preview"
        )
        self.trace(
            message,
            log_level=logging.WARNING if result_success is False else logging.INFO,
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=preview_result["tool_name"],
            diff_summary=self.preview_text(preview_result.get("display_message")),
            diff_item_count=len(diff_items),
            result_success=result_success,
        )

    def trace_tool_confirmation(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        display_name: str,
        confirmed: bool,
        confirmation_wait_ms: float,
        terminate_turn: bool,
    ) -> None:
        """用于记录工具确认结果。"""
        self.trace(
            "agent.trace.tool.confirmation",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=display_name,
            confirmed=confirmed,
            confirmation_wait_ms=confirmation_wait_ms,
            terminate_turn=terminate_turn,
        )

    async def sdk_preview_result(
        self,
        agent: AgentDefinition,
        tool_call: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """用于为 SDK HITL 生成不落库的工具预览。"""
        preview_context = dict(context)
        preview_context["resume_content"] = deepcopy(context.get("resume_content"))
        preview_context["dry_run"] = True
        return await self.call_tool_executor(
            agent=agent,
            tool_call=tool_call,
            context=preview_context,
        )

    async def publish_sdk_preapproval_failure(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
        tool_started_at: float,
        tool_result: dict[str, Any],
    ) -> None:
        """用于把 SDK 审批前失败转成模型可恢复输出和必要前端事件。"""
        result = tool_result.get("result", {})
        output = json.dumps(result, ensure_ascii=False)
        SdkToolApprovalState(context).store_preapproval_output(call_id, output)
        self.trace_tool_executed(agent, run_id, call_id, tool_name, tool_result, tool_started_at)
        if self.is_noop_preview_failure(tool_result):
            return
        await self.publish_visible_tool_call_once(
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            event_queue=event_queue,
            event_callback=event_callback,
            stream_state=stream_state,
        )
        executed_tools.append(self.executed_tool_summary(tool_result, result))
        await self.publish_tool_result(
            call_id=call_id,
            tool_name=tool_name,
            tool_result=tool_result,
            result=result,
            display_message=tool_result.get("display_message"),
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            context=context,
            needs_confirmation=False,
        )

    def trace_tool_executed(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_result: dict[str, Any],
        tool_started_at: float,
    ) -> None:
        """用于记录工具执行结果。"""
        self.trace(
            "agent.trace.tool.executed",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=tool_result["tool_name"],
            result_success=self.tool_success(tool_result),
            display_message=self.preview_text(tool_result.get("display_message")),
            result_summary=self.result_summary(tool_result.get("result", {})),
            latency_ms=round((perf_counter() - tool_started_at) * 1000, 2),
        )

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
    def remember_visible_tool_call(state: dict[str, Any], call_id: str) -> bool:
        """用于记录工具调用是否已经展示。"""
        visible_call_ids = state.setdefault("visible_tool_call_ids", set())
        if call_id in visible_call_ids:
            return False
        visible_call_ids.add(call_id)
        return True

    @staticmethod
    def tool_call_payload(
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        """用于构建前端和工具执行器共享的工具调用载荷。"""
        return {
            "id": call_id,
            "type": "function",
            "function": {"name": tool_name, "arguments": tool_input},
        }

    @staticmethod
    def executed_tool_summary(
        tool_result: dict[str, Any],
        result: Any,
    ) -> dict[str, Any]:
        """用于生成已执行工具的短摘要。"""
        return {
            "name": tool_result["tool_name"],
            "result": result.get("diff_summary") if isinstance(result, dict) else tool_result.get("display_message"),
            "success": result.get("success") if isinstance(result, dict) else None,
        }

    @staticmethod
    def remember_confirmed_diff_items(
        stream_state: dict[str, Any],
        result: Any,
    ) -> None:
        """用于把已确认 diff 传给后续只读摘要工具。"""
        if not isinstance(result, dict) or result.get("success") is False:
            return
        diff_items = result.get("diff_items")
        if not isinstance(diff_items, list):
            return
        confirmed = stream_state.get("confirmed_diff_items")
        if isinstance(confirmed, list):
            confirmed.extend(item for item in diff_items if isinstance(item, dict))

    @staticmethod
    def is_tool_failure(tool_result: dict[str, Any]) -> bool:
        """用于判断工具结果是否失败。"""
        result = tool_result.get("result")
        return isinstance(result, dict) and result.get("success") is False
    @staticmethod
    def is_noop_preview_failure(tool_result: dict[str, Any]) -> bool:
        """用于识别不会落库的同文改写失败，避免污染用户工具卡片。"""
        result = tool_result.get("result")
        message = tool_result.get("display_message")
        if isinstance(result, dict):
            message = result.get("message") or result.get("error") or message
        return isinstance(message, str) and "新旧" in message and "未执行修改" in message

    @staticmethod
    def has_tool_argument_parse_error(tool_input: dict[str, Any]) -> bool:
        """用于判断工具参数是否来自 provider JSON 解析错误。"""
        return isinstance(tool_input.get(_TOOL_ARGUMENTS_PARSE_ERROR_KEY), dict)

    @classmethod
    def invalid_tool_arguments_message(cls, tool_name: str, parse_error: Any) -> str:
        """用于生成可回灌给模型的坏参数错误信息。"""
        detail = ""
        if isinstance(parse_error, dict):
            detail = cls.preview_text(parse_error.get("message"))
        if detail:
            return f"{tool_name} 工具参数不是合法 JSON，无法执行：{detail}"
        return f"{tool_name} 工具参数不是合法 JSON，无法执行。"

    @staticmethod
    def tool_success(tool_result: dict[str, Any]) -> bool | None:
        """用于读取工具结果里的成功状态。"""
        result = tool_result.get("result")
        if isinstance(result, dict) and "success" in result:
            return bool(result["success"])
        return None

    @classmethod
    def result_summary(cls, result: Any) -> dict[str, Any]:
        """用于生成日志友好的工具结果摘要。"""
        if not isinstance(result, dict):
            return {"type": type(result).__name__, "preview": cls.preview_text(result)}
        summary: dict[str, Any] = {"keys": sorted(str(key) for key in result.keys())}
        if "success" in result:
            summary["success"] = result.get("success")
        if "diff_summary" in result:
            summary["diff_summary"] = cls.preview_text(result.get("diff_summary"))
        if isinstance(result.get("diff_items"), list):
            summary["diff_item_count"] = len(result["diff_items"])
        if "error" in result:
            summary["error"] = cls.preview_text(result.get("error"))
        return summary

    @classmethod
    def safe_tool_input(cls, tool_input: dict[str, Any]) -> dict[str, Any]:
        """用于避免日志记录完整简历或长文本。"""
        summary: dict[str, Any] = {}
        for key, value in tool_input.items():
            if key in {"resume_content", "content"}:
                continue
            if key == "text" and isinstance(value, str):
                summary["text_chars"] = len(value)
                summary["text_preview"] = cls.preview_text(value, limit=80)
                continue
            if key == "reason" and isinstance(value, str):
                summary[key] = cls.preview_text(value, limit=80)
                continue
            summary[key] = cls.summarize_value(value)
        return summary

    @classmethod
    def summarize_value(cls, value: Any) -> Any:
        """用于压缩日志字段值。"""
        if isinstance(value, str):
            return cls.preview_text(value)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return {"type": "list", "count": len(value)}
        if isinstance(value, dict):
            return {"type": "dict", "keys": sorted(str(key) for key in value.keys())[:20]}
        return {"type": type(value).__name__, "preview": cls.preview_text(value)}

    @staticmethod
    def preview_text(value: Any, limit: int = 240) -> str:
        """用于生成短文本预览。"""
        if value is None:
            return ""
        text = " ".join(str(value).split())
        if len(text) <= limit:
            return text
        return f"{text[:limit]}..."

    @staticmethod
    def trace(message: str, **fields: Any) -> None:
        """用于写入 Agent trace 日志。"""
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


__all__ = ["ResumeToolExecutionStage"]
