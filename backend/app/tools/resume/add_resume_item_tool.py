"""用于实现新增教育、工作、项目或开源条目工具。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .shared import build_diff_payload, normalize_reason
from .update_item_fields_tool import ITEM_FIELD_WHITELIST

_ITEM_ID_PREFIX = {
    "education": "edu",
    "work_experience": "work",
    "projects": "proj",
    "open_source": "oss",
}


def add_resume_item(
    resume_content: dict[str, Any],
    section: str,
    fields: Any,
    item_id: Any = None,
    reason: Any = None,
) -> dict[str, Any]:
    """用于在教育、工作、项目或开源板块新增一条结构化经历。"""
    if section not in ITEM_FIELD_WHITELIST:
        return {"success": False, "message": f"{section} 不支持新增条目"}
    if not isinstance(fields, dict) or not fields:
        return {"success": False, "message": "新增条目字段不能为空"}

    invalid_fields = sorted(set(str(key) for key in fields) - ITEM_FIELD_WHITELIST[section])
    if invalid_fields:
        return {
            "success": False,
            "message": f"{section} 不支持新增字段: {', '.join(invalid_fields)}",
        }

    items = resume_content.get(section)
    if items is None:
        items = []
    if not isinstance(items, list):
        return {"success": False, "message": f"{section} 数据格式异常"}

    next_id = _normalize_item_id(section, item_id)
    if any(str(item.get("id")) == next_id for item in items if isinstance(item, dict)):
        return {"success": False, "message": f"{section} 已存在 id={next_id} 的条目"}

    item = {"id": next_id}
    for key, value in fields.items():
        item[str(key)] = _normalize_item_field_value(value)
    items.append(item)
    resume_content[section] = items

    diff_payload = build_diff_payload(
        title=f"{section} 新增条目",
        before="（新增）",
        after=item,
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": "已新增简历条目",
        "updated_section": section,
        **diff_payload,
    }


def _normalize_item_id(section: str, item_id: Any) -> str:
    """用于优先使用模型给定 id，缺省时生成稳定前缀 id。"""
    candidate = str(item_id or "").strip()
    if candidate:
        return candidate
    return f"{_ITEM_ID_PREFIX[section]}_{uuid4().hex[:12]}"


def _normalize_item_field_value(value: Any) -> Any:
    """用于清理新增条目的普通文本和链接列表字段。"""
    if isinstance(value, list):
        return value
    return str(value or "").strip()


__all__ = ["add_resume_item"]
