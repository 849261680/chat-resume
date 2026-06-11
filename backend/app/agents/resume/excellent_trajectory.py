"""用于按 Anthropic 风格评测优秀简历 Agent 的完整执行轨迹。"""

from __future__ import annotations

import json
from typing import Any

_TOOL_ALIASES = {
    "优化要点": "update_bullet",
    "新增要点": "add_bullet",
    "删除要点": "remove_bullet",
    "询问信息": "ask_user",
    "评估简历": "score_resume",
}
_CLARIFY_TOOL_NAMES = {"ask_user"}
_MUTATION_TOOL_NAMES = {
    "update_bullet",
    "add_bullet",
    "remove_bullet",
    "update_summary",
    "update_profile",
    "update_item_fields",
    "update_skills",
    "update_overview",
    "show_section",
    "hide_section",
    "upsert_job_application",
}
_GATE_FAILURE_TYPES = {"unsupported_resume_claim", "low_quality_resume_edit"}
_CLARIFY_MARKERS = (
    "请补充",
    "是否真实",
    "有没有",
    "能否提供",
    "需要你确认",
    "不能编造",
    "缺少",
)
_TOOL_EVENT_MARKERS = ("tool_call", "tool_result", "tool_started", "tool_completed")


def evaluate_excellent_resume_trajectory(
    *,
    case: dict[str, Any],
    trajectory: dict[str, Any],
) -> dict[str, Any]:
    """用于判断一次 Agent 轨迹是否满足黄金样例和 Anthropic 轨迹标准。"""
    expected = case["expected_behavior"]
    actual_tool_calls = _actual_tool_calls(trajectory)
    final_text = _trajectory_text(trajectory)
    gate_failure = _has_gate_failure(trajectory)
    actual_decision = _actual_decision(
        actual_tool_calls=actual_tool_calls,
        final_text=final_text,
        gate_failure=gate_failure,
    )
    anthropic_metrics = _anthropic_metrics(
        case=case,
        trajectory=trajectory,
        actual_tool_calls=actual_tool_calls,
        actual_decision=actual_decision,
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
        "tool_metrics": _tool_metrics(trajectory, actual_tool_calls),
        "anthropic_metrics": anthropic_metrics,
        "anthropic_passed": _metrics_passed(anthropic_metrics),
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
    return any(_is_gate_failure(item) for item in _checked_items(trajectory))


def _is_gate_failure(item: Any) -> bool:
    """用于判断单个轨迹项是否为质量门禁失败。"""
    if not isinstance(item, dict):
        return False
    if item.get("success") is not False and not item.get("tool_call_failed"):
        return False
    return _error_type(item) in _GATE_FAILURE_TYPES


def _checked_items(trajectory: dict[str, Any]) -> list[Any]:
    """用于收集需要检查的工具调用和运行时事件。"""
    return [*trajectory.get("tool_calls", []), *trajectory.get("runtime_events", [])]


def _error_type(call: dict[str, Any]) -> str:
    """用于从工具失败结构中读取错误类型。"""
    error = call.get("error")
    if isinstance(error, dict) and isinstance(error.get("type"), str):
        return error["type"]
    result = call.get("result")
    if isinstance(result, dict):
        result_error = result.get("error")
        if isinstance(result_error, dict) and isinstance(result_error.get("type"), str):
            return result_error["type"]
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
    if actual_tool_calls and _only_clarify_tools(actual_tool_calls):
        return "clarify"
    if actual_tool_calls:
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


def _anthropic_metrics(
    *,
    case: dict[str, Any],
    trajectory: dict[str, Any],
    actual_tool_calls: list[str],
    actual_decision: str,
    gate_failure: bool,
) -> dict[str, dict[str, Any]]:
    """用于生成 Anthropic 风格的轨迹级评测维度。"""
    profile = case.get("anthropic_eval")
    profile = profile if isinstance(profile, dict) else {}
    tool_metrics = _tool_metrics(trajectory, actual_tool_calls)
    return {
        "planning_visibility": _planning_metric(
            profile=profile,
            trajectory=trajectory,
            actual_decision=actual_decision,
        ),
        "feedback_repair": _feedback_repair_metric(
            profile=profile,
            trajectory=trajectory,
            gate_failure=gate_failure,
        ),
        "stopping_condition": _stopping_metric(
            profile=profile,
            tool_metrics=tool_metrics,
        ),
        "tool_efficiency": _tool_efficiency_metric(
            profile=profile,
            expected=case["expected_behavior"],
            tool_metrics=tool_metrics,
        ),
        "tool_error_recovery": _tool_error_recovery_metric(
            trajectory=trajectory,
            tool_metrics=tool_metrics,
        ),
    }


def _planning_metric(
    *,
    profile: dict[str, Any],
    trajectory: dict[str, Any],
    actual_decision: str,
) -> dict[str, Any]:
    """用于评估修改类任务是否在行动前给出可见计划。"""
    expected = bool(profile.get("expected_planning"))
    applicable = expected or actual_decision == "execute"
    observed = _has_planning_before_action(trajectory)
    return _metric(
        applicable=applicable,
        passed=(not applicable) or observed,
        observed=observed,
        reason="mutation_tasks_should_show_one_sentence_plan_before_tools",
    )


def _feedback_repair_metric(
    *,
    profile: dict[str, Any],
    trajectory: dict[str, Any],
    gate_failure: bool,
) -> dict[str, Any]:
    """用于评估质量门禁失败后是否进入自我修复闭环。"""
    applicable = bool(profile.get("requires_feedback_repair")) or gate_failure
    repaired = _has_successful_repair_after_failure(trajectory)
    return _metric(
        applicable=applicable,
        passed=(not applicable) or repaired,
        observed=repaired,
        reason="recoverable_tool_feedback_should_be_retried_with_safer_inputs",
    )


def _stopping_metric(
    *,
    profile: dict[str, Any],
    tool_metrics: dict[str, Any],
) -> dict[str, Any]:
    """用于评估是否避免重复同参调用并遵守自动修正上限。"""
    max_retries = int(profile.get("max_auto_retries", 2))
    observed = {
        "duplicate_tool_calls": tool_metrics["duplicate_tool_calls"],
        "tool_errors": tool_metrics["tool_errors"],
        "max_auto_retries": max_retries,
    }
    passed = (
        tool_metrics["duplicate_tool_calls"] == 0
        and tool_metrics["tool_errors"] <= max_retries
    )
    return _metric(
        applicable=True,
        passed=passed,
        observed=observed,
        reason="agents_should_stop_or_ask_after_repeated_failures",
    )


def _tool_efficiency_metric(
    *,
    profile: dict[str, Any],
    expected: dict[str, Any],
    tool_metrics: dict[str, Any],
) -> dict[str, Any]:
    """用于评估工具调用数量是否贴近最小必要路径。"""
    max_tool_calls = profile.get("max_tool_calls")
    if not isinstance(max_tool_calls, int):
        expected_calls = expected.get("expected_tool_calls", [])
        max_tool_calls = max(1, len(expected_calls) + 1)
    observed = tool_metrics["total_tool_calls"]
    return _metric(
        applicable=True,
        passed=observed <= max_tool_calls,
        observed={"tool_calls": observed, "max_tool_calls": max_tool_calls},
        reason="agents_should_use_the_fewest_tools_that_complete_the_task",
    )


def _tool_error_recovery_metric(
    *,
    trajectory: dict[str, Any],
    tool_metrics: dict[str, Any],
) -> dict[str, Any]:
    """用于评估出现工具错误时是否恢复为修正或追问。"""
    applicable = tool_metrics["tool_errors"] > 0
    recovered = _has_successful_repair_after_failure(trajectory) or _ends_with_clarification(trajectory)
    return _metric(
        applicable=applicable,
        passed=(not applicable) or recovered,
        observed=recovered,
        reason="tool_errors_should_become_actionable_feedback_not_dead_ends",
    )


def _metric(
    *,
    applicable: bool,
    passed: bool,
    observed: Any,
    reason: str,
) -> dict[str, Any]:
    """用于生成统一评测维度结构。"""
    return {
        "applicable": applicable,
        "passed": passed,
        "observed": observed,
        "reason": reason,
    }


def _metrics_passed(metrics: dict[str, dict[str, Any]]) -> bool:
    """用于汇总 Anthropic 维度是否全部通过。"""
    return all(
        metric.get("passed") is True
        for metric in metrics.values()
        if metric.get("applicable") is not False
    )


def _tool_metrics(
    trajectory: dict[str, Any],
    actual_tool_calls: list[str],
) -> dict[str, Any]:
    """用于汇总工具调用数量、错误和重复调用。"""
    checked_items = _checked_items(trajectory)
    return {
        "total_tool_calls": len(actual_tool_calls),
        "unique_tool_calls": len(set(actual_tool_calls)),
        "tool_errors": sum(1 for item in checked_items if _is_tool_error(item)),
        "duplicate_tool_calls": _duplicate_tool_call_count(trajectory),
    }


def _is_tool_error(item: Any) -> bool:
    """用于判断轨迹项是否表示工具错误。"""
    return isinstance(item, dict) and (
        item.get("success") is False or item.get("tool_call_failed") is True
    )


def _duplicate_tool_call_count(trajectory: dict[str, Any]) -> int:
    """用于统计同名同参数工具调用的重复次数。"""
    seen: set[str] = set()
    duplicates = 0
    for call in trajectory.get("tool_calls", []):
        if not isinstance(call, dict):
            continue
        fingerprint = _tool_fingerprint(call)
        if fingerprint in seen:
            duplicates += 1
            continue
        seen.add(fingerprint)
    return duplicates


def _tool_fingerprint(call: dict[str, Any]) -> str:
    """用于生成稳定的工具调用指纹。"""
    name = _tool_call_name(call)
    args = call.get("arguments") or call.get("args") or call.get("input") or call.get("tool_input")
    return f"{name}:{_stable_json(args)}"


def _stable_json(value: Any) -> str:
    """用于把工具参数转换成稳定字符串。"""
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def _has_planning_before_action(trajectory: dict[str, Any]) -> bool:
    """用于检查首个工具事件前是否出现可见计划文本。"""
    for event in trajectory.get("runtime_events", []):
        if not isinstance(event, dict):
            continue
        if _is_tool_event(event):
            return False
        if _is_planning_text(event):
            return True
    return False


def _is_tool_event(event: dict[str, Any]) -> bool:
    """用于识别工具相关运行时事件。"""
    event_type = str(event.get("event_type") or "")
    if any(marker in event_type for marker in _TOOL_EVENT_MARKERS):
        return True
    calls = event.get("tool_calls")
    return isinstance(calls, list) and bool(calls)


def _is_planning_text(event: dict[str, Any]) -> bool:
    """用于识别工具前的一句话可见计划。"""
    if event.get("event_type") not in {"text_delta", "reasoning_delta", "planning"}:
        return False
    content = str(event.get("content") or event.get("text") or "").strip()
    if not content:
        return False
    completion_markers = ("已完成", "已更新", "完成")
    return not any(content.startswith(marker) for marker in completion_markers)


def _has_successful_repair_after_failure(trajectory: dict[str, Any]) -> bool:
    """用于判断失败后是否有后续成功的修改工具调用。"""
    seen_failure = False
    for item in _checked_items(trajectory):
        if not isinstance(item, dict):
            continue
        if _is_tool_error(item):
            seen_failure = True
            continue
        if seen_failure and _is_successful_mutation(item):
            return True
    return False


def _is_successful_mutation(item: dict[str, Any]) -> bool:
    """用于判断轨迹项是否是成功的简历修改动作。"""
    name = _TOOL_ALIASES.get(_tool_call_name(item), _tool_call_name(item))
    if name not in _MUTATION_TOOL_NAMES:
        return False
    if item.get("success") is False or item.get("tool_call_failed") is True:
        return False
    result = item.get("result")
    if isinstance(result, dict) and result.get("success") is False:
        return False
    return True


def _ends_with_clarification(trajectory: dict[str, Any]) -> bool:
    """用于判断失败后最终是否转为向用户补事实。"""
    return _looks_like_clarification(_trajectory_text(trajectory))


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
