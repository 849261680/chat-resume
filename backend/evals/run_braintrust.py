#!/usr/bin/env python
"""用于把真实 Resume Agent 输出上报为 Braintrust experiment。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, cast

from braintrust import Eval
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from braintrust_resume_scorers import (  # noqa: E402
    final_resume_score_scorer,
    hallucination_safety_scorer,
    jd_match_scorer,
    star_quality_scorer,
    uplift_score_scorer,
)
from app.services.agent.quality_judge import (  # noqa: E402
    judge_agent_output,
    judge_bullet_quality,
)
from evals.braintrust_real_dataset import build_braintrust_eval_data  # noqa: E402
from eval.harness import (  # type: ignore[reportMissingImports]  # noqa: E402
    build_agent,
    has_required_agent_api_key,
    load_backend_env,
    required_agent_api_key_name,
    run_agent_target,
)

BRAINTRUST_PROJECT_NAME = "chat-resume"
BRAINTRUST_EXPERIMENT_NAME = "resume-agent-real-eval"
PASS_THRESHOLD = 70.0


async def resume_optimization_task(input: dict[str, Any]) -> dict[str, Any]:
    """用于调用真实 Resume Agent 并返回可评分的输出摘要。"""
    agent = build_agent()
    result = await run_agent_target(
        agent,
        {
            "case_id": input["case_id"],
            "resume": input["resume"],
            "user_message": input["user_request"],
            "jd": input.get("jd"),
        },
    )
    resume_after = result.get("resume_after")
    optimized_bullet = _target_bullet_text(resume_after, input.get("target"))
    return {
        "optimized_bullet": optimized_bullet,
        "agent_reply": result.get("agent_reply", ""),
        "tool_calls": result.get("tool_calls", []),
        "decision": result.get("decision", ""),
        "elapsed_s": result.get("elapsed_s"),
        "resume_after": resume_after,
    }


def _quality_judgment(input: dict[str, Any], output: Any):
    """用于复用现有 Resume Agent 规则评判器。"""
    return judge_agent_output(
        user_message=str(input["user_request"]),
        tool_calls=_output_tool_calls(output),
        final_text=_output_text(output),
        pass_threshold=PASS_THRESHOLD,
    )


def rule_quality_score(
    input: dict[str, Any],
    output: Any,
    expected: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """用于给整体规则评判分上报 Braintrust score。"""
    del expected
    judgment = _quality_judgment(input, output)
    return {
        "name": "Rule quality",
        "score": judgment.overall_score / 100.0,
        "metadata": {
            "raw_score": judgment.overall_score,
            "passed": judgment.passed,
            "summary": judgment.summary,
        },
    }


def behavior_match_score(
    input: dict[str, Any],
    output: Any,
    expected: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """用于评估真实 Agent 的 decision 和 tool_calls 是否符合期望。"""
    del input
    expected = expected or {}
    expected_decision = str(expected.get("expected_decision", ""))
    expected_tools = _string_list(expected.get("expected_tool_calls"))
    actual_decision = _output_decision(output)
    actual_tools = _output_tool_names(output)
    decision_score = 1.0 if actual_decision == expected_decision else 0.0
    tool_score = 1.0 if actual_tools == expected_tools else 0.0
    return {
        "name": "Behavior match",
        "score": (decision_score + tool_score) / 2,
        "metadata": {
            "expected_decision": expected_decision,
            "actual_decision": actual_decision,
            "expected_tool_calls": expected_tools,
            "actual_tool_calls": actual_tools,
        },
    }


def forbidden_claims_score(
    input: dict[str, Any],
    output: Any,
    expected: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """用于评估真实 Agent 是否写入了明确禁止的编造项。"""
    del input
    forbidden = _string_list((expected or {}).get("forbidden_claims"))
    text = _flatten_text(output)
    hits = [claim for claim in forbidden if claim and claim in text]
    return {
        "name": "Forbidden claims safety",
        "score": 1.0 if not hits else 0.0,
        "metadata": {"forbidden_claims": forbidden, "hits": hits},
    }


def bullet_quality_score(
    input: dict[str, Any],
    output: Any,
    expected: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """用于给 bullet 文本质量上报 Braintrust score。"""
    del input
    if not _resume_quality_applicable(expected):
        return {
            "name": "Bullet quality",
            "score": None,
            "metadata": {"not_applicable": True},
        }
    dimension = judge_bullet_quality(_output_text(output))
    return {
        "name": "Bullet quality",
        "score": dimension.score / 100.0,
        "metadata": {
            "raw_score": dimension.score,
            "passed": dimension.passed,
            "findings": dimension.findings,
        },
    }


def resume_final_score(
    input: dict[str, Any],
    output: Any,
    expected: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """用于在真实 Agent 执行类 case 上复用项目级最终分 scorer。"""
    if not _resume_quality_applicable(expected):
        return _not_applicable_score("Resume final score")
    return final_resume_score_scorer(input=input, output=output, expected=expected)


def resume_uplift_score(
    input: dict[str, Any],
    output: Any,
    expected: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """用于在真实 Agent 执行类 case 上复用项目级提升 scorer。"""
    if not _resume_quality_applicable(expected):
        return _not_applicable_score("Resume uplift score")
    return uplift_score_scorer(input=input, output=output, expected=expected)


def resume_star_quality_score(
    input: dict[str, Any],
    output: Any,
    expected: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """用于在真实 Agent 执行类 case 上复用项目级 STAR scorer。"""
    if not _resume_quality_applicable(expected):
        return _not_applicable_score("Resume STAR quality score")
    return star_quality_scorer(input=input, output=output, expected=expected)


def resume_jd_match_score(
    input: dict[str, Any],
    output: Any,
    expected: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """用于在真实 Agent 执行类 case 上复用项目级 JD 匹配 scorer。"""
    if not _resume_quality_applicable(expected):
        return _not_applicable_score("Resume JD match score")
    return jd_match_scorer(input=input, output=output, expected=expected)


def resume_hallucination_safety_score(
    input: dict[str, Any],
    output: Any,
    expected: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """用于在真实 Agent 执行类 case 上复用项目级幻觉安全 scorer。"""
    if not _resume_quality_applicable(expected):
        return _not_applicable_score("Resume hallucination safety")
    return hallucination_safety_scorer(input=input, output=output, expected=expected)


def run_braintrust_eval():
    """用于执行 Braintrust experiment 并返回 SDK 结果。"""
    load_dotenv(BACKEND_DIR / ".env")
    load_backend_env()
    _ensure_agent_api_key()
    return Eval(
        BRAINTRUST_PROJECT_NAME,
        experiment_name=BRAINTRUST_EXPERIMENT_NAME,
        data=cast(Any, _limited_eval_data()),
        task=resume_optimization_task,
        scores=cast(Any, [
            rule_quality_score,
            behavior_match_score,
            forbidden_claims_score,
            bullet_quality_score,
            resume_final_score,
            resume_uplift_score,
            resume_star_quality_score,
            resume_jd_match_score,
            resume_hallucination_safety_score,
        ]),
        metadata={
            "dataset": "eval/cases/excellent_resume_agent_cases.json",
            "pass_threshold": PASS_THRESHOLD,
            "eval_limit": os.getenv("BRAINTRUST_EVAL_LIMIT", ""),
            "real_agent": True,
        },
    )


def _target_bullet_text(resume: Any, target: Any) -> str:
    """用于从真实 Agent 修改后的简历中读取目标 bullet 文本。"""
    if not isinstance(resume, dict) or not isinstance(target, dict):
        return ""
    section = resume.get(str(target.get("section", "")))
    if not isinstance(section, list):
        return ""
    for item in section:
        text = _target_bullet_from_item(item, target)
        if text:
            return text
    return ""


def _target_bullet_from_item(item: Any, target: dict[str, Any]) -> str:
    """用于在单个简历条目中查找目标 bullet。"""
    if not isinstance(item, dict):
        return ""
    if str(item.get("id")) != str(target.get("item_id")):
        return ""
    highlights = item.get("highlights")
    if not isinstance(highlights, list):
        return ""
    for highlight in highlights:
        if isinstance(highlight, dict) and str(highlight.get("id")) == str(target.get("bullet_id")):
            return str(highlight.get("text") or "")
    return ""


def _output_text(output: Any) -> str:
    """用于从 Braintrust task 输出中提取被评分 bullet 文本。"""
    if isinstance(output, dict):
        return str(output.get("optimized_bullet") or output.get("agent_reply") or "")
    return str(output or "")


def _output_decision(output: Any) -> str:
    """用于从 task 输出中提取 Agent 决策。"""
    if isinstance(output, dict):
        return str(output.get("decision", ""))
    return ""


def _output_tool_names(output: Any) -> list[str]:
    """用于从 task 输出中提取工具名列表。"""
    if not isinstance(output, dict):
        return []
    return _string_list(output.get("tool_calls"))


def _output_tool_calls(output: Any) -> list[dict[str, Any]]:
    """用于把 task 输出中的工具名转换为质量评判器可读结构。"""
    if not isinstance(output, dict) or not isinstance(output.get("tool_calls"), list):
        return []
    return [{"name": str(name), "arguments": {}} for name in output["tool_calls"]]


def _limited_eval_data() -> list[dict[str, Any]]:
    """用于按环境变量限制真实 Agent eval 数据行数量。"""
    rows = _case_id_filtered_data(build_braintrust_eval_data())
    raw_limit = os.getenv("BRAINTRUST_EVAL_LIMIT", "").strip()
    if not raw_limit:
        return rows
    limit = int(raw_limit)
    return rows[:max(0, limit)]


def _case_id_filtered_data(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用于按 BRAINTRUST_EVAL_CASE_IDS 选择真实 eval case。"""
    raw_case_ids = os.getenv("BRAINTRUST_EVAL_CASE_IDS", "").strip()
    if not raw_case_ids:
        return rows
    wanted = {item.strip() for item in raw_case_ids.split(",") if item.strip()}
    return [row for row in rows if str(row["input"].get("case_id", "")) in wanted]


