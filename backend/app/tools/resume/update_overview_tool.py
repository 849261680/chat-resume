"""用于实现项目简介更新工具。"""

from __future__ import annotations

from typing import Any

from .document import update_resume_overview


def update_overview(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    overview: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于只修改项目条目的 overview 文本。"""
    return update_resume_overview(
        resume_content=resume_content,
        section=section,
        item_id=item_id,
        overview=overview,
        reason=reason,
    )


__all__ = ["update_overview"]
