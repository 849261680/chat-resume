"""用于控制简历板块的显示和隐藏，统一以 visibleModules 开关为唯一真相，不修改板块内容。"""

from __future__ import annotations

from typing import Any

from .shared import build_diff_payload, normalize_reason

# Agent 显隐操作的过渡字段：模块 id 列表，回传后由流式服务同步到 layout_config.visibleModules
VISIBLE_MODULES_KEY = "_visible_modules"

# 受支持的模块 id（与前端 resumeLayoutConfig.ts 的 DEFAULT_MODULE_ORDER 同构）
MODULE_IDS = [
    "personal",
    "summary",
    "education",
    "work",
    "projects",
    "open_source",
    "skills",
]

_MODULE_LABELS = {
    "personal": "个人信息",
    "summary": "个人简介",
    "education": "教育经历",
    "work": "工作经历",
    "projects": "项目经历",
    "open_source": "开源经验",
    "skills": "技能专长",
}

# 把 content key 或常见别名归一化成模块 id
_MODULE_ALIASES = {
    "personal_info": "personal",
    "work_experience": "work",
    "experience": "work",
    "project": "projects",
    "edu": "education",
    "opensource": "open_source",
    "languages": "skills",
}


def _normalize_module(section: str) -> str:
    """用于把 content key 或别名归一化成模块 id。"""
    key = str(section).strip()
    return _MODULE_ALIASES.get(key, key)


def _current_visible(resume_content: dict[str, Any]) -> list[str]:
    """用于读取当前可见模块列表；未注入基线时按全部可见兜底。"""
    raw = resume_content.get(VISIBLE_MODULES_KEY)
    if isinstance(raw, list):
        return [str(module) for module in raw]
    return list(MODULE_IDS)


def show_section(
    resume_content: dict[str, Any],
    section: str,
    reason: Any = None,
) -> dict[str, Any]:
    """用于显示一个简历板块（打开 visibleModules 开关），不修改板块内容。"""
    module = _normalize_module(section)
    if module not in _MODULE_LABELS:
        return {"success": False, "message": f"{section} 不是有效的简历板块"}

    visible = _current_visible(resume_content)
    label = _MODULE_LABELS[module]
    if module in visible:
        return {"success": False, "message": f"{label}已在简历中显示"}

    visible.append(module)
    resume_content[VISIBLE_MODULES_KEY] = visible
    diff_payload = build_diff_payload(
        title=f"显示板块「{label}」",
        before="（隐藏）",
        after="（显示）",
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已显示{label}板块",
        "updated_section": module,
        **diff_payload,
    }


def hide_section(
    resume_content: dict[str, Any],
    section: str,
    reason: Any = None,
) -> dict[str, Any]:
    """用于隐藏一个简历板块（关闭 visibleModules 开关），内容保留以便后续恢复。"""
    module = _normalize_module(section)
    if module not in _MODULE_LABELS:
        return {"success": False, "message": f"{section} 不是有效的简历板块"}

    visible = _current_visible(resume_content)
    label = _MODULE_LABELS[module]
    if module not in visible:
        return {"success": False, "message": f"{label}当前未显示"}

    visible.remove(module)
    resume_content[VISIBLE_MODULES_KEY] = visible
    diff_payload = build_diff_payload(
        title=f"隐藏板块「{label}」",
        before="（显示）",
        after="（隐藏）",
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已隐藏{label}板块，内容已保留",
        "updated_section": module,
        **diff_payload,
    }


__all__ = [
    "VISIBLE_MODULES_KEY",
    "MODULE_IDS",
    "show_section",
    "hide_section",
]
