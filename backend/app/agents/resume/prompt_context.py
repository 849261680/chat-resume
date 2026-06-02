"""用于把简历内容整理成提示词模板可消费的上下文。"""

from __future__ import annotations

import copy
import json
from typing import Any

from app.schemas.resume import dump_resume_content_for_frontend
from app.agents.resume.session import maybe_compact_resume_context


def strip_redundant_fields(resume_content: dict[str, Any]) -> dict[str, Any]:
    """用于移除当前提示词阶段不需要的冗余字段。"""
    content = dump_resume_content_for_frontend(copy.deepcopy(resume_content))
    content.pop("summary", None)
    for section in ("work_experience", "projects"):
        items = content.get(section)
        if isinstance(items, list):
            for item in items:
                item.pop("achievements", None)
                item.pop("technologies", None)
    return content


# 模块 id → 给用户看的中文板块名
_MODULE_LABELS = {
    "personal": "个人信息",
    "summary": "个人简介",
    "education": "教育经历",
    "work": "工作经历",
    "projects": "项目经历",
    "skills": "技能",
}

# 模块 id → 简历内容里对应的列表字段名
_MODULE_LIST_FIELDS = {
    "education": "education",
    "work": "work_experience",
    "projects": "projects",
    "skills": "skills",
}


def _module_has_content(resume_content: dict[str, Any], module: str) -> bool:
    """用于按前端规则判断某板块是否有可渲染内容。"""
    if module == "personal":
        return bool(resume_content.get("personal_info"))
    if module == "summary":
        summary = resume_content.get("summary")
        text = summary.get("text") if isinstance(summary, dict) else None
        return bool(text and str(text).strip())
    items = resume_content.get(_MODULE_LIST_FIELDS.get(module, module))
    return isinstance(items, list) and len(items) > 0


def _visibility_text(toggle_on: bool, has_content: bool) -> str:
    """用于把"显示开关"和"内容是否非空"两道门翻译成显隐结论。"""
    if toggle_on and has_content:
        return "显示"
    if not toggle_on and not has_content:
        return "隐藏（开关关闭且无内容）"
    if not toggle_on:
        return "隐藏（开关关闭）"
    return "隐藏（无内容）"


def build_module_visibility(
    resume_content: dict[str, Any],
    visible_modules: list[str] | None,
) -> str:
    """用于生成各板块在预览中的真实显隐说明；缺少开关信息时返回空串。"""
    if not isinstance(resume_content, dict) or not visible_modules:
        return ""
    toggles = set(visible_modules)
    lines = [
        f"- {label}({module}): "
        f"{_visibility_text(module in toggles, _module_has_content(resume_content, module))}"
        for module, label in _MODULE_LABELS.items()
    ]
    return "\n".join(lines)


def build_resume_prompt_context(context: dict[str, Any]) -> dict[str, Any]:
    """用于构造简历 Agent 渲染系统提示词所需的变量。"""
    resume_content = context["resume_content"]
    job_application = (
        resume_content.get("job_application", {})
        if isinstance(resume_content, dict)
        else {}
    )
    prompt_resume = maybe_compact_resume_context(
        resume_content=strip_redundant_fields(resume_content),
        confirmed_diff_items=context.get("confirmed_diff_items"),
        conversation_history=context.get("conversation_history"),
    )
    return {
        "target_title": str(job_application.get("target_title", "") or ""),
        "target_company": str(job_application.get("target_company", "") or ""),
        "jd_text": str(job_application.get("jd_text", "") or ""),
        "resume_json": json.dumps(
            prompt_resume,
            ensure_ascii=False,
            indent=2,
        ),
        "module_visibility": build_module_visibility(
            resume_content if isinstance(resume_content, dict) else {},
            context.get("visible_modules"),
        ),
    }


__all__ = [
    "build_resume_prompt_context",
    "strip_redundant_fields",
    "build_module_visibility",
]
