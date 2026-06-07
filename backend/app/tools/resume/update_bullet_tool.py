"""用于实现简历 bullet 文本更新工具。"""

from __future__ import annotations

from typing import Any

from .shared import (
    HIGHLIGHT_SECTIONS,
    SECTION_NAMES,
    build_diff_payload,
    find_item,
    normalize_reason,
    snapshot,
    summarize_dict,
)


def update_bullet(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    bullet_id: str,
    text: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于精确更新某条 resume bullet 的文本内容。"""
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

    next_text = str(text or "").strip()
    for highlight in highlights:
        if str(highlight.get("id")) == str(bullet_id):
            current_text = str(highlight.get("text") or "").strip()
            if next_text == current_text:
                return {
                    "success": False,
                    "message": "新旧 bullet 内容一致，未执行修改；如果无需修改，请直接回复用户，不要调用 update_bullet。",
                }
            before = snapshot(highlight)
            highlight["text"] = next_text
            section_name = SECTION_NAMES.get(section, section)
            item_label = summarize_dict(items[idx])
            diff_payload = build_diff_payload(
                title=f"{section_name} / {item_label} 修改要点",
                before=before,
                after=highlight,
                reason=normalize_reason(reason),
            )
            return {
                "success": True,
                "message": f"已更新 {section_name} 中的要点",
                "updated_section": section,
                **diff_payload,
            }
    return {"success": False, "message": f"未找到 id={bullet_id} 的要点"}


__all__ = ["update_bullet"]
