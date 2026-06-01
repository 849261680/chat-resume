"""用于集中处理 Agent 工具确认等待规则。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolConfirmationDecision:
    """用于表达工具调用确认策略的判断结果。"""

    requires_confirmation: bool
    terminate_turn: bool = False


@dataclass(frozen=True)
class ToolConfirmationResult:
    """用于表达用户确认后的策略结果。"""

    confirmed: bool
    terminate_turn: bool
    feedback: str | None = None


class ToolConfirmationPolicy:
    """用于封装工具确认 hook 语义。"""

    def before_tool_call(
        self,
        *,
        confirmation_queue: asyncio.Queue | None,
        tool_name: str,
        auto_execute_tool_names: set[str],
    ) -> ToolConfirmationDecision:
        """用于在工具执行前判断是否需要确认。"""
        return ToolConfirmationDecision(
            requires_confirmation=requires_tool_confirmation(
                confirmation_queue=confirmation_queue,
                tool_name=tool_name,
                auto_execute_tool_names=auto_execute_tool_names,
            )
        )

    async def wait_for_decision(
        self,
        confirmation_queue: asyncio.Queue,
    ) -> ToolConfirmationResult:
        """用于等待用户确认结果。"""
        return await wait_for_tool_confirmation(confirmation_queue)

    def after_tool_decision(
        self,
        *,
        confirmed: bool,
        feedback: str | None = None,
    ) -> ToolConfirmationResult:
        """用于在用户确认或拒绝后把结果交还给模型继续 ReAct。"""
        return ToolConfirmationResult(
            confirmed=confirmed,
            terminate_turn=False,
            feedback=normalize_confirmation_feedback(feedback),
        )


def requires_tool_confirmation(
    *,
    confirmation_queue: asyncio.Queue | None,
    tool_name: str,
    auto_execute_tool_names: set[str],
) -> bool:
    """用于判断一个业务工具调用是否需要用户确认。"""
    return (
        confirmation_queue is not None
        and tool_name not in auto_execute_tool_names
    )


def normalize_confirmation_feedback(value: object) -> str | None:
    """用于把用户反馈清洗为可传给 Agent 的短文本。"""
    if not isinstance(value, str):
        return None
    feedback = value.strip()
    return feedback[:1000] if feedback else None


def parse_confirmation_queue_item(value: object) -> ToolConfirmationResult:
    """用于兼容旧布尔确认值和新结构化确认值。"""
    if not isinstance(value, dict):
        return ToolConfirmationResult(confirmed=bool(value), terminate_turn=False)
    return ToolConfirmationResult(
        confirmed=bool(value.get("confirmed")),
        terminate_turn=False,
        feedback=normalize_confirmation_feedback(value.get("feedback")),
    )


async def wait_for_tool_confirmation(
    confirmation_queue: asyncio.Queue,
    *,
    timeout_seconds: float | None = None,
) -> ToolConfirmationResult:
    """用于等待用户确认，默认作为持久 checkpoint 不自动拒绝。"""
    try:
        return parse_confirmation_queue_item(
            await asyncio.wait_for(confirmation_queue.get(), timeout=timeout_seconds)
        )
    except asyncio.TimeoutError:
        return ToolConfirmationResult(confirmed=False, terminate_turn=False)


__all__ = [
    "ToolConfirmationDecision",
    "ToolConfirmationPolicy",
    "ToolConfirmationResult",
    "normalize_confirmation_feedback",
    "parse_confirmation_queue_item",
    "requires_tool_confirmation",
    "wait_for_tool_confirmation",
]
