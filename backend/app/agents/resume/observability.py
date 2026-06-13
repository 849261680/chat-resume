"""用于维护单次 Resume Agent run 的观测指标。"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_CURRENT_RUN_STATE: ContextVar[dict[str, Any] | None] = ContextVar(
    "resume_agent_observability_state",
    default=None,
)


def bind_observability_state(state: dict[str, Any]) -> Token[dict[str, Any] | None]:
    """用于把当前异步链路绑定到单次 run 状态。"""
    return _CURRENT_RUN_STATE.set(state)


def reset_observability_state(token: Token[dict[str, Any] | None]) -> None:
    """用于解除当前异步链路的 run 状态绑定。"""
    _CURRENT_RUN_STATE.reset(token)


def current_observability_state() -> dict[str, Any] | None:
    """用于读取当前异步链路绑定的 run 状态。"""
    return _CURRENT_RUN_STATE.get()


def increment_counter(state: dict[str, Any] | None, key: str, amount: int = 1) -> None:
    """用于递增 run 状态中的整数计数器。"""
    if state is None:
        return
    state[key] = int(state.get(key) or 0) + amount


def increment_unique_counter(
    state: dict[str, Any] | None,
    *,
    bucket_key: str,
    value: str,
    counter_key: str,
) -> None:
    """用于按唯一值递增计数器，避免同一工具调用重复计数。"""
    if state is None or not value:
        return
    bucket = state.setdefault(bucket_key, set())
    if not isinstance(bucket, set) or value in bucket:
        return
    bucket.add(value)
    increment_counter(state, counter_key)


def record_guardrail_rejections(count: int) -> None:
    """用于记录 SDK guardrail 拒绝次数。"""
    if count <= 0:
        return
    increment_counter(current_observability_state(), "guardrail_rejected_count", count)


__all__ = [
    "bind_observability_state",
    "current_observability_state",
    "increment_counter",
    "increment_unique_counter",
    "record_guardrail_rejections",
    "reset_observability_state",
]
