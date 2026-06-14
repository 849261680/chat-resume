"""用于把真实 Resume Agent eval cases 转换为 Braintrust 数据集行。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
REAL_CASES_PATH = ROOT_DIR / "eval" / "cases" / "excellent_resume_agent_cases.json"


def load_real_eval_cases(path: Path = REAL_CASES_PATH) -> list[dict[str, Any]]:
    """用于读取真实 Resume Agent 评测样例。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Real eval cases must be a list: {path}")
    return [case for case in data if isinstance(case, dict)]


def build_braintrust_eval_data(
    cases: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """用于把真实 Agent case 转换为 Braintrust Eval 数据行。"""
    source_cases = cases if cases is not None else load_real_eval_cases()
    return [_build_row(case) for case in source_cases]


def _build_row(case: dict[str, Any]) -> dict[str, Any]:
    """用于转换单条真实 eval case。"""
    expected_behavior = _dict_value(case.get("expected_behavior"))
    target = _dict_value(expected_behavior.get("target"))
    resume = _dict_value(case.get("resume"))
    forbidden_claims = _string_list(case.get("forbidden_claims"))
    return {
        "input": {
            "case_id": str(case.get("id", "")),
            "title": str(case.get("title", "")),
            "user_request": str(case.get("user_message", "")),
            "resume": resume,
            "jd": _build_jd(case),
            "target": target,
            "original": _target_or_first_bullet_text(resume, target),
        },
        "expected": {
            "expected_decision": str(expected_behavior.get("decision", "")),
            "expected_tool_calls": _string_list(
                expected_behavior.get("expected_tool_calls")
            ),
            "forbidden_claims": forbidden_claims,
            "acceptance": str(case.get("acceptance", "")),
            "expert_rewrite": _dict_value(case.get("expert_rewrite")),
        },
        "metadata": {
            "category": str(case.get("category", "")),
            "quality_checks": _string_list(case.get("quality_checks")),
            "source": "eval/cases/excellent_resume_agent_cases.json",
            "anthropic_split": _anthropic_split(case),
        },
    }


def _build_jd(case: dict[str, Any]) -> dict[str, str]:
    """用于把 case 中的 JD 文本整理成 harness 可消费结构。"""
    return {
        "title": str(case.get("title", "")),
        "company": "",
        "description": str(case.get("jd_text", "")),
    }


def _target_or_first_bullet_text(resume: dict[str, Any], target: dict[str, Any]) -> str:
    """用于读取目标 bullet；没有 target 时退回第一条 bullet。"""
    text = _target_bullet_text(resume, target)
    if text:
        return text
    return _first_bullet_text(resume)


def _target_bullet_text(resume: dict[str, Any], target: dict[str, Any]) -> str:
    """用于按 section/item/bullet 定位真实 case 的原始 bullet。"""
    section = resume.get(str(target.get("section", "")))
    if not isinstance(section, list):
        return ""
    for item in section:
        text = _target_bullet_from_item(item, target)
        if text:
            return text
    return ""


def _target_bullet_from_item(item: Any, target: dict[str, Any]) -> str:
    """用于在一个简历条目里读取目标 bullet 文本。"""
    if not isinstance(item, dict):
        return ""
    if str(item.get("id")) != str(target.get("item_id")):
        return ""
    highlights = item.get("highlights")
    if not isinstance(highlights, list):
        return ""
    for highlight in highlights:
        if isinstance(highlight, dict) and str(highlight.get("id")) == str(target.get("bullet_id")):
            return str(highlight.get("text", ""))
    return ""


def _first_bullet_text(resume: dict[str, Any]) -> str:
    """用于在澄清类 case 中读取第一条可见 bullet 作为原文。"""
    for section_name in ("work_experience", "projects"):
        text = _first_section_bullet_text(resume.get(section_name))
        if text:
            return text
    return ""


def _first_section_bullet_text(section: Any) -> str:
    """用于读取某个简历 section 的第一条 bullet 文本。"""
    if not isinstance(section, list):
        return ""
    for item in section:
        if not isinstance(item, dict):
            continue
        text = _first_highlight_text(item.get("highlights"))
        if text:
            return text
    return ""


def _first_highlight_text(highlights: Any) -> str:
    """用于从 highlights 列表里读取第一条文本。"""
    if not isinstance(highlights, list):
        return ""
    for highlight in highlights:
        if isinstance(highlight, dict) and highlight.get("text"):
            return str(highlight["text"])
    return ""


def _dict_value(value: Any) -> dict[str, Any]:
    """用于把可选 dict 字段规范化为空字典或原字典。"""
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    """用于把可选列表字段规范化成字符串列表。"""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _anthropic_split(case: dict[str, Any]) -> str:
    """用于读取 case 的 split 元数据。"""
    anthropic_eval = _dict_value(case.get("anthropic_eval"))
    return str(anthropic_eval.get("split", ""))


__all__ = [
    "REAL_CASES_PATH",
    "build_braintrust_eval_data",
    "load_real_eval_cases",
]
