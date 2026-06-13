"""用于实现简历条目字段更新工具。"""

from __future__ import annotations

from typing import Any

from .shared import build_diff_payload, find_item, normalize_reason, snapshot, summarize_dict

ITEM_FIELD_WHITELIST = {
    "education": {
        "school",
        "major",
        "degree",
        "duration",
        "start_date",
        "end_date",
        "location",
        "gpa",
    },
    "work_experience": {
        "company",
        "position",
        "duration",
        "start_date",
        "end_date",
        "location",
        "employment_type",
    },
    "projects": {
        "name",
        "overview",
        "role",
        "duration",
        "start_date",
        "end_date",
        "github_url",
        "demo_url",
        "links",
    },
    "open_source": {
        "name",
        "overview",
        "role",
        "duration",
        "start_date",
        "end_date",
        "github_url",
        "demo_url",
        "links",
    },
}


def update_item_fields(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    fields: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于更新工作、项目、开源或教育条目的非 bullet 字段。"""
    if section not in ITEM_FIELD_WHITELIST:
        return {"success": False, "message": f"{section} 不支持字段更新"}
    if not isinstance(fields, dict) or not fields:
        return {"success": False, "message": "条目更新字段不能为空"}

    invalid_fields = sorted(set(str(key) for key in fields) - ITEM_FIELD_WHITELIST[section])
    if invalid_fields:
        return {
            "success": False,
            "message": f"{section} 不支持修改字段: {', '.join(invalid_fields)}",
        }

    items, idx = find_item(resume_content, section, item_id)
    if items is None:
        return {"success": False, "message": f"{section} 数据格式异常"}
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    before = snapshot(items[idx])
    for key, value in fields.items():
        items[idx][str(key)] = _normalize_item_field_value(str(key), value)
    resume_content[section] = items

    diff_payload = build_diff_payload(
        title=f"{summarize_dict(items[idx])} 修改字段",
        before={key: before.get(key) for key in fields},
        after={key: items[idx].get(key) for key in fields},
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": "已更新简历条目字段",
        "updated_section": section,
        **diff_payload,
    }


def _normalize_item_field_value(key: str, value: Any) -> Any:
    """用于按字段类型清理条目字段值。"""
    if key == "links":
        return value if isinstance(value, list) else [str(value).strip()]
    if key == "is_current":
        return bool(value)
    return str(value or "").strip()


__all__ = ["ITEM_FIELD_WHITELIST", "update_item_fields"]
