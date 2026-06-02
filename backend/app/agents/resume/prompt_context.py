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
    content.pop("_visible_modules", None)
    for section in ("work_experience", "projects"):
        items = content.get(section)
        if isinstance(items, list):
            for item in items:
                item.pop("achievements", None)
                item.pop("technologies", None)
    return content


# 模块 id → 给用户看的中文板块名（与 resume_item_tool 的模块集合一致）
_MODULE_LABELS = {
    "personal": "个人信息",
    "summary": "个人简介",
    "education": "教育经历",
    "work": "工作经历",
    "projects": "项目经历",
    "open_source": "开源贡献",
    "skills": "技能",
}


def build_module_visibility(
    resume_content: dict[str, Any],
    visible_modules: list[str] | None,
) -> str:
    """用于生成各板块的显示开关状态；缺少开关信息时返回空串。"""
    if not isinstance(resume_content, dict) or not visible_modules:
        return ""
    toggles = set(visible_modules)
    lines = [
        f"- {label}({module}): {'显示' if module in toggles else '隐藏'}"
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
    # 优先用内容里被 show/hide 改写过的最新可见模块，否则退回请求传入的基线
    live_visible = (
        resume_content.get("_visible_modules")
        if isinstance(resume_content, dict)
        else None
    )
    visible_modules = live_visible if isinstance(live_visible, list) else context.get("visible_modules")
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
            visible_modules,
        ),
    }


__all__ = [
    "build_resume_prompt_context",
    "strip_redundant_fields",
    "build_module_visibility",
]
