"""用于实现删除教育、工作、项目或开源条目工具。"""

from __future__ import annotations

from typing import Any

from .shared import SECTION_NAMES, build_diff_payload, find_item, normalize_reason, summarize_dict
from .update_item_fields_tool import ITEM_FIELD_WHITELIST


def remove_resume_item(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    reason: Any = None,
) -> dict[str, Any]:
    """用于从教育、工作、项目或开源板块删除一条完整经历。"""
    if section not in ITEM_FIELD_WHITELIST:
        return {"success": False, "message": f"{section} 不支持删除条目"}

    items, idx = find_item(resume_content, section, item_id)
    if items is None:
        return {"success": False, "message": f"{section} 数据格式异常"}
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    removed = items.pop(idx)
    resume_content[section] = items

    section_name = SECTION_NAMES.get(section, section)
    item_label = summarize_dict(removed)
    diff_payload = build_diff_payload(
        title=f"{section_name} / {item_label} 删除条目",
        before=removed,
        after="（已删除）",
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已从 {section_name} 中删除条目",
        "updated_section": section,
        **diff_payload,
    }


__all__ = ["remove_resume_item"]
