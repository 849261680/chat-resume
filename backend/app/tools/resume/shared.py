"""用于沉淀简历工具之间共享的辅助逻辑。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

SECTION_NAMES = {
    "education": "教育经历",
    "work_experience": "工作经历",
    "projects": "项目经历",
    "open_source": "开源经历",
}

HIGHLIGHT_SECTIONS = {"education", "work_experience", "projects", "open_source"}


def normalize_reason(reason: Any) -> str:
    """用于把任意理由输入标准化成可展示文本。"""
    return str(reason or "").strip()


def build_diff_payload(
    *,
    title: str,
    before: Any,
    after: Any,
    reason: str = "",
) -> dict[str, Any]:
    """用于生成前端确认和展示所需的统一 diff 结构。"""
    before_text = summarize_value(before)
    after_text = summarize_value(after)
    before_diff = serialize_diff_item_value(before)
    after_diff = serialize_diff_item_value(after)
    lines = [
        title,
        f"  改前：{before_text}",
        f"  改后：{after_text}",
    ]
    if reason:
        lines.append(f"  改动理由：{reason}")
    return {
        "diff_summary": "\n".join(lines),
        "diff_items": [
            {
                "before": before_diff,
                "after": after_diff,
                "reason": reason,
            }
        ],
    }


def summarize_value(value: Any, max_length: int = 160) -> str:
    """用于把复杂值压缩成适合 diff 展示的短文本。"""
    if value in (None, "", [], {}):
        return "空"

    if isinstance(value, str):
        return truncate(value.replace("\n", " "), max_length)

    if isinstance(value, list):
        if not value:
            return "空"
        items = []
        for item in value[:3]:
            if isinstance(item, dict):
                items.append(summarize_dict(item))
            else:
                items.append(truncate(str(item), 40))
        suffix = "" if len(value) <= 3 else f" 等共 {len(value)} 项"
        return truncate("；".join(items) + suffix, max_length)

    if isinstance(value, dict):
        return truncate(summarize_dict(value), max_length)

    return truncate(str(value), max_length)

def serialize_diff_item_value(value: Any) -> str:
    """用于保留结构化 diff 条目的完整值，供前端精简字段差异。"""
    if value in (None, "", [], {}):
        return "空"
    if isinstance(value, str):
        return value.replace("\n", " ")
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except TypeError:
            return str(value)
    return str(value)


def summarize_dict(data: dict[str, Any]) -> str:
    """用于优先提取字典中的关键字段生成摘要。"""
    preferred_keys = [
        "name",
        "title",
        "company",
        "school",
        "position",
        "role",
        "degree",
        "major",
        "duration",
        "description",
        "text",
    ]
    values = []
    for key in preferred_keys:
        raw = data.get(key)
        if raw:
            values.append(str(raw).replace("\n", " "))
    if not values:
        try:
            return json.dumps(data, ensure_ascii=False)
        except TypeError:
            return str(data)
    return " | ".join(values[:4])


def truncate(text: str, max_length: int) -> str:
    """用于限制展示文本长度，避免摘要过长。"""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def find_item(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
) -> tuple[list[dict[str, Any]], int | None] | tuple[None, None]:
    """用于在指定板块里定位目标条目及其索引。"""
    items: list[dict[str, Any]] = resume_content.get(section) or []
    if not isinstance(items, list):
        return None, None
    idx = next(
        (i for i, item in enumerate(items) if str(item.get("id")) == str(item_id)),
        None,
    )
    if idx is None:
        return items, None
    return items, idx


def snapshot(value: Any) -> Any:
    """用于在修改前保留一份可对比的深拷贝快照。"""
    return deepcopy(value)


__all__ = [
    "HIGHLIGHT_SECTIONS",
    "SECTION_NAMES",
    "build_diff_payload",
    "find_item",
    "normalize_reason",
    "snapshot",
    "summarize_dict",
]
