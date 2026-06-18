"""用于实现新增教育、工作、项目或开源条目工具。"""

from __future__ import annotations

from typing import Any

from .document import ITEM_FIELD_WHITELIST, add_resume_item_to_document


def add_resume_item(
    resume_content: dict[str, Any],
    section: str,
    fields: Any,
    item_id: Any = None,
    reason: Any = None,
) -> dict[str, Any]:
    """用于在教育、工作、项目或开源板块新增一条结构化经历。"""
    return add_resume_item_to_document(
        resume_content=resume_content,
        section=section,
        fields=fields,
        item_id=item_id,
        reason=reason,
    )


__all__ = ["add_resume_item"]
