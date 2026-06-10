"""用于生成 OpenAI Agents SDK 标准兼容的 Agent eval 产物。"""

from __future__ import annotations

import json
from typing import Any

from agents import gen_trace_id

from app.runtime.openai_agents_eval import OpenAIAgentsTraceConfig

OPENAI_AGENTS_EVAL_SPEC_VERSION = "2026-06-10"
OPENAI_AGENTS_EVAL_WORKFLOW = "chat-resume.resume-agent.eval"
OPENAI_AGENTS_EVAL_NAME = "chat_resume_resume_agent_workflow"
OPENAI_AGENTS_GRADER_NAME = "chat_resume_agent_workflow_grader"

OPENAI_AGENTS_PYTHON_GRADER_SOURCE = r'''
"""OpenAI Python grader for Chat Resume agent workflow evals."""

from typing import Any


def grade(sample: dict[str, Any], item: dict[str, Any]) -> float:
    """Grade one Resume Agent workflow sample against its dataset item."""
    output_json = sample.get("output_json") or {}
    output_text = str(sample.get("output_text") or "")
    output_tools = sample.get("output_tools") or []
    checks = [
        _decision_score(output_json, item),
        _tool_score(output_json, output_tools, item),
        _keyword_score(output_json, item),
        _forbidden_score(output_json, output_text, item),
        _reply_shape_score(output_text, item),
    ]
    active = [score for score in checks if score is not None]
    return sum(active) / len(active) if active else 1.0


def _decision_score(output_json: dict[str, Any], item: dict[str, Any]) -> float | None:
    """Score the high-level execute-vs-clarify decision."""
    expected = item.get("expected_decision")
    if not expected:
        return None
    return 1.0 if output_json.get("decision") == expected else 0.0


def _tool_score(
    output_json: dict[str, Any],
    output_tools: list[Any],
    item: dict[str, Any],
) -> float | None:
    """Score expected tool names using JSON output and SDK tool-call shape."""
    if "expected_tool_calls" not in item:
        return None
    expected = [str(name) for name in item.get("expected_tool_calls") or []]
    actual = _tool_names(output_json, output_tools)
    return 1.0 if actual == expected else 0.0


def _keyword_score(output_json: dict[str, Any], item: dict[str, Any]) -> float | None:
    """Score required resume keywords in the final structured state."""
    required = [str(term) for term in item.get("must_contain_keywords") or []]
    if not required:
        return None
    resume_text = _collect_text(output_json.get("resume_after"))
    return 1.0 if all(term in resume_text for term in required) else 0.0


def _forbidden_score(
    output_json: dict[str, Any],
    output_text: str,
    item: dict[str, Any],
) -> float | None:
    """Score forbidden terms across final text and resume state."""
    forbidden = [str(term) for term in item.get("forbidden_content") or []]
    if not forbidden:
        return None
    resume_text = _collect_text(output_json.get("resume_after"))
    combined = output_text + "\n" + resume_text
    return 1.0 if not any(term in combined for term in forbidden) else 0.0


def _reply_shape_score(output_text: str, item: dict[str, Any]) -> float | None:
    """Score reply substring and question-count expectations."""
    scores: list[float] = []
    forbidden = [str(term) for term in item.get("forbidden_reply_substrings") or []]
    required_any = [str(term) for term in item.get("required_reply_substrings_any") or []]
    max_questions = item.get("max_question_marks")
    if forbidden:
        scores.append(1.0 if not any(term in output_text for term in forbidden) else 0.0)
    if required_any:
        scores.append(1.0 if any(term in output_text for term in required_any) else 0.0)
    if isinstance(max_questions, int):
        question_count = output_text.count("?") + output_text.count("？")
        scores.append(1.0 if question_count <= max_questions else 0.0)
    return sum(scores) / len(scores) if scores else None


def _tool_names(output_json: dict[str, Any], output_tools: list[Any]) -> list[str]:
    """Read tool names from output_json first, then SDK output_tools."""
    names = output_json.get("tool_calls")
    if isinstance(names, list):
        return [str(name) for name in names]
    return [_tool_name(tool) for tool in output_tools if _tool_name(tool)]


def _tool_name(tool: Any) -> str:
    """Read one SDK output tool name."""
    if not isinstance(tool, dict):
        return ""
    function = tool.get("function")
    if isinstance(function, dict) and isinstance(function.get("name"), str):
        return function["name"]
    name = tool.get("name")
    return name if isinstance(name, str) else ""


def _collect_text(value: Any) -> str:
    """Flatten nested JSON into text for keyword checks."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_collect_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_collect_text(item) for item in value.values())
    return ""
'''


def build_trace_config(case_id: str) -> OpenAIAgentsTraceConfig:
    """用于为单个 eval case 创建 SDK trace 配置。"""
    return OpenAIAgentsTraceConfig(
        workflow_name=OPENAI_AGENTS_EVAL_WORKFLOW,
        trace_id=gen_trace_id(),
        group_id=f"chat-resume-eval:{case_id}",
        metadata={
            "eval_name": OPENAI_AGENTS_EVAL_NAME,
            "eval_spec_version": OPENAI_AGENTS_EVAL_SPEC_VERSION,
            "case_id": case_id,
            "agent": "ResumeAgent",
            "standard": "openai-agents-sdk",
        },
        trace_include_sensitive_data=False,
    )


