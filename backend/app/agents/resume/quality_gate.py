"""用于在简历 Agent diff 进入确认前检查事实约束。"""

from __future__ import annotations

import json
import re
from typing import Any

_NUMBER_CLAIM_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|万|千|ms|s|秒|人|用户|DAU|QPS)?", re.IGNORECASE)
_TECH_TERMS = (
    "Redis",
    "Kafka",
    "RabbitMQ",
    "Kubernetes",
    "K8s",
    "Docker",
    "Spring Cloud",
    "Dubbo",
    "MySQL",
    "PostgreSQL",
    "MongoDB",
    "ElasticSearch",
    "Elasticsearch",
    "React",
    "Vue",
    "TypeScript",
    "FastAPI",
    "Django",
    "RAG",
    "LangChain",
    "向量数据库",
    "微服务",
    "高并发",
)
_EDIT_TOOLS = {
    "update_summary",
    "update_profile",
    "upsert_job_application",
    "update_item_fields",
    "update_skills",
    "update_overview",
    "update_bullet",
    "add_bullet",
    "remove_bullet",
}


def evaluate_resume_edit_quality(
    *,
    resume_content: dict[str, Any],
    tool_name: str,
    tool_input: dict[str, Any],
    preview_result: dict[str, Any],
    user_message: str = "",
) -> dict[str, Any]:
    """用于检查一次简历编辑 diff 是否引入无来源事实。"""
    if tool_name not in _EDIT_TOOLS:
        return _passed()
    if preview_result.get("success") is False:
        return _passed()

    after_text = _preview_after_text(preview_result, tool_input)
    if not after_text:
        return _passed()

    source_text = _source_text(resume_content, preview_result, user_message)
    unsupported = _unsupported_claims(after_text, source_text)
    if not unsupported:
        return _passed()
    return {
        "passed": False,
        "error_type": "unsupported_resume_claim",
        "recoverable": True,
        "unsupported_claims": unsupported,
        "message": (
            "这次改写引入了原简历或用户输入没有支撑的新事实："
            + "、".join(unsupported[:6])
            + "。请先向用户确认这些事实，或改成只基于已有事实的表达。"
        ),
    }


def _passed() -> dict[str, Any]:
    """用于返回通过门禁的统一结构。"""
    return {"passed": True}


def _preview_after_text(preview_result: dict[str, Any], tool_input: dict[str, Any]) -> str:
    """用于从 diff 或工具参数中读取候选改写文本。"""
    chunks: list[str] = []
    diff_items = preview_result.get("diff_items")
    if isinstance(diff_items, list):
        for item in diff_items:
            if isinstance(item, dict):
                chunks.append(_text_from_value(item.get("after")))
    result_diff_items = preview_result.get("result", {}).get("diff_items")
    if isinstance(result_diff_items, list):
        for item in result_diff_items:
            if isinstance(item, dict):
                chunks.append(_text_from_value(item.get("after")))
    if isinstance(tool_input.get("text"), str):
        chunks.append(tool_input["text"])
    return "\n".join(chunk for chunk in chunks if chunk)


def _source_text(
    resume_content: dict[str, Any],
    preview_result: dict[str, Any],
    user_message: str,
) -> str:
    """用于汇总可作为事实来源的原简历、改前 diff 和用户本轮输入。"""
    chunks = [_text_from_value(resume_content), user_message]
    diff_items = preview_result.get("diff_items")
    if isinstance(diff_items, list):
        chunks.extend(
            _text_from_value(item.get("before"))
            for item in diff_items
            if isinstance(item, dict)
        )
    result_diff_items = preview_result.get("result", {}).get("diff_items")
    if isinstance(result_diff_items, list):
        chunks.extend(
            _text_from_value(item.get("before"))
            for item in result_diff_items
            if isinstance(item, dict)
        )
    return "\n".join(chunk for chunk in chunks if chunk)


def _unsupported_claims(after_text: str, source_text: str) -> list[str]:
    """用于找出候选文本中没有来源支撑的数字和技术栈。"""
    source_lower = source_text.lower()
    claims = []
    claims.extend(
        claim
        for claim in _extract_number_claims(after_text)
        if claim.lower() not in source_lower
    )
    claims.extend(
        term
        for term in _extract_tech_terms(after_text)
        if term.lower() not in source_lower
    )
    return _dedupe(claims)


def _extract_number_claims(text: str) -> list[str]:
    """用于提取候选改写中的数字型事实。"""
    return [match.group(0).strip() for match in _NUMBER_CLAIM_RE.finditer(text)]


def _extract_tech_terms(text: str) -> list[str]:
    """用于提取候选改写中的技术栈和关键能力事实。"""
    lowered = text.lower()
    return [term for term in _TECH_TERMS if term.lower() in lowered]


def _text_from_value(value: Any) -> str:
    """用于把 diff 字符串、JSON 字符串或结构化值压平成文本。"""
    if value is None:
        return ""
    if isinstance(value, str):
        parsed = _parse_json_string(value)
        if parsed is not None:
            return _text_from_value(parsed)
        return value
    if isinstance(value, dict):
        return "\n".join(_text_from_value(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text_from_value(item) for item in value)
    return str(value)


def _parse_json_string(value: str) -> Any | None:
    """用于解析 diff 中序列化后的 JSON 值。"""
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _dedupe(items: list[str]) -> list[str]:
    """用于在保持顺序的前提下去重。"""
    seen: set[str] = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


__all__ = ["evaluate_resume_edit_quality"]
