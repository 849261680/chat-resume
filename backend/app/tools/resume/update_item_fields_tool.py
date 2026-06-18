"""用于实现简历条目字段更新工具。"""

from __future__ import annotations

from typing import Any

from .document import ITEM_FIELD_WHITELIST, update_resume_item_fields


def update_item_fields(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    fields: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于更新工作、项目、开源或教育条目的非 bullet 字段。"""
    return update_resume_item_fields(
        resume_content=resume_content,
        section=section,
        item_id=item_id,
        fields=fields,
        reason=reason,
    )


__all__ = ["ITEM_FIELD_WHITELIST", "update_item_fields"]
