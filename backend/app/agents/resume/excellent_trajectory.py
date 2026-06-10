"""用于评测优秀简历 Agent 的离线轨迹结果。"""

from __future__ import annotations

from typing import Any

_TOOL_ALIASES = {
    "优化要点": "update_bullet",
    "新增要点": "add_bullet",
    "删除要点": "remove_bullet",
    "优化总结": "update_summary",
    "优化项目简介": "update_overview",
    "询问信息": "ask_user",
    "update_bullet": "update_bullet",
    "add_bullet": "add_bullet",
    "remove_bullet": "remove_bullet",
    "update_summary": "update_summary",
    "update_overview": "update_overview",
    "ask_user": "ask_user",
}
_CLARIFY_TOOL_NAMES = {"ask_user"}
_GATE_FAILURE_TYPES = {"unsupported_resume_claim", "low_quality_resume_edit"}
_CLARIFY_MARKERS = (
    "请补充",
    "请确认",
    "是否",
    "有没有",
    "需要确认",
    "不能编造",
    "缺少",
    "真实",
    "?",
    "？",
)


def evaluate_excellent_resume_trajectory(
    *,
    case: dict[str, Any],
    trajectory: dict[str, Any],
) -> dict[str, Any]:
    """用于判断一次 Agent 轨迹是否满足黄金样例期望。"""
    expected = case["expected_behavior"]
    actual_tool_calls = _actual_tool_calls(trajectory)
    final_text = _trajectory_text(trajectory)
    gate_failure = _has_gate_failure(trajectory)
    actual_decision = _actual_decision(
        actual_tool_calls=actual_tool_calls,
        final_text=final_text,
        gate_failure=gate_failure,
    )
    failures = _failures(
        case=case,
        expected=expected,
        actual_decision=actual_decision,
        actual_tool_calls=actual_tool_calls,
        final_text=final_text,
    )
    return {
        "passed": not failures,
        "failure_codes": failures,
        "actual_decision": actual_decision,
        "actual_tool_calls": actual_tool_calls,
        "gate_failure": gate_failure,
    }


def _actual_tool_calls(trajectory: dict[str, Any]) -> list[str]:
    """用于从轨迹中提取标准化后的工具调用名。"""
    names: list[str] = []
    for call in trajectory.get("tool_calls", []):
        raw_name = _tool_call_name(call)
        normalized = _TOOL_ALIASES.get(raw_name, raw_name)
        if normalized:
            names.append(normalized)
    return names


def _tool_call_name(call: Any) -> str:
    """用于兼容字符串和字典两种工具调用结构。"""
    if isinstance(call, str):
        return call
    if not isinstance(call, dict):
        return ""
    name = call.get("name") or call.get("tool_name") or call.get("tool_id")
    return name if isinstance(name, str) else ""


def _trajectory_text(trajectory: dict[str, Any]) -> str:
    """用于合并最终回复和工具结果中的文本。"""
    chunks = [_text_from_value(trajectory.get("final_text", ""))]
    chunks.extend(_text_from_value(call) for call in trajectory.get("tool_calls", []))
    return "\n".join(chunk for chunk in chunks if chunk)


def _has_gate_failure(trajectory: dict[str, Any]) -> bool:
    """用于识别事实或质量门禁触发后的失败工具调用。"""
    for call in trajectory.get("tool_calls", []):
        if not isinstance(call, dict):
            continue
        if call.get("success") is not False:
            continue
        error_type = _error_type(call)
        if error_type in _GATE_FAILURE_TYPES:
            return True
    return False


def _error_type(call: dict[str, Any]) -> str:
    """用于从工具失败结构中读取错误类型。"""
    error = call.get("error")
    if isinstance(error, dict) and isinstance(error.get("type"), str):
        return error["type"]
    if isinstance(call.get("error_type"), str):
        return call["error_type"]
    return ""


def _actual_decision(
    *,
    actual_tool_calls: list[str],
    final_text: str,
    gate_failure: bool,
) -> str:
    """用于把轨迹压缩成执行或追问决策。"""
    if gate_failure:
        return "clarify"
    if actual_tool_calls and not _only_clarify_tools(actual_tool_calls):
        return "execute"
    if _looks_like_clarification(final_text):
        return "clarify"
    return "execute"


def _only_clarify_tools(actual_tool_calls: list[str]) -> bool:
    """用于判断工具轨迹是否只包含结构化追问。"""
    return all(name in _CLARIFY_TOOL_NAMES for name in actual_tool_calls)


def _looks_like_clarification(text: str) -> bool:
    """用于判断最终回复是否在向用户补事实。"""
    return any(marker in text for marker in _CLARIFY_MARKERS)


def _failures(
    *,
    case: dict[str, Any],
    expected: dict[str, Any],
    actual_decision: str,
    actual_tool_calls: list[str],
    final_text: str,
) -> list[str]:
    """用于汇总轨迹不满足黄金样例的失败原因。"""
    failures: list[str] = []
    if actual_decision != expected["decision"]:
        failures.append("unexpected_decision")
    if _missing_tool_calls(expected, actual_tool_calls):
        failures.append("missing_expected_tool_calls")
    if actual_decision == "execute" and _forbidden_claims_present(case, final_text):
        failures.append("forbidden_claims_present")
    return failures


def _missing_tool_calls(expected: dict[str, Any], actual_tool_calls: list[str]) -> bool:
    """用于判断执行轨迹是否缺少期望工具。"""
    missing = set(expected["expected_tool_calls"]) - set(actual_tool_calls)
    return bool(missing)


def _forbidden_claims_present(case: dict[str, Any], final_text: str) -> bool:
    """用于判断最终可见文本是否包含样例禁止编造的事实。"""
    return any(claim in final_text for claim in case.get("forbidden_claims", []))


def _text_from_value(value: Any) -> str:
    """用于从嵌套结构中提取可检索文本。"""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_text_from_value(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text_from_value(item) for item in value)
    return ""


__all__ = ["evaluate_excellent_resume_trajectory"]
