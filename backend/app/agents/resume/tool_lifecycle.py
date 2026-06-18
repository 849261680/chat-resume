"""用于定义一次 Resume 工具调用生命周期的公开请求对象。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.agents.resume.sdk_tool_lifecycle import SdkToolApprovalState
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.runtime.tool_confirmation import ToolConfirmationPolicy


@dataclass(slots=True)
class ResumeToolLifecycleRequest:
    """用于把一次工具调用生命周期所需上下文收敛成单一接口。"""

    agent: AgentDefinition
    run_id: str
    call_id: str
    tool_name: str
    tool_input: dict[str, Any]
    context: dict[str, Any]
    confirmation_queue: asyncio.Queue[Any] | None
    event_queue: asyncio.Queue[Any] | None
    event_callback: RuntimeEventCallback | None
    executed_tools: list[dict[str, Any]]
    stream_state: dict[str, Any]


@dataclass(slots=True)
class ResumeToolLifecycleStart:
    """用于描述一次工具调用生命周期的开始阶段决策。"""

    tool_started_at: float
    tool_call: dict[str, Any]
    needs_confirmation: bool
    preapproval_output: str | None
    sdk_approved: bool


class ResumeToolLifecycleRunner:
    """用于编排一次 Resume 工具调用从 requested 到 executed 的生命周期。"""

    def __init__(self, operations: Any, confirmation_policy: ToolConfirmationPolicy):
        """用于绑定底层工具操作和确认策略。"""
        self.operations = operations
        self.confirmation_policy = confirmation_policy

    async def run(self, request: ResumeToolLifecycleRequest) -> str:
        """用于运行完整工具生命周期并返回工具输出。"""
        operations = self.operations
        tool_call = operations.tool_call_payload(
            request.call_id,
            request.tool_name,
            request.tool_input,
        )
        lifecycle_start = begin_resume_tool_lifecycle(
            request,
            confirmation_policy=self.confirmation_policy,
            tool_call=tool_call,
        )
        if lifecycle_start.preapproval_output is not None:
            return lifecycle_start.preapproval_output
        if lifecycle_start.sdk_approved:
            return await self.operations.run_sdk_approved_tool_call(request, lifecycle_start)
        return await self.operations.run_requested_tool_call(request, lifecycle_start)


def begin_resume_tool_lifecycle(
    request: ResumeToolLifecycleRequest,
    *,
    confirmation_policy: ToolConfirmationPolicy,
    tool_call: dict[str, Any],
) -> ResumeToolLifecycleStart:
    """用于集中计算 requested 阶段的确认、SDK 审批和预审批状态。"""
    confirmation_decision = confirmation_policy.before_tool_call(
        confirmation_queue=request.confirmation_queue,
        tool_name=request.tool_name,
        auto_execute_tool_names=request.agent.auto_execute_tool_names,
    )
    sdk_state = SdkToolApprovalState(request.context)
    preapproval_output = sdk_state.pop_preapproval_output(request.call_id)
    sdk_approved = False if preapproval_output is not None else sdk_state.consume_approved(request.call_id)
    return ResumeToolLifecycleStart(
        tool_started_at=perf_counter(),
        tool_call=tool_call,
        needs_confirmation=confirmation_decision.requires_confirmation,
        preapproval_output=preapproval_output,
        sdk_approved=sdk_approved,
    )


__all__ = [
    "ResumeToolLifecycleRequest",
    "ResumeToolLifecycleRunner",
    "ResumeToolLifecycleStart",
    "begin_resume_tool_lifecycle",
]
