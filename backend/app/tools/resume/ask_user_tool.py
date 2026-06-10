"""用于让简历 Agent 向用户发起结构化追问。"""

from __future__ import annotations

from typing import Any

_MAX_OPTIONS = 5


def ask_user(
    resume_content: dict[str, Any],
    question: str,
    options: list[str],
    category: str = "other",
    context: str = "",
    allow_custom: bool = True,
) -> dict[str, Any]:
    """用于生成前端可渲染的用户信息询问卡片载荷。"""
    del resume_content
    clean_question = question.strip()
    clean_options = _normalize_options(options)
    if not clean_question:
        return {"success": False, "message": "question 不能为空"}
    if not clean_options:
        return {"success": False, "message": "options 至少需要一个选项"}
    return {
        "success": True,
        "terminate": True,
        "message": clean_question,
        "user_input_request": {
            "question": clean_question,
            "options": clean_options,
            "category": category.strip() or "other",
            "context": context.strip(),
            "allow_custom": bool(allow_custom),
        },
    }


def _normalize_options(options: list[str]) -> list[str]:
    """用于清理并限制询问卡片选项数量。"""
    clean_options: list[str] = []
    seen: set[str] = set()
    for option in options:
        clean_option = str(option).strip()
        if not clean_option or clean_option in seen:
            continue
        clean_options.append(clean_option)
        seen.add(clean_option)
        if len(clean_options) >= _MAX_OPTIONS:
            break
    return clean_options


__all__ = ["ask_user"]
