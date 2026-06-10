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
_QUALITY_EDIT_TOOLS = {"update_bullet", "add_bullet", "update_overview", "update_summary"}
_WEAK_PREFIXES = ("负责", "参与", "协助", "帮助", "配合", "完成")
_ACTION_WORDS = (
    "设计",
    "搭建",
    "推动",
    "重构",
    "实现",
    "开发",
    "优化",
    "构建",
    "建立",
    "改造",
    "落地",
    "迁移",
    "解决",
    "修复",
    "主导",
)
_RESULT_WORDS = (
    "提升",
    "降低",
    "缩短",
    "减少",
    "增长",
    "覆盖",
    "支撑",
    "降到",
    "从",
    "节省",
)
_KEYWORD_STUFFING_TERMS = (
    "后端",
    "前端",
    "接口",
    "数据库",
    "数据库优化",
    "系统",
    "高并发",
    "分布式",
    "微服务",
    "稳定性",
)


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
        quality_issue = _quality_issue(tool_name, after_text)
        if quality_issue is None:
            return _passed()
        return {
            "passed": False,
            "error_type": "low_quality_resume_edit",
            "recoverable": True,
            "quality_issue": quality_issue,
            "message": quality_issue,
        }
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


def _quality_issue(tool_name: str, after_text: str) -> str | None:
    """用于判断候选改写是否具备优秀简历的最低表达质量。"""
    if tool_name not in _QUALITY_EDIT_TOOLS:
        return None
    text = " ".join(after_text.split())
    if not text:
        return None
    if _looks_like_keyword_stuffing(text):
        return "这次改写主要是在堆关键词，没有把经历写具体；请补充动作、方案和可面试追问的结果证据。"
    if _starts_weak_without_result(text):
        return "这次改写仍以弱动词开头且缺少具体结果；请改成更具体的动作、方案和结果。"
    return None


def _looks_like_keyword_stuffing(text: str) -> bool:
    """用于识别缺少动作结果、只罗列岗位关键词的候选 bullet。"""
    matched_terms = [term for term in _KEYWORD_STUFFING_TERMS if term in text]
    has_many_terms = len(matched_terms) >= 3
    has_action = any(word in text for word in _ACTION_WORDS)
    has_result = any(word in text for word in _RESULT_WORDS) or bool(_NUMBER_CLAIM_RE.search(text))
    return has_many_terms and not (has_action and has_result)


def _starts_weak_without_result(text: str) -> bool:
    """用于识别仍停留在泛泛职责描述的候选 bullet。"""
    if not text.startswith(_WEAK_PREFIXES):
        return False
    has_result = any(word in text for word in _RESULT_WORDS) or bool(_NUMBER_CLAIM_RE.search(text))
    has_action = any(word in text for word in _ACTION_WORDS)
    return not (has_action and has_result)


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
        if isinstance(value.get("text"), str):
            return value["text"]
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
