"""用于实现技能分类更新工具。"""

from __future__ import annotations

from typing import Any

from .document import SKILL_UPDATE_MODES, update_resume_skills


def update_skills(
    resume_content: dict[str, Any],
    category_id: str,
    items: Any = None,
    category: Any = None,
    mode: str = "replace",
    reason: Any = None,
) -> dict[str, Any]:
    """用于新增、更新或删除某个技能分类。"""
    return update_resume_skills(
        resume_content=resume_content,
        category_id=category_id,
        items=items,
        category=category,
        mode=mode,
        reason=reason,
    )


__all__ = ["SKILL_UPDATE_MODES", "update_skills"]