def _resume_quality_applicable(expected: dict[str, Any] | None) -> bool:
    """用于判断当前 case 是否应评估最终简历质量。"""
    expected = expected or {}
    has_target = bool(expected.get("expert_rewrite")) or bool(expected.get("expected_decision") == "execute")
    return has_target


def _not_applicable_score(name: str) -> dict[str, Any]:
    """用于返回 Braintrust 可忽略的非适用分数。"""
    return {"name": name, "score": None, "metadata": {"not_applicable": True}}


def _flatten_text(value: Any) -> str:
    """用于把输出 JSON 展平成文本以检查禁用声明。"""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value or "")


def _string_list(value: Any) -> list[str]:
    """用于把可选列表字段规范化成字符串列表。"""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _ensure_agent_api_key() -> None:
    """用于在真实 Agent eval 前确认模型 provider 的 API key 已存在。"""
    if has_required_agent_api_key():
        return
    key_name = required_agent_api_key_name()
    raise RuntimeError(f"{key_name} is required to run real Resume Agent eval")


def main() -> None:
    """用于从命令行运行 Braintrust eval 并打印 experiment 链接。"""
    result = run_braintrust_eval()
    summary = result.summary
    print(f"Braintrust experiment: {summary.experiment_name}")
    if summary.experiment_url:
        print(f"Experiment URL: {summary.experiment_url}")


if __name__ == "__main__":
    main()
