"""用于集中处理简历文档的结构化变更。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .shared import (
    HIGHLIGHT_SECTIONS,
    SECTION_NAMES,
    build_diff_payload,
    find_item,
    normalize_reason,
    snapshot,
    summarize_dict,
)

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
SKILL_UPDATE_MODES = {"replace", "merge", "remove"}
_ITEM_ID_PREFIX = {
    "education": "edu",
    "work_experience": "work",
    "projects": "proj",
    "open_source": "oss",
}


def update_resume_bullet(
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
        if str(highlight.get("id")) != str(bullet_id):
            continue
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


def add_resume_bullet(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    text: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于在指定条目下追加一条新的 resume bullet。"""
    if section not in HIGHLIGHT_SECTIONS:
        return {"success": False, "message": f"{section} 不支持要点编辑"}

    items, idx = find_item(resume_content, section, item_id)
    if items is None:
        return {"success": False, "message": f"{section} 数据格式异常"}
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    next_text = str(text or "").strip()
    if not next_text:
        return {"success": False, "message": "要点文本不能为空"}

    highlight = {"id": f"{item_id}_hl_{uuid4().hex[:8]}", "text": next_text}
    highlights = items[idx].get("highlights")
    if not isinstance(highlights, list):
        highlights = []
        items[idx]["highlights"] = highlights
    highlights.append(highlight)
    resume_content[section] = items

    section_name = SECTION_NAMES.get(section, section)
    item_label = summarize_dict(items[idx])
    diff_payload = build_diff_payload(
        title=f"{section_name} / {item_label} 新增要点",
        before="（新增）",
        after=highlight,
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已在 {section_name} 中新增要点",
        "updated_section": section,
        **diff_payload,
    }


def remove_resume_bullet(
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
        highlight for highlight in highlights if str(highlight.get("id")) == str(bullet_id)
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


def add_resume_item_to_document(
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

    invalid_fields = sorted(
        set(str(key) for key in fields) - ITEM_FIELD_WHITELIST[section]
    )
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

    next_id = normalize_resume_item_id(section, item_id)
    if any(str(item.get("id")) == next_id for item in items if isinstance(item, dict)):
        return {"success": False, "message": f"{section} 已存在 id={next_id} 的条目"}

    item = {"id": next_id}
    for key, value in fields.items():
        item[str(key)] = normalize_new_resume_item_field_value(value)
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


def remove_resume_item_from_document(
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


def update_resume_item_fields(
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

    invalid_fields = sorted(
        set(str(key) for key in fields) - ITEM_FIELD_WHITELIST[section]
    )
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
        items[idx][str(key)] = normalize_resume_item_field_value(str(key), value)
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


def update_resume_overview(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    overview: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于只修改项目条目的 overview 文本。"""
    if section != "projects":
        return {"success": False, "message": "只有 projects 支持 overview 编辑"}

    items, idx = find_item(resume_content, section, item_id)
    if items is None:
        return {"success": False, "message": f"{section} 数据格式异常"}
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    next_overview = str(overview or "").strip()
    before = snapshot(items[idx])
    items[idx]["overview"] = next_overview
    resume_content[section] = items

    section_name = SECTION_NAMES.get(section, section)
    item_label = summarize_dict(items[idx])
    diff_payload = build_diff_payload(
        title=f"{section_name} / {item_label} 修改摘要",
        before=before.get("overview"),
        after=next_overview,
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已更新 {section_name} 的简介",
        "updated_section": section,
        **diff_payload,
    }


def update_resume_skills(
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
        return remove_resume_skill_category(
            resume_content,
            skills=skills,
            idx=idx,
            category_id=category_id,
            reason=reason,
        )

    next_items = normalize_resume_skill_items(items)
    if not next_items:
        return {"success": False, "message": "技能列表不能为空"}
    if idx is None:
        return add_resume_skill_category(
            resume_content,
            skills=skills,
            category_id=category_id,
            category=category,
            items=next_items,
            reason=reason,
        )
    return update_resume_skill_category(
        resume_content,
        skills=skills,
        idx=idx,
        category=category,
        items=next_items,
        mode=mode,
        reason=reason,
    )


def normalize_resume_item_field_value(key: str, value: Any) -> Any:
    """用于按字段类型清理条目字段值。"""
    if key == "links":
        return value if isinstance(value, list) else [str(value).strip()]
    if key == "is_current":
        return bool(value)
    return str(value or "").strip()


def normalize_new_resume_item_field_value(value: Any) -> Any:
    """用于清理新增条目的普通文本和链接列表字段。"""
    if isinstance(value, list):
        return value
    return str(value or "").strip()


def normalize_resume_item_id(section: str, item_id: Any) -> str:
    """用于优先使用模型给定 id，缺省时生成稳定前缀 id。"""
    candidate = str(item_id or "").strip()
    if candidate:
        return candidate
    return f"{_ITEM_ID_PREFIX[section]}_{uuid4().hex[:12]}"


def add_resume_skill_category(
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


def update_resume_skill_category(
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
    skills[idx]["items"] = merge_resume_skill_items(skills[idx].get("items"), items, mode)
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


def remove_resume_skill_category(
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


def normalize_resume_skill_items(items: Any) -> list[str]:
    """用于清理技能输入并保持首次出现顺序。"""
    raw_items = items if isinstance(items, list) else [items]
    normalized: list[str] = []
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def merge_resume_skill_items(existing: Any, next_items: list[str], mode: str) -> list[str]:
    """用于按更新模式生成最终技能列表。"""
    if mode == "replace":
        return next_items
    merged = normalize_resume_skill_items(existing)
    for item in next_items:
        if item not in merged:
            merged.append(item)
    return merged


__all__ = [
    "ITEM_FIELD_WHITELIST",
    "SKILL_UPDATE_MODES",
    "add_resume_bullet",
    "add_resume_item_to_document",
    "merge_resume_skill_items",
    "normalize_resume_item_field_value",
    "normalize_resume_item_id",
    "normalize_resume_skill_items",
    "remove_resume_bullet",
    "remove_resume_item_from_document",
    "update_resume_overview",
    "update_resume_bullet",
    "update_resume_item_fields",
    "update_resume_skills",
]
