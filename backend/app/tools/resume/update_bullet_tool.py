"""用于实现简历 bullet 文本更新工具。"""

from __future__ import annotations

from typing import Any

from .document import update_resume_bullet


def update_bullet(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    bullet_id: str,
    text: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于精确更新某条 resume bullet 的文本内容。"""
    return update_resume_bullet(
        resume_content=resume_content,
        section=section,
        item_id=item_id,
        bullet_id=bullet_id,
        text=text,
        reason=reason,
    )


__all__ = ["update_bullet"]
