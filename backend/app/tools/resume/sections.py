"""用于集中声明 Resume Agent 可操作的简历板块术语。"""

from __future__ import annotations

from typing import Any

RESUME_SECTION_ALIASES = {
    "work": "work_experience",
    "work_experiences": "work_experience",
    "experience": "work_experience",
    "project": "projects",
    "project_experience": "projects",
    "edu": "education",
}

RESUME_MODULE_TO_CONTENT_SECTION = {
    "personal": "personal_info",
    "summary": "summary",
    "education": "education",
    "work": "work_experience",
    "work_experience": "work_experience",
    "projects": "projects",
    "open_source": "open_source",
    "skills": "skills",
}

ITEM_FIELD_SECTIONS = ("education", "work_experience", "projects", "open_source")
BULLET_SECTIONS = ("education", "work_experience", "projects", "open_source")
VISIBILITY_SECTIONS = (
    "personal",
    "summary",
    "education",
    "work",
    "work_experience",
    "projects",
    "open_source",
    "skills",
)

SECTION_DISPLAY_NAMES = {
    "personal_info": "个人信息",
    "education": "教育经历",
    "work_experience": "工作经历",
    "skills": "技能专长",
    "projects": "项目经历",
    "open_source": "开源经历",
    "summary": "个人总结",
    "job_application": "求职目标",
    "languages": "语言能力",
}


def content_section_from_module(module: Any) -> str | None:
    """用于把前端可见模块 id 转成简历内容 section key。"""

    return RESUME_MODULE_TO_CONTENT_SECTION.get(str(module))


def allowed_sections_from_visible_modules(visible_modules: list[str]) -> set[str]:
    """用于把当前可见模块列表转成工具可编辑 section 集合。"""

    return {
        section
        for module in visible_modules
        if (section := content_section_from_module(module))
    }


def resume_section_display_name(section_key: str | None) -> str | None:
    """用于把内部板块 key 转成前端更容易展示的中文名称。"""

    if not section_key:
        return None
    return SECTION_DISPLAY_NAMES.get(section_key, section_key)
