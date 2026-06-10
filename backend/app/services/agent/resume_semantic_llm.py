"""用于提供简历评分的 LLM 语义评审层，替代本地启发式。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.prompts.loader import load_prompt
from app.services.llm.chat_service import ChatService
from .resume_rule_score import extract_jd_text

logger = logging.getLogger(__name__)


async def review_resume_with_llm(
    resume_content: dict[str, Any],
    _rule_dimensions: list[dict[str, Any]],
) -> dict[str, Any]:
    """用于调用 LLM 对整份简历做语义级评审。"""
    resume_text = _build_resume_text(resume_content)
    jd_text = extract_jd_text(resume_content) or "（未提供目标岗位 JD）"

    spec = load_prompt("resume_semantic_judge")
    system_prompt = spec.render(resume_text=resume_text, jd_text=jd_text)

    async with ChatService() as chat:
        response = await chat.chat_completion(
            messages=[{"role": "user", "content": "请评价这份简历"}],
            temperature=spec.model_defaults.get("temperature", 0.3),
            max_tokens=spec.model_defaults.get("max_tokens", 2000),
            stream=False,
            system_prompt=system_prompt,
        )

    content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
    finish_reason = (
        response.get("choices", [{}])[0]
        .get("finish_reason", "")
    )
    if finish_reason == "length":
        logger.warning(
            "LLM 语义评审响应被 max_tokens 截断，降级为本地启发式"
        )
        raise ValueError("LLM 响应被截断，JSON 不完整")
    return _parse_llm_response(content)


def _build_resume_text(resume_content: dict[str, Any]) -> str:
    """用于把简历内容整理成 LLM 可读的结构化文本。"""
    sections: list[str] = []

    # 个人信息
    personal = resume_content.get("personal_info") or {}
    name = personal.get("name", "")
    if name:
        sections.append(f"姓名：{name}")

    # 个人总结
    summary = (resume_content.get("summary") or {}).get("text", "")
    if summary:
        sections.append(f"个人总结：{summary}")

    # 各经历板块
    section_labels = {
        "education": "教育经历",
        "work_experience": "工作经历",
        "projects": "项目经历",
    }
    for section_key, label in section_labels.items():
        items = resume_content.get(section_key) or []
        if not items:
            continue
        sections.append(f"\n## {label}")
        for item in items:
            item_parts = _summarize_item(item)
            sections.append(item_parts)

    # 技能
    skills = resume_content.get("skills") or []
    if skills:
        sections.append("\n## 技能")
        for category in skills:
            cat_name = category.get("category", "")
            items = category.get("items", [])
            if cat_name and items:
                sections.append(f"{cat_name}：{', '.join(items)}")

    return "\n".join(sections)


def _summarize_item(item: dict[str, Any]) -> str:
    """用于把单个经历条目转成可读文本。"""
    parts: list[str] = []

    # 提取关键字段
    for field in ("company", "school", "name", "position", "role", "degree", "major"):
        value = item.get(field)
        if value:
            parts.append(str(value))

    duration = item.get("duration")
    if duration:
        parts.append(f"({duration})")

    header = " | ".join(parts) if parts else "（条目）"

    # 提取要点
    highlights = item.get("highlights") or []
    bullet_lines = []
    for highlight in highlights:
        text = str(highlight.get("text", "")).strip()
        if text:
            bullet_lines.append(f"  - {text}")

    if bullet_lines:
        return f"{header}\n" + "\n".join(bullet_lines)
    return header


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """用于从 LLM 返回文本中提取结构化评审结果。"""
    text = raw.strip()

    # 去掉 markdown 代码块标记
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # 尝试修复截断的 JSON：补全未闭合的括号
        repaired = _try_repair_json(text)
        if repaired is not None:
            logger.info("LLM 语义评审 JSON 修复成功")
            result = repaired
        else:
            logger.warning(
                "LLM 语义评审结果不是有效 JSON: %s", text[:300]
            )
            raise ValueError(
                f"LLM 语义评审结果解析失败: {text[:200]}"
            ) from None

    # 提取维度
    raw_dimensions = result.get("dimensions", [])
    dimensions = [_normalize_dimension(dim) for dim in raw_dimensions]

    # 计算总分
    if dimensions:
        score = round(sum(dim["score"] for dim in dimensions) / len(dimensions))
    else:
        score = 0

    # 提取弱信号和优先动作
    weak_signals = _normalize_weak_signals(result.get("weak_signals", []))
    priority_actions = _normalize_priority_actions(result.get("priority_actions", []))

    return {
        "status": "available",
        "method": "llm_semantic_review",
        "overall": {
            "score": score,
            "level": _level(score),
            "reason": str(result.get("overall_reason", "")),
        },
        "dimensions": dimensions,
        "selling_points": _extract_selling_points(dimensions),
        "weak_signals": weak_signals,
        "interview_risks": [
            f"如果被追问：{signal['issue']}，当前简历证据不足。"
            for signal in weak_signals[:4]
        ],
        "priority_actions": priority_actions,
    }


def _try_repair_json(text: str) -> dict[str, Any] | None:
    """用于尝试修复截断的 JSON，补全未闭合的括号和数组。"""
    repaired = text.rstrip()
    # 去掉末尾的逗号和空白
    while repaired and repaired[-1] in (',', ' ', '\n', '\r', '\t'):
        repaired = repaired[:-1]
    # 统计未闭合的括号
    open_braces = 0
    open_brackets = 0
    in_string = False
    escape_next = False
    for ch in repaired:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            open_braces += 1
        elif ch == '}':
            open_braces -= 1
        elif ch == '[':
            open_brackets += 1
        elif ch == ']':
            open_brackets -= 1
    # 补全未闭合的字符串
    if in_string:
        repaired += '"'
    # 补全括号
    repaired += ']' * max(0, open_brackets)
    repaired += '}' * max(0, open_braces)
    try:
        return json.loads(repaired)
    except (json.JSONDecodeError, ValueError):
        return None


def _normalize_dimension(dim: dict[str, Any]) -> dict[str, Any]:
    """用于把 LLM 返回的维度结果规范化。"""
    return {
        "key": str(dim.get("key", "unknown")),
        "score": max(0, min(100, int(dim.get("score", 0)))),
        "evidence": str(dim.get("evidence", "")),
        "risk": _risk(int(dim.get("score", 0))),
        "suggestion": str(dim.get("suggestion", "")),
    }


def _normalize_weak_signals(signals: list[Any]) -> list[dict[str, Any]]:
    """用于把 LLM 返回的弱信号规范化。"""
    result = []
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        item_id = str(signal.get("item_id") or "")
        bullet_id = str(signal.get("bullet_id") or "")
        target = {}
        if item_id and bullet_id:
            target = {"item_id": item_id, "bullet_id": bullet_id}
        result.append({
            "issue": str(signal.get("issue", "")),
            "target": target,
            "rewrite_direction": str(signal.get("rewrite_direction", "")),
            "tool_hint": str(signal.get("tool_hint", "update_bullet")),
        })
    return result[:6]


def _normalize_priority_actions(actions: list[Any]) -> list[dict[str, Any]]:
    """用于把 LLM 返回的优先动作规范化。"""
    result = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        item_id = str(action.get("item_id") or "")
        bullet_id = str(action.get("bullet_id") or "")
        target = {}
        if item_id and bullet_id:
            target = {"item_id": item_id, "bullet_id": bullet_id}
        tool_hint = "update_bullet" if target else "update_resume"
        if "add" in str(action.get("rewrite_direction", "")).lower():
            tool_hint = "add_bullet"
        result.append({
            "source": "semantic_review",
            "dimension_key": "semantic_review",
            "dimension_name": "语义评审",
            "title": str(action.get("rewrite_direction", "")),
            "reason": str(action.get("reason", "")),
            "target": target,
            "section": "",
            "tool_hint": tool_hint,
        })
    return result[:6]


def _extract_selling_points(dimensions: list[dict[str, Any]]) -> list[str]:
    """用于从高分维度中提取候选人卖点。"""
    return [
        dim["suggestion"]
        for dim in dimensions
        if dim["score"] >= 80 and dim.get("suggestion")
    ]


def _level(score: int) -> str:
    """用于把语义分转成等级。"""
    if score >= 85:
        return "strong"
    if score >= 70:
        return "medium"
    return "weak"


def _risk(score: int) -> str:
    """用于把单项语义分转成风险标签。"""
    if score >= 80:
        return "low"
    if score >= 60:
        return "medium"
    return "high"


__all__ = ["review_resume_with_llm"]
