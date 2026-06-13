"""用于实现技能分类更新工具。"""

from __future__ import annotations

from typing import Any

from .shared import build_diff_payload, normalize_reason, snapshot

SKILL_UPDATE_MODES = {"replace", "merge", "remove"}


def update_skills(
    resume_content: dict[str, Any],
    category_id: str,
    items: Any = None,
    category: Any = None,
    mode: str = "replace",
    reason: Any = None,
) -> dict[str, Any]:
    """用于新增、更新或删除某个技能分类。"""
    skills = resume_content.get("skills")
    if skills is None:
        skills = []
    if not isinstance(skills, list):
        return {"success": False, "message": "技能分类数据格式异常"}
    if mode not in SKILL_UPDATE_MODES:
        return {"success": False, "message": f"不支持的技能更新模式: {mode}"}

    idx = next(
        (i for i, item in enumerate(skills) if str(item.get("id")) == str(category_id)),
        None,
    )
    if mode == "remove":
        return _remove_skill_category(
            resume_content,
            skills=skills,
            idx=idx,
            category_id=category_id,
            reason=reason,
        )

    next_items = _normalize_skill_items(items)
    if not next_items:
        return {"success": False, "message": "技能列表不能为空"}

    if idx is None:
        return _add_skill_category(
            resume_content,
            skills=skills,
            category_id=category_id,
            category=category,
            items=next_items,
            reason=reason,
        )

    return _update_skill_category(
        resume_content,
        skills=skills,
        idx=idx,
        category=category,
        items=next_items,
        mode=mode,
        reason=reason,
    )


def _add_skill_category(
    resume_content: dict[str, Any],
    *,
    skills: list[dict[str, Any]],
    category_id: str,
    category: Any,
    items: list[str],
    reason: Any,
) -> dict[str, Any]:
    """用于新增一个技能分类。"""
    skill_category = {
        "id": str(category_id).strip(),
        "category": str(category or "其他").strip() or "其他",
        "items": items,
    }
    skills.append(skill_category)
    resume_content["skills"] = skills
    diff_payload = build_diff_payload(
        title="技能专长 新增分类",
        before="（新增）",
        after=skill_category,
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": "已新增技能分类",
        "updated_section": "skills",
        **diff_payload,
    }


def _update_skill_category(
    resume_content: dict[str, Any],
    *,
    skills: list[dict[str, Any]],
    idx: int,
    category: Any,
    items: list[str],
    mode: str,
    reason: Any,
) -> dict[str, Any]:
    """用于更新一个已有技能分类。"""

    before = snapshot(skills[idx])
    if category is not None:
        skills[idx]["category"] = str(category or "").strip()
    skills[idx]["items"] = _merge_items(skills[idx].get("items"), items, mode)
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


def _remove_skill_category(
    resume_content: dict[str, Any],
    *,
    skills: list[dict[str, Any]],
    idx: int | None,
    category_id: str,
    reason: Any,
) -> dict[str, Any]:
    """用于删除一个已有技能分类。"""
    if idx is None:
        return {"success": False, "message": f"未找到 id={category_id} 的技能分类"}

    removed = skills.pop(idx)
    resume_content["skills"] = skills
    diff_payload = build_diff_payload(
        title="技能专长 删除分类",
        before=removed,
        after="（已删除）",
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": "已删除技能分类",
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
