"""用于控制简历板块的显示和隐藏，不修改板块内部内容。"""

from __future__ import annotations

from typing import Any

from .shared import build_diff_payload, normalize_reason, summarize_dict

HIDDEN_SECTIONS_KEY = "_hidden_sections"

SECTION_KEYS = {
    "education",
    "work_experience",
    "projects",
    "skills",
    "languages",
    "custom_sections",
}

_SECTION_LABELS = {
    "education": "教育经历",
    "work_experience": "工作经历",
    "projects": "项目经历",
    "skills": "技能专长",
    "languages": "语言能力",
    "custom_sections": "自定义板块",
}


def _get_hidden(resume_content: dict[str, Any]) -> dict[str, Any]:
    """用于获取隐藏板块存储区。"""
    return resume_content.setdefault(HIDDEN_SECTIONS_KEY, {})


def _section_label(section: str) -> str:
    """用于把板块 key 转成中文标签。"""
    return _SECTION_LABELS.get(section, summarize_dict({"name": section}))


def show_section(
    resume_content: dict[str, Any],
    section: str,
    reason: Any = None,
) -> dict[str, Any]:
    """用于将一个隐藏板块重新显示到简历中，不修改板块内容。"""
    if section not in SECTION_KEYS:
        return {"success": False, "message": f"{section} 不是有效的简历板块"}

    if section in resume_content and not isinstance(resume_content[section], str):
        return {"success": False, "message": f"{_section_label(section)} 已在简历中显示"}

    hidden = _get_hidden(resume_content)
    if section in hidden:
        resume_content[section] = hidden.pop(section)
        source_text = "已恢复隐藏内容"
    else:
        resume_content[section] = []
        source_text = "新建空板块"

    if not hidden:
        resume_content.pop(HIDDEN_SECTIONS_KEY, None)

    diff_payload = build_diff_payload(
        title=f"显示板块「{_section_label(section)}」",
        before="（隐藏）",
        after="（显示）",
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已将{_section_label(section)}显示到简历中（{source_text}）",
        "updated_section": section,
        **diff_payload,
    }


def hide_section(
    resume_content: dict[str, Any],
    section: str,
    reason: Any = None,
) -> dict[str, Any]:
    """用于将一个简历板块隐藏，内容保留以便后续恢复。"""
    if section not in SECTION_KEYS:
        return {"success": False, "message": f"{section} 不是有效的简历板块"}

    if section not in resume_content:
        return {"success": False, "message": f"{_section_label(section)} 不在简历中"}

    content = resume_content.pop(section)
    hidden = _get_hidden(resume_content)
    hidden[section] = content

    diff_payload = build_diff_payload(
        title=f"隐藏板块「{_section_label(section)}」",
        before="（显示）",
        after="（隐藏）",
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已将{_section_label(section)}从简历中隐藏，内容已保留",
        "updated_section": section,
        **diff_payload,
    }


__all__ = [
    "HIDDEN_SECTIONS_KEY",
    "SECTION_KEYS",
    "show_section",
    "hide_section",
]
