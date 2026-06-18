"""用于实现删除教育、工作、项目或开源条目工具。"""

from __future__ import annotations

from typing import Any

from .document import ITEM_FIELD_WHITELIST, remove_resume_item_from_document


def remove_resume_item(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    reason: Any = None,
) -> dict[str, Any]:
    """用于从教育、工作、项目或开源板块删除一条完整经历。"""
    return remove_resume_item_from_document(
        resume_content=resume_content,
        section=section,
        item_id=item_id,
        reason=reason,
    )


__all__ = ["remove_resume_item"]
