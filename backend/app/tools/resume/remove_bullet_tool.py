"""用于实现删除简历 bullet 工具。"""

from __future__ import annotations

from typing import Any

from .shared import (
    HIGHLIGHT_SECTIONS,
    SECTION_NAMES,
    build_diff_payload,
    find_item,
    normalize_reason,
    summarize_dict,
)


def remove_bullet(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    bullet_id: str,
    reason: Any = None,
) -> dict[str, Any]:
    """用于从指定条目中删除一条已有 resume bullet。"""
    if section not in HIGHLIGHT_SECTIONS:
        return {"success": False, "message": f"{section} 不支持要点编辑"}

    items, idx = find_item(resume_content, section, item_id)
    if items is None:
        return {"success": False, "message": f"{section} 数据格式异常"}
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    highlights = items[idx].get("highlights") or []
    if not isinstance(highlights, list):
        return {"success": False, "message": "bullets 数据格式异常"}

    remaining = [
        highlight
        for highlight in highlights
        if str(highlight.get("id")) != str(bullet_id)
    ]
    if len(remaining) == len(highlights):
        return {"success": False, "message": f"未找到 id={bullet_id} 的要点"}

    removed = next(
        highlight
        for highlight in highlights
        if str(highlight.get("id")) == str(bullet_id)
    )
    items[idx]["highlights"] = remaining
    resume_content[section] = items

    section_name = SECTION_NAMES.get(section, section)
    item_label = summarize_dict(items[idx])
    diff_payload = build_diff_payload(
        title=f"{section_name} / {item_label} 删除要点",
        before=removed,
        after="（已删除）",
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已从 {section_name} 中删除要点",
        "updated_section": section,
        **diff_payload,
    }


__all__ = ["remove_bullet"]
