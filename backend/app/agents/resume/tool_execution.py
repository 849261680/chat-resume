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
from app.infra.config import settings
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.runtime.tool_confirmation import ToolConfirmationPolicy
from app.agents.resume.quality_gate import evaluate_resume_edit_quality
from app.types.stream import ResumeStreamEvent

logger = logging.getLogger("app.agents.resume.runtime")

_TOOL_ARGUMENTS_PARSE_ERROR_KEY = "__tool_arguments_parse_error"


class ResumeToolExecutionStage:
    """用于独立执行 Resume Agent 的工具调用、确认和结果事件。"""

    def __init__(self, confirmation_policy: ToolConfirmationPolicy | None = None):
        """用于初始化工具确认策略。"""
        self.confirmation_policy = confirmation_policy or ToolConfirmationPolicy()

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
        output = await self.execute_tool(
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
        return AgentToolResult(
            content=[TextContent(text=output)],
            details=self.tool_result_details(output),
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
        tool_started_at = perf_counter()
        confirmation_decision = self.confirmation_policy.before_tool_call(
            confirmation_queue=confirmation_queue,
            tool_name=tool_name,
            auto_execute_tool_names=agent.auto_execute_tool_names,
        )
        needs_confirmation = confirmation_decision.requires_confirmation
        tool_call = self.tool_call_payload(call_id, tool_name, tool_input)
        if self.remember_visible_tool_call(stream_state, call_id):
            await self.publish_visible_tool_call(
                call_id=call_id,
                tool_name=tool_name,
                tool_input=tool_input,
                event_queue=event_queue,
                event_callback=event_callback,
            )
        self.trace_tool_requested(
            agent,
            run_id,
            call_id,
            tool_name,
            tool_input,
            needs_confirmation,
        )
        if self.has_tool_argument_parse_error(tool_input):
            return await self.publish_invalid_tool_arguments(
                agent=agent,
                run_id=run_id,
                call_id=call_id,
                tool_name=tool_name,
                tool_input=tool_input,
                context=context,
                event_queue=event_queue,
                event_callback=event_callback,
                executed_tools=executed_tools,
                tool_started_at=tool_started_at,
            )
        preview = await self.maybe_confirm_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_call=tool_call,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            needs_confirmation=needs_confirmation,
            tool_started_at=tool_started_at,
            stream_state=stream_state,
        )
        if isinstance(preview, str):
            return preview
        return await self.run_confirmed_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_call=tool_call,
            context=context,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            needs_confirmation=needs_confirmation,
            tool_started_at=tool_started_at,
            stream_state=stream_state,
        )

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
        quality_failure = self.quality_gate_failure(
            tool_name=tool_name,
            tool_input=tool_input,
            context=context,
            preview_result=preview_result,
        )
        if quality_failure is not None:
            self.trace_tool_executed(
                agent,
                run_id,
                call_id,
                tool_name,
                quality_failure,
                tool_started_at,
            )
            quality_result = quality_failure["result"]
            executed_tools.append(self.executed_tool_summary(quality_failure, quality_result))
            await self.publish_tool_result(
                call_id=call_id,
                tool_name=tool_name,
                tool_result=quality_failure,
                result=quality_result,
                display_message=quality_failure.get("display_message"),
                event_queue=event_queue,
                event_callback=event_callback,
                executed_tools=executed_tools,
                context=context,
                needs_confirmation=False,
            )
            return json.dumps(quality_result, ensure_ascii=False)
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
        if tool_name == "score_resume":
            context["score_history"] = context.get("score_snapshots") or []
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
        executed_tools.append(self.executed_tool_summary(tool_result, result))
        self.maybe_record_score_snapshot(tool_name, result, executed_tools, context)
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
    ) -> None:
        """用于发布用户拒绝工具事件。"""
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
    def maybe_record_score_snapshot(
        tool_name: str,
        result: Any,
        executed_tools: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> None:
        """用于在 score_resume 工具成功时把分数快照追加到 context。"""
        del executed_tools
        if tool_name != "score_resume":
            return
        if not isinstance(result, dict) or result.get("success") is not True:
            return
        snapshot = {
            "total_score": result.get("total_score"),
            "grade": result.get("grade"),
            "note": result.get("diagnosis", {}).get("verdict", ""),
        }
        snapshots = context.setdefault("score_snapshots", [])
        snapshots.append(snapshot)

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

    @staticmethod
    def quality_gate_failure(
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        preview_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        """用于把质量门禁未通过结果转换成工具失败载荷。"""
        resume_content = context.get("resume_content")
        if not isinstance(resume_content, dict):
            return None
        gate = evaluate_resume_edit_quality(
            resume_content=resume_content,
            tool_name=tool_name,
            tool_input=tool_input,
            preview_result=preview_result.get("result", {}),
            user_message=str(context.get("user_message") or ""),
        )
        if gate.get("passed") is True:
            return None
        message = str(gate.get("message") or "这次改写没有通过简历质量门禁。")
        result = {
            "success": False,
            "error": {
                "type": str(gate.get("error_type") or "resume_quality_gate_failed"),
                "message": message,
                "recoverable": bool(gate.get("recoverable", True)),
            },
            "message": message,
            "unsupported_claims": gate.get("unsupported_claims", []),
        }
        return {
            "tool_name": str(preview_result.get("tool_name") or tool_name),
            "result": result,
            "display_message": message,
            "qr_image": None,
            "updated_section_name": None,
        }

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