def build_dataset_item(
    *,
    case: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """用于把本地 eval case 转成 OpenAI dataset item 形状。"""
    return {
        "case_id": inputs.get("case_id") or case.get("id"),
        "input": {
            "user_message": inputs.get("user_message", ""),
            "resume": inputs.get("resume"),
            "jd": inputs.get("jd"),
        },
        "expected_decision": case.get("expected_decision"),
        "expected_tool_calls": _list_of_strings(case.get("expected_tool_calls")),
        "must_contain_keywords": _list_of_strings(case.get("must_contain_keywords")),
        "forbidden_content": _list_of_strings(case.get("forbidden_content")),
        "required_reply_substrings_any": _list_of_strings(
            case.get("required_reply_substrings_any")
        ),
        "forbidden_reply_substrings": _list_of_strings(case.get("forbidden_reply_substrings")),
        "max_question_marks": case.get("max_question_marks"),
        "expect_refusal": bool(case.get("expect_refusal", False)),
        "expect_moderate_refusal": bool(case.get("expect_moderate_refusal", False)),
    }


def build_model_sample(result: dict[str, Any]) -> dict[str, Any]:
    """用于把本地 Agent 结果转成 OpenAI grader 的 sample 形状。"""
    tool_calls = _list_of_strings(result.get("tool_calls"))
    return {
        "output_text": str(result.get("agent_reply", "")),
        "output_json": {
            "decision": result.get("decision"),
            "tool_calls": tool_calls,
            "resume_after": result.get("resume_after", {}),
            "runtime_events": result.get("runtime_events", []),
        },
        "output_tools": [_output_tool(name) for name in tool_calls],
    }


def build_python_grader() -> dict[str, Any]:
    """用于生成 OpenAI Python grader 配置。"""
    return {
        "type": "python",
        "name": OPENAI_AGENTS_GRADER_NAME,
        "source": OPENAI_AGENTS_PYTHON_GRADER_SOURCE,
        "image_tag": "2025-05-08",
    }


def build_eval_artifact(
    *,
    case: dict[str, Any],
    inputs: dict[str, Any],
    result: dict[str, Any],
    trace_config: OpenAIAgentsTraceConfig,
) -> dict[str, Any]:
    """用于汇总单条 case 的 OpenAI Agents eval 标准兼容产物。"""
    return {
        "spec_version": OPENAI_AGENTS_EVAL_SPEC_VERSION,
        "eval_name": OPENAI_AGENTS_EVAL_NAME,
        "trace": {
            "workflow_name": trace_config.workflow_name,
            "trace_id": trace_config.trace_id,
            "group_id": trace_config.group_id,
            "metadata": trace_config.metadata,
            "trace_include_sensitive_data": trace_config.trace_include_sensitive_data,
        },
        "dataset_item": build_dataset_item(case=case, inputs=inputs),
        "model_sample": build_model_sample(result),
        "grader": build_python_grader(),
    }


def build_eval_run_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """用于汇总整次 eval run 的 OpenAI Agents 标准信息。"""
    trace_ids = []
    for result in results:
        trace_id = _trace_id_from_result(result)
        if trace_id:
            trace_ids.append(trace_id)
    return {
        "spec_version": OPENAI_AGENTS_EVAL_SPEC_VERSION,
        "eval_name": OPENAI_AGENTS_EVAL_NAME,
        "workflow_name": OPENAI_AGENTS_EVAL_WORKFLOW,
        "grader_name": OPENAI_AGENTS_GRADER_NAME,
        "trace_ids": trace_ids,
        "dataset_item_count": len(results),
        "grader": build_python_grader(),
    }


def _trace_id_from_result(result: dict[str, Any]) -> str:
    """用于从单条结果里读取 trace id。"""
    artifact = result.get("openai_agents_eval")
    if not isinstance(artifact, dict):
        return ""
    trace = artifact.get("trace")
    if not isinstance(trace, dict):
        return ""
    trace_id = trace.get("trace_id")
    return trace_id if isinstance(trace_id, str) else ""


def _output_tool(name: str) -> dict[str, Any]:
    """用于构建 OpenAI sample.output_tools 兼容的工具调用摘要。"""
    return {
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps({}, ensure_ascii=False),
        },
    }


def _list_of_strings(value: Any) -> list[str]:
    """用于把任意列表值规范化成字符串列表。"""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


__all__ = [
    "OPENAI_AGENTS_EVAL_NAME",
    "OPENAI_AGENTS_EVAL_SPEC_VERSION",
    "OPENAI_AGENTS_EVAL_WORKFLOW",
    "build_dataset_item",
    "build_eval_artifact",
    "build_eval_run_summary",
    "build_model_sample",
    "build_python_grader",
    "build_trace_config",
]
