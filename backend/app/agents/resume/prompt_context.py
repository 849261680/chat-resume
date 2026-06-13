"""用于把简历内容整理成提示词模板可消费的上下文。"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from typing import Any

from app.schemas.resume import dump_resume_content_for_agent


def strip_redundant_fields(resume_content: dict[str, Any]) -> dict[str, Any]:
    """用于移除提示词不应读取的传输态字段。"""
    content = dump_resume_content_for_agent(copy.deepcopy(resume_content))
    content.pop("_visible_modules", None)
    return content


# 模块 id → 给用户看的中文板块名（与 resume_item_tool 的模块集合一致）
_MODULE_LABELS = {
    "personal": "个人信息",
    "summary": "个人简介",
    "education": "教育经历",
    "work": "工作经历",
    "projects": "项目经历",
    "open_source": "开源经验",
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
    prompt_resume = strip_redundant_fields(resume_content)
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
        "candidate_profile": str(context.get("candidate_profile", "") or ""),
        "current_time": build_current_time_context(),
    }


def build_current_time_context(now: datetime | None = None) -> str:
    """用于生成注入给 Agent 的当前服务端时间说明。"""
    if now is None:
        current = datetime.now().astimezone()
    else:
        current = now if now.tzinfo else now.astimezone()
    timezone_name = current.tzname() or "local"
    return (
        f"- 当前日期：{current.date().isoformat()}\n"
        f"- 当前时间：{current.isoformat(timespec='seconds')}\n"
        f"- 当前时区：{timezone_name}"
    )


__all__ = [
    "build_resume_prompt_context",
    "build_current_time_context",
    "build_module_visibility",
    "strip_redundant_fields",
]
