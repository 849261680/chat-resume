"""用于收口一次 Resume 工具调用 transaction 的执行顺序。"""

from __future__ import annotations

from typing import Any

from app.agents.resume.tool_lifecycle import (
    ResumeToolLifecycleRequest,
    ResumeToolLifecycleStart,
)


class ResumeToolTransaction:
    """用于隐藏工具调用的预览、确认、闸口和执行顺序。"""

    def __init__(
        self,
        *,
        operations: Any,
        request: ResumeToolLifecycleRequest,
        lifecycle_start: ResumeToolLifecycleStart,
    ):
        """用于绑定工具操作实现、生命周期请求和开始状态。"""
        self.operations = operations
        self.request = request
        self.lifecycle_start = lifecycle_start

    async def run_requested(self) -> str:
        """用于执行普通 requested 工具调用 transaction。"""
        self.record_requested_tool()
        if self.operations.has_tool_argument_parse_error(self.request.tool_input):
            return await self.run_invalid_arguments()
        return await self.run_valid_arguments()

    async def run_sdk_approved(self) -> str:
        """用于执行 SDK 已确认后的工具调用 transaction。"""
        self.record_requested_tool(needs_confirmation=True)
        return await self.run_confirmed_tool(needs_confirmation=True)

    def record_requested_tool(self, needs_confirmation: bool | None = None) -> None:
        """用于记录 requested 阶段的计数和 trace。"""
        request = self.request
        confirmation = self.lifecycle_start.needs_confirmation
        if needs_confirmation is not None:
            confirmation = needs_confirmation
        self.operations.record_tool_requested(request.stream_state, request.call_id)
        self.operations.trace_tool_requested(
            request.agent,
            request.run_id,
            request.call_id,
            request.tool_name,
            request.tool_input,
            confirmation,
        )

    async def run_invalid_arguments(self) -> str:
        """用于发布坏参数工具调用并返回可恢复错误输出。"""
        request = self.request
        await self.operations.publish_visible_tool_call_once(
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_input=request.tool_input,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            stream_state=request.stream_state,
        )
        return await self.operations.publish_invalid_tool_arguments(
            agent=request.agent,
            run_id=request.run_id,
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_input=request.tool_input,
            context=request.context,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            executed_tools=request.executed_tools,
            tool_started_at=self.lifecycle_start.tool_started_at,
            stream_state=request.stream_state,
        )

    async def run_valid_arguments(self) -> str:
        """用于执行参数合法工具的确认和最终工具输出。"""
        preview = await self.preview_or_wait_for_confirmation()
        if not self.lifecycle_start.needs_confirmation:
            await self.publish_auto_visible_tool_call()
        auto_quality_failure = await self.maybe_block_auto_execute_tool()
        if isinstance(auto_quality_failure, str):
            return auto_quality_failure
        if isinstance(preview, str):
            return preview
        return await self.run_confirmed_tool()

    async def preview_or_wait_for_confirmation(self) -> dict[str, Any] | str | None:
        """用于在需要用户确认时生成预览并等待确认结果。"""
        request = self.request
        return await self.operations.maybe_confirm_tool(
            agent=request.agent,
            run_id=request.run_id,
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_input=request.tool_input,
            tool_call=self.lifecycle_start.tool_call,
            context=request.context,
            confirmation_queue=request.confirmation_queue,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            executed_tools=request.executed_tools,
            needs_confirmation=self.lifecycle_start.needs_confirmation,
            tool_started_at=self.lifecycle_start.tool_started_at,
            stream_state=request.stream_state,
        )

    async def publish_auto_visible_tool_call(self) -> None:
        """用于为免确认工具发布一次可见工具调用。"""
        request = self.request
        await self.operations.publish_visible_tool_call_once(
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_input=request.tool_input,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            stream_state=request.stream_state,
        )

    async def maybe_block_auto_execute_tool(self) -> str | None:
        """用于执行自动工具的质量闸口扩展点。"""
        request = self.request
        return await self.operations.maybe_block_auto_execute_tool(
            agent=request.agent,
            run_id=request.run_id,
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_input=request.tool_input,
            tool_call=self.lifecycle_start.tool_call,
            context=request.context,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            executed_tools=request.executed_tools,
            needs_confirmation=self.lifecycle_start.needs_confirmation,
            tool_started_at=self.lifecycle_start.tool_started_at,
        )

    async def run_confirmed_tool(self, needs_confirmation: bool | None = None) -> str:
        """用于执行已确认或免确认的最终工具调用。"""
        request = self.request
        confirmation = self.lifecycle_start.needs_confirmation
        if needs_confirmation is not None:
            confirmation = needs_confirmation
        return await self.operations.run_confirmed_tool(
            agent=request.agent,
            run_id=request.run_id,
            call_id=request.call_id,
            tool_name=request.tool_name,
            tool_call=self.lifecycle_start.tool_call,
            context=request.context,
            event_queue=request.event_queue,
            event_callback=request.event_callback,
            executed_tools=request.executed_tools,
            needs_confirmation=confirmation,
            tool_started_at=self.lifecycle_start.tool_started_at,
            stream_state=request.stream_state,
        )


__all__ = ["ResumeToolTransaction"]
