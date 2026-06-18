"""用于实现新增简历 bullet 工具。"""

from __future__ import annotations

from typing import Any

from .document import add_resume_bullet


def add_bullet(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    text: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于在指定条目下追加一条新的 resume bullet。"""
    return add_resume_bullet(
        resume_content=resume_content,
        section=section,
        item_id=item_id,
        text=text,
        reason=reason,
    )


__all__ = ["add_bullet"]
