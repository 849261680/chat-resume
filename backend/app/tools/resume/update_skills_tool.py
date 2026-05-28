"""用于实现技能分类更新工具。"""

from __future__ import annotations

from typing import Any

from .shared import build_diff_payload, normalize_reason, snapshot

SKILL_UPDATE_MODES = {"replace", "merge"}


def update_skills(
    resume_content: dict[str, Any],
    category_id: str,
    items: Any,
    category: Any = None,
    mode: str = "replace",
    reason: Any = None,
) -> dict[str, Any]:
    """用于更新某个技能分类的名称和技能列表。"""
    skills = resume_content.get("skills")
    if not isinstance(skills, list):
        return {"success": False, "message": "当前没有可更新的技能分类，请先新增技能条目"}
    if mode not in SKILL_UPDATE_MODES:
        return {"success": False, "message": f"不支持的技能更新模式: {mode}"}

    idx = next(
        (i for i, item in enumerate(skills) if str(item.get("id")) == str(category_id)),
        None,
    )
    if idx is None:
        return {"success": False, "message": f"未找到 id={category_id} 的技能分类"}

    next_items = _normalize_skill_items(items)
    if not next_items:
        return {"success": False, "message": "技能列表不能为空"}

    before = snapshot(skills[idx])
    if category is not None:
        skills[idx]["category"] = str(category or "").strip()
    skills[idx]["items"] = _merge_items(skills[idx].get("items"), next_items, mode)
    resume_content["skills"] = skills

    diff_payload = build_diff_payload(
        title="技能专长 修改内容",
        before=before,
        after=skills[idx],
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": "已更新技能专长",
        "updated_section": "skills",
        **diff_payload,
    }


def _normalize_skill_items(items: Any) -> list[str]:
    """用于清理技能输入并保持首次出现顺序。"""
    raw_items = items if isinstance(items, list) else [items]
    normalized: list[str] = []
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _merge_items(existing: Any, next_items: list[str], mode: str) -> list[str]:
    """用于按更新模式生成最终技能列表。"""
    if mode == "replace":
        return next_items
    merged = _normalize_skill_items(existing)
    for item in next_items:
        if item not in merged:
            merged.append(item)
    return merged


__all__ = ["SKILL_UPDATE_MODES", "update_skills"]
