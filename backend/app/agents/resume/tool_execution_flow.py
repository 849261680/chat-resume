"""用于封装 Resume 工具调用开始后的执行流。"""

from __future__ import annotations

from typing import Any

from app.agents.resume.tool_lifecycle import (
    ResumeToolLifecycleRequest,
    ResumeToolLifecycleStart,
)


class ResumeToolExecutionFlow:
    """用于隐藏工具预览、确认、可见事件和最终输出的执行顺序。"""

    def __init__(self, operations: Any):
        """用于绑定底层工具操作实现。"""
        self.operations = operations

    async def run_sdk_approved(
        self,
        request: ResumeToolLifecycleRequest,
        lifecycle_start: ResumeToolLifecycleStart,
    ) -> str:
        """用于执行 SDK 已确认的工具调用。"""
        operations = self.operations
        operations.record_tool_requested(request.stream_state, request.call_id)
        operations.trace_tool_requested(
            request.agent,
            request.run_id,
            request.call_id,
            request.tool_name,
            request.tool_input,
            True,
        )
        return await operations.run_confirmed_tool(
            agent=request.agent,
            run_id=request.run_id,
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_call=lifecycle_start.tool_call,
            context=request.context,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            executed_tools=request.executed_tools,
            needs_confirmation=True,
            tool_started_at=lifecycle_start.tool_started_at,
            stream_state=request.stream_state,
        )

    async def run_requested(
        self,
        request: ResumeToolLifecycleRequest,
        lifecycle_start: ResumeToolLifecycleStart,
    ) -> str:
        """用于执行普通 requested 工具调用的预览、确认和执行分支。"""
        operations = self.operations
        operations.record_tool_requested(request.stream_state, request.call_id)
        operations.trace_tool_requested(
            request.agent,
            request.run_id,
            request.call_id,
            request.tool_name,
            request.tool_input,
            lifecycle_start.needs_confirmation,
        )
        if operations.has_tool_argument_parse_error(request.tool_input):
            return await self.run_invalid_arguments(request, lifecycle_start)
        return await self.run_valid_arguments(request, lifecycle_start)

    async def run_invalid_arguments(
        self,
        request: ResumeToolLifecycleRequest,
        lifecycle_start: ResumeToolLifecycleStart,
    ) -> str:
        """用于发布坏工具参数的可见事件和可恢复结果。"""
        operations = self.operations
        await operations.publish_visible_tool_call_once(
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_input=request.tool_input,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            stream_state=request.stream_state,
        )
        return await operations.publish_invalid_tool_arguments(
            agent=request.agent,
            run_id=request.run_id,
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_input=request.tool_input,
            context=request.context,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            executed_tools=request.executed_tools,
            tool_started_at=lifecycle_start.tool_started_at,
            stream_state=request.stream_state,
        )

    async def run_valid_arguments(
        self,
        request: ResumeToolLifecycleRequest,
        lifecycle_start: ResumeToolLifecycleStart,
    ) -> str:
        """用于执行参数合法工具的确认和最终工具输出。"""
        operations = self.operations
        preview = await operations.maybe_confirm_tool(
            agent=request.agent,
            run_id=request.run_id,
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_input=request.tool_input,
            tool_call=lifecycle_start.tool_call,
            context=request.context,
            confirmation_queue=request.confirmation_queue,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            executed_tools=request.executed_tools,
            needs_confirmation=lifecycle_start.needs_confirmation,
            tool_started_at=lifecycle_start.tool_started_at,
            stream_state=request.stream_state,
        )
        if not lifecycle_start.needs_confirmation:
            await operations.publish_visible_tool_call_once(
                call_id=request.call_id,
                tool_name=request.tool_name,
                tool_input=request.tool_input,
                event_queue=request.event_queue,
                event_callback=request.event_callback,
                stream_state=request.stream_state,
            )
        auto_quality_failure = await operations.maybe_block_auto_execute_tool(
            agent=request.agent,
            run_id=request.run_id,
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_input=request.tool_input,
            tool_call=lifecycle_start.tool_call,
            context=request.context,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            executed_tools=request.executed_tools,
            needs_confirmation=lifecycle_start.needs_confirmation,
            tool_started_at=lifecycle_start.tool_started_at,
        )
        if isinstance(auto_quality_failure, str):
            return auto_quality_failure
        if isinstance(preview, str):
            return preview
        return await operations.run_confirmed_tool(
            agent=request.agent,
            run_id=request.run_id,
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_call=lifecycle_start.tool_call,
            context=request.context,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            executed_tools=request.executed_tools,
            needs_confirmation=lifecycle_start.needs_confirmation,
            tool_started_at=lifecycle_start.tool_started_at,
            stream_state=request.stream_state,
        )


__all__ = ["ResumeToolExecutionFlow"]
