"""用于实现删除简历 bullet 工具。"""

from __future__ import annotations

from typing import Any

from .document import remove_resume_bullet


def remove_bullet(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    bullet_id: str,
    reason: Any = None,
) -> dict[str, Any]:
    """用于从指定条目中删除一条已有 resume bullet。"""
    return remove_resume_bullet(
        resume_content=resume_content,
        section=section,
        item_id=item_id,
        bullet_id=bullet_id,
        reason=reason,
    )


__all__ = ["remove_bullet"]
