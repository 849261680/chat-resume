"""用于集中声明简历工具 schema 和分发关系。"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Any, cast

from .add_resume_item_tool import add_resume_item
from .add_bullet_tool import add_bullet
from .ask_user_tool import ask_user
from .job_post_tool import list_job_posts, read_job_post
from .memory_tool import read_memory, update_memory
from .remove_bullet_tool import remove_bullet
from .remove_resume_item_tool import remove_resume_item
from .resume_item_tool import hide_section, show_section
from .sections import (
    BULLET_SECTIONS,
    ITEM_FIELD_SECTIONS,
    RESUME_SECTION_ALIASES,
    VISIBILITY_SECTIONS,
    resume_section_display_name,
)
from .update_bullet_tool import update_bullet
from .update_item_fields_tool import ITEM_FIELD_WHITELIST, update_item_fields
from .update_overview_tool import update_overview
from .update_profile_tool import update_profile
from .update_skills_tool import update_skills
from .update_summary_tool import update_summary
from .upsert_job_application_tool import upsert_job_application

logger = logging.getLogger(__name__)

_RESUME_LINK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "label": {"type": "string"},
        "url": {"type": "string"},
    },
}
_ITEM_FIELD_SCHEMA_PROPERTIES: dict[str, Any] = {
    field: {"type": "string"}
    for fields in ITEM_FIELD_WHITELIST.values()
    for field in fields
}
_ITEM_FIELD_SCHEMA_PROPERTIES["links"] = {
    "type": "array",
    "items": _RESUME_LINK_SCHEMA,
}
ResumeToolResult = dict[str, Any] | Awaitable[dict[str, Any]]
ResumeToolExecutionResult = dict[str, Any] | Awaitable[dict[str, Any]]

@dataclass(frozen=True)
class ResumeToolDefinition:
    """用于把工具 schema、handler 和分类收敛成一个定义单元。"""

    name: str
    handler: Callable[..., ResumeToolResult]
    schema: dict[str, Any] | None = None
    category: str = "resume"
    profiles: tuple[str, ...] = ("resume_edit",)
    required_args: tuple[str, ...] = ()
    display_name: str = ""
    section_enum: tuple[str, ...] = ()
    argument_aliases: Mapping[str, str] = field(default_factory=dict)
    auto_execute: bool = False
    visibility_tool: bool = False


_RESUME_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": (
                "向用户发起结构化追问，不修改简历。"
                "用于缺少事实边界、职责、量化结果或经历细节时。"
                "question 必须是直接问用户的疑问句；调用后等待用户回答。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": (
                            "需要用户回答的具体问题。必须是直接问用户的疑问句，"
                            "例如“你在 OpenClaw 中具体负责哪部分？”；"
                            "不要写成“我需要了解三个关键信息”这类陈述或任务说明。"
                        ),
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "提供给用户点击选择的候选答案，建议 2-4 个",
                    },
                    "category": {
                        "type": "string",
                        "enum": [
                            "personal_info",
                            "work_experience",
                            "projects",
                            "education",
                            "skills",
                            "job_application",
                            "other",
                        ],
                        "description": "本次追问对应的信息类别",
                    },
                    "context": {
                        "type": "string",
                        "description": "为什么需要这个信息的简短上下文",
                    },
                    "allow_custom": {
                        "type": "boolean",
                        "description": "是否允许用户自己输入文字，默认 true",
                    },
                },
                "required": ["question", "options"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hide_section",
            "description": (
                "隐藏简历板块，只改显示开关，不删除内容。"
                "section 使用模块 id；需要恢复显示时用 show_section。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": [
                            "personal",
                            "summary",
                            "education",
                            "work",
                            "projects",
                            "open_source",
                            "skills",
                        ],
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次隐藏的简短理由，供前端展示",
                    },
                },
                "required": ["section"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_section",
            "description": (
                "显示简历板块，只改显示开关，不写入内容。"
                "section 使用模块 id；空板块只显示标题。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": [
                            "personal",
                            "summary",
                            "education",
                            "work",
                            "projects",
                            "open_source",
                            "skills",
                        ],
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次显示的简短理由，供前端展示",
                    },
                },
                "required": ["section"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_skills",
            "description": (
                "新增、修改或删除技能分类。"
                "category_id 命中当前简历时更新该分类；未命中且 mode 不是 remove 时创建新分类。"
                "mode=replace 替换技能列表，mode=merge 追加去重，mode=remove 删除整个分类。"
                "只能写入简历或用户明确提供的技能。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "string",
                        "description": "技能分类条目的 id",
                    },
                    "category": {
                        "type": "string",
                        "description": "新的技能分类名称",
                    },
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "技能列表；replace/merge 必填，remove 不需要",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["replace", "merge", "remove"],
                        "description": "replace 替换列表，merge 合并追加，remove 删除整个分类",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次修改的简短理由，供前端展示",
                    },
                },
                "required": ["category_id", "skills"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_resume_item",
            "description": (
                "删除一整条教育、工作、项目或开源经历。"
                "section 只能是 education、work_experience、projects、open_source；item_id 必须来自当前简历。"
                "只在用户明确要求删除整段经历/项目/教育/开源条目时使用；删除单条 bullet 用 remove_bullet。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {"type": "string", "enum": list(ITEM_FIELD_SECTIONS)},
                    "item_id": {
                        "type": "string",
                        "description": "要删除的教育/工作/项目/开源条目的 id",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次删除的简短理由，供前端展示",
                    },
                },
                "required": ["section", "item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_resume_item",
            "description": (
                "新增教育、工作、项目或开源条目。"
                "从零创建简历或目标条目不存在时使用；新增后再用 add_bullet 追加亮点。"
                "section 只能是 education、work_experience、projects、open_source。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {"type": "string", "enum": list(ITEM_FIELD_SECTIONS)},
                    "item_id": {
                        "type": "string",
                        "description": "可选条目 id；缺省时系统自动生成",
                    },
                    "fields": {
                        "type": "object",
                        "description": (
                            "要新增的条目字段。education 支持 school/major/degree/duration/"
                            "start_date/end_date/location/gpa；work_experience 支持 "
                            "company/position/duration/start_date/end_date/"
                            "location/employment_type；projects/open_source 支持 "
                            "name/overview/role/duration/start_date/end_date/"
                            "github_url/demo_url/links。"
                        ),
                        "properties": _ITEM_FIELD_SCHEMA_PROPERTIES,
                        "additionalProperties": False,
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次新增的简短理由，供前端展示",
                    },
                },
                "required": ["section", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_item_fields",
            "description": (
                "修改工作、项目、开源、教育条目的非 bullet 字段。"
                "section 只能是 education、work_experience、projects、open_source；item_id 必须来自当前简历。"
                "目标条目不存在时先用 add_resume_item；不修改亮点文本；改 bullet 用 update_bullet；不允许修改 is_current。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {"type": "string", "enum": list(ITEM_FIELD_SECTIONS)},
                    "item_id": {
                        "type": "string",
                        "description": "工作/项目/教育条目的 id",
                    },
                    "fields": {
                        "type": "object",
                        "description": (
                            "要更新的字段。education 支持 school/major/degree/duration/"
                            "start_date/end_date/location/gpa；work_experience 支持 "
                            "company/position/duration/start_date/end_date/"
                            "location/employment_type；projects/open_source 支持 "
                            "name/overview/role/duration/start_date/end_date/"
                            "github_url/demo_url/links。is_current 是内部派生字段，不允许直接修改。"
                        ),
                        "properties": _ITEM_FIELD_SCHEMA_PROPERTIES,
                        "additionalProperties": False,
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次修改的简短理由，供前端展示",
                    },
                },
                "required": ["section", "item_id", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_profile",
            "description": (
                "修改个人信息、求职定位、headline、地点或链接。"
                "fields 只传要改的字段；修改 name/email/phone/address 时必须填写 source。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fields": {
                        "type": "object",
                        "description": "要更新的个人信息字段和值",
                        "properties": {
                            "position": {"type": "string"},
                            "headline": {"type": "string"},
                            "location": {"type": "string"},
                            "github": {"type": "string"},
                            "linkedin": {"type": "string"},
                            "website": {"type": "string"},
                            "address": {"type": "string"},
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "phone": {"type": "string"},
                            "links": {
                                "type": "array",
                                "items": _RESUME_LINK_SCHEMA,
                            },
                        },
                        "additionalProperties": False,
                    },
                    "source": {
                        "type": "string",
                        "description": "身份或联系方式字段的明确来源，例如用户输入或上传简历原文",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次修改的简短理由，供前端展示",
                    },
                },
                "required": ["fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upsert_job_application",
            "description": (
                "设置或更新求职目标上下文：目标公司、目标岗位、JD 原文。"
                "fields 只传本次要改的字段；不修改简历正文。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fields": {
                        "type": "object",
                        "description": "只包含本次要修改的求职目标字段和值",
                        "properties": {
                            "target_company": {
                                "type": "string",
                                "description": "目标公司或面试公司",
                            },
                            "target_title": {
                                "type": "string",
                                "description": "目标岗位或面试岗位",
                            },
                            "jd_text": {
                                "type": "string",
                                "description": "目标岗位 JD 原文",
                            },
                        },
                        "additionalProperties": False,
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次修改的简短理由，供前端展示",
                    },
                },
                "required": ["fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_summary",
            "description": (
                "修改简历个人总结/自我评价文本。"
                "只能基于当前简历、候选人档案或用户明确提供的事实。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "新的个人总结文本",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次修改的简短理由，供前端展示",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_overview",
            "description": (
                "修改 projects 中某个项目的 overview 简介。"
                "section 必须是 projects；item_id 必须来自当前简历。"
                "只改项目简介，不改 bullet。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": ["projects"],
                    },
                    "item_id": {
                        "type": "string",
                        "description": "项目条目的 id",
                    },
                    "overview": {
                        "type": "string",
                        "description": "新的项目简介文本",
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "本次修改的简短理由，供前端展示，如“突出量化结果”"
                        ),
                    },
                },
                "required": ["section", "item_id", "overview"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_job_posts",
            "description": "列出当前用户保存过的 JD 摘要列表，只读，不修改简历。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "可选关键词，可按公司、岗位或 JD 内容筛选",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量，默认 20，最大 50",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_job_post",
            "description": "按 job_post_id 读取一条完整 JD 原文，只读，不修改简历。",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_post_id": {
                        "type": "integer",
                        "description": "要读取的 JD 记录 id",
                    },
                },
                "required": ["job_post_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_memory",
            "description": (
                "读取用户长期记忆，只读。"
                "包含偏好、事实约束、目标策略和已拒绝写法。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["user", "resume"],
                        "description": "读取用户级或当前简历级记忆",
                    },
                    "query": {
                        "type": "string",
                        "description": "可选关键词，用于筛选相关记忆",
                    },
                },
                "required": ["scope"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_memory",
            "description": (
                "记录用户明确表达的长期偏好、事实约束或目标策略。"
                "只能记录用户明说的内容，不推断、不编造。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["append", "replace", "disable"],
                        "description": "追加、替换或停用一条记忆",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["user", "resume"],
                        "description": "更新用户级或当前简历级记忆",
                    },
                    "memory_id": {
                        "type": "string",
                        "description": "replace/disable 时要操作的记忆 id",
                    },
                    "kind": {
                        "type": "string",
                        "enum": [
                            "preference",
                            "fact_constraint",
                            "target_strategy",
                        ],
                        "description": "记忆类型",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的记忆内容",
                    },
                    "reason": {
                        "type": "string",
                        "description": "为什么这条内容值得长期记住",
                    },
                },
                "required": ["operation", "scope"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_bullet",
            "description": (
                "重写已有 bullet/亮点文本。"
                "section 只能是 education、work_experience、projects、open_source；"
                "item_id 和 bullet_id 必须来自当前简历；新增 bullet 用 add_bullet。"
                "text 必须完整替换原文、有实质差异，不要传入原文。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": list(BULLET_SECTIONS),
                    },
                    "item_id": {
                        "type": "string",
                        "description": "经历/项目/教育条目的 id",
                    },
                    "bullet_id": {
                        "type": "string",
                        "description": "要修改的 bullet id",
                    },
                    "text": {
                        "type": "string",
                        "description": (
                            "新的完整 bullet 文本。必须与原文有实质差异；"
                            "不得传入原文，也不得只调整空格、标点或语序。"
                            "只能写当前简历、用户补充或背景档案中可追溯的事实。"
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次修改的简短理由，供前端展示；reason 不能替代 text 修改",
                    },
                },
                "required": ["section", "item_id", "bullet_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_bullet",
            "description": (
                "向已有工作、项目、教育或开源条目追加一条新 bullet。"
                "section 和 item_id 必须来自当前简历；改已有 bullet 用 update_bullet。"
                "新增内容必须基于用户明确提供的事实。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": list(BULLET_SECTIONS),
                    },
                    "item_id": {
                        "type": "string",
                        "description": "经历/项目/教育条目的 id",
                    },
                    "text": {
                        "type": "string",
                        "description": "新增的 bullet 文本",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次新增的简短理由，供前端展示",
                    },
                },
                "required": ["section", "item_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_bullet",
            "description": (
                "删除已有 bullet/亮点。"
                "section、item_id、bullet_id 必须来自当前简历；不要主动删除未被要求删除的内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": list(BULLET_SECTIONS),
                    },
                    "item_id": {
                        "type": "string",
                        "description": "经历/项目/教育条目的 id",
                    },
                    "bullet_id": {
                        "type": "string",
                        "description": "要删除的 bullet id",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次删除的简短理由，供前端展示",
                    },
                },
                "required": ["section", "item_id", "bullet_id"],
            },
        },
    },
]


def _schema_tool_name(schema: dict[str, Any]) -> str:
    """用于从 OpenAI function schema 中读取工具名。"""
    function = schema.get("function")
    if not isinstance(function, dict):
        return ""
    name = function.get("name")
    return name if isinstance(name, str) else ""


_SCHEMA_BY_NAME = {
    name: schema
    for schema in _RESUME_TOOL_SCHEMAS
    if (name := _schema_tool_name(schema))
}


def _define_tool(
    name: str,
    handler: Callable[..., ResumeToolResult],
    *,
    display_name: str,
    profiles: tuple[str, ...] = ("resume_edit",),
    required_args: tuple[str, ...] = (),
    section_enum: tuple[str, ...] = (),
    argument_aliases: Mapping[str, str] | None = None,
    auto_execute: bool = False,
    visibility_tool: bool = False,
) -> ResumeToolDefinition:
    """用于用一个目录项声明工具 schema、handler 和运行时元数据。"""
    return ResumeToolDefinition(
        name=name,
        handler=handler,
        schema=_SCHEMA_BY_NAME.get(name),
        display_name=display_name,
        profiles=profiles,
        required_args=required_args,
        section_enum=section_enum,
        argument_aliases=argument_aliases or {},
        auto_execute=auto_execute,
        visibility_tool=visibility_tool,
    )


_READ_ONLY_PROFILES = ("resume_edit", "read_only")
RESUME_TOOL_CATALOG: tuple[ResumeToolDefinition, ...] = (
    _define_tool(
        "ask_user",
        ask_user,
        display_name="询问信息",
        profiles=_READ_ONLY_PROFILES,
        required_args=("question", "options"),
        auto_execute=True,
    ),
    _define_tool(
        "update_summary",
        update_summary,
        display_name="优化总结",
        required_args=("text",),
    ),
    _define_tool(
        "update_profile",
        update_profile,
        display_name="优化个人信息",
        required_args=("fields",),
    ),
    _define_tool(
        "upsert_job_application",
        upsert_job_application,
        display_name="更新求职目标",
        required_args=("fields",),
    ),
    _define_tool(
        "add_resume_item",
        add_resume_item,
        display_name="新增经历条目",
        required_args=("section", "fields"),
        section_enum=ITEM_FIELD_SECTIONS,
    ),
    _define_tool(
        "remove_resume_item",
        remove_resume_item,
        display_name="删除经历条目",
        required_args=("section", "item_id"),
        section_enum=ITEM_FIELD_SECTIONS,
    ),
    _define_tool(
        "update_item_fields",
        update_item_fields,
        display_name="优化条目字段",
        required_args=("section", "item_id", "fields"),
        section_enum=ITEM_FIELD_SECTIONS,
    ),
    _define_tool(
        "update_skills",
        update_skills,
        display_name="优化技能",
        required_args=("category_id",),
        argument_aliases={"skills": "items"},
    ),
    _define_tool(
        "show_section",
        show_section,
        display_name="显示板块",
        required_args=("section",),
        section_enum=VISIBILITY_SECTIONS,
        visibility_tool=True,
    ),
    _define_tool(
        "hide_section",
        hide_section,
        display_name="隐藏板块",
        required_args=("section",),
        section_enum=VISIBILITY_SECTIONS,
        visibility_tool=True,
    ),
    _define_tool(
        "update_overview",
        update_overview,
        display_name="优化简介",
        required_args=("section", "item_id", "overview"),
        section_enum=("projects",),
        argument_aliases={"text": "overview", "description": "overview"},
    ),
    _define_tool(
        "update_bullet",
        update_bullet,
        display_name="优化要点",
        required_args=("section", "item_id", "bullet_id", "text"),
        section_enum=BULLET_SECTIONS,
        argument_aliases={"highlight_id": "bullet_id"},
    ),
    _define_tool(
        "add_bullet",
        add_bullet,
        display_name="新增要点",
        required_args=("section", "item_id", "text"),
        section_enum=BULLET_SECTIONS,
    ),
    _define_tool(
        "remove_bullet",
        remove_bullet,
        display_name="删除要点",
        required_args=("section", "item_id", "bullet_id"),
        section_enum=BULLET_SECTIONS,
        argument_aliases={"highlight_id": "bullet_id"},
    ),
    _define_tool(
        "list_job_posts",
        list_job_posts,
        display_name="读取JD列表",
        profiles=_READ_ONLY_PROFILES,
        auto_execute=True,
    ),
    _define_tool(
        "read_job_post",
        read_job_post,
        display_name="读取JD",
        profiles=_READ_ONLY_PROFILES,
        required_args=("job_post_id",),
        auto_execute=True,
    ),
    _define_tool(
        "read_memory",
        read_memory,
        display_name="读取记忆",
        profiles=_READ_ONLY_PROFILES,
        required_args=("scope",),
        auto_execute=True,
    ),
    _define_tool(
        "update_memory",
        update_memory,
        display_name="更新记忆",
        required_args=("operation", "scope"),
        auto_execute=True,
    ),
)

RESUME_AUTO_EXECUTE_TOOL_NAMES: set[str] = {
    definition.name for definition in RESUME_TOOL_CATALOG if definition.auto_execute
}

RESUME_TOOL_PROFILES: dict[str, set[str]] = {}
for _definition in RESUME_TOOL_CATALOG:
    for _profile in _definition.profiles:
        RESUME_TOOL_PROFILES.setdefault(_profile, set()).add(_definition.name)

RESUME_TOOL_REQUIRED_ARGS: dict[str, set[str]] = {
    definition.name: set(definition.required_args)
    for definition in RESUME_TOOL_CATALOG
}

RESUME_TOOL_SECTION_ENUMS: dict[str, set[str]] = {
    definition.name: set(definition.section_enum)
    for definition in RESUME_TOOL_CATALOG
    if definition.section_enum
}

RESUME_TOOL_DISPLAY_NAMES: dict[str, str] = {
    definition.name: definition.display_name
    for definition in RESUME_TOOL_CATALOG
    if definition.display_name
}

RESUME_TOOL_ARGUMENT_ALIASES: dict[str, dict[str, str]] = {
    definition.name: dict(definition.argument_aliases)
    for definition in RESUME_TOOL_CATALOG
    if definition.argument_aliases
}

RESUME_VISIBILITY_TOOL_NAMES: set[str] = {
    definition.name for definition in RESUME_TOOL_CATALOG if definition.visibility_tool
}

RESUME_TOOLS_SCHEMA: list[dict[str, Any]] = [
    definition.schema
    for definition in RESUME_TOOL_CATALOG
    if definition.schema is not None
]
_RESUME_TOOL_HANDLERS = {
    definition.name: definition.handler for definition in RESUME_TOOL_CATALOG
}
_RESUME_TOOL_DEFINITIONS = {
    definition.name: definition for definition in RESUME_TOOL_CATALOG
}


def execute_resume_tool_call(
    *,
    tool_name: str,
    raw_arguments: Any,
    context: dict[str, Any],
) -> dict[str, Any]:
    """用于从模型原始参数执行一次完整的简历工具调用。"""
    tool_input, error = parse_resume_tool_input(tool_name, raw_arguments)
    if error is not None:
        return error
    return execute_prepared_resume_tool_call(
        tool_name=tool_name,
        tool_input=tool_input,
        context=context,
    )


def execute_prepared_resume_tool_call(
    *,
    tool_name: str,
    tool_input: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """用于执行已解析的简历工具参数并返回统一 runtime 结果。"""
    normalized_input = normalize_resume_tool_input(tool_name, tool_input)
    error = validate_resume_tool_input(tool_name, normalized_input, context)
    if error is not None:
        return error
    return cast(
        dict[str, Any],
        dispatch_resume_tool_call(
            tool_name=tool_name,
            tool_input=normalized_input,
            context=context,
        ),
    )


def parse_resume_tool_input(
    tool_name: str,
    raw_arguments: Any,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """用于解析模型工具参数并把错误包装成统一工具结果。"""
    try:
        parsed = parse_resume_tool_arguments(raw_arguments)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return {}, resume_tool_error_result(
            tool_name,
            "invalid_arguments_json",
            f"工具参数不是合法 JSON，无法执行 {tool_name}: {exc}",
            recoverable=True,
            expected_arguments=expected_resume_tool_arguments(tool_name),
        )
    if isinstance(parsed, dict):
        return parsed, None
    return {}, resume_tool_error_result(
        tool_name,
        "invalid_arguments_type",
        f"工具参数必须是对象，实际收到 {type(parsed).__name__}",
        recoverable=True,
        expected_arguments=expected_resume_tool_arguments(tool_name),
    )


def parse_resume_tool_arguments(raw_arguments: Any) -> Any:
    """用于把模型返回的工具参数解析成 Python 值。"""
    if isinstance(raw_arguments, dict):
        return dict(raw_arguments)
    if not isinstance(raw_arguments, str):
        raise ValueError(
            f"无法解析工具参数类型: {type(raw_arguments)}, value={raw_arguments!r}"
        )
    try:
        return json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        logger.warning(
            "tool_args.json_parse_failed",
            extra={"error_type": type(exc).__name__, "raw_chars": len(raw_arguments)},
        )
        fragment = parse_json_object_fragment(raw_arguments)
        if fragment is not None:
            return fragment
        raise


def parse_json_object_fragment(value: str) -> dict[str, Any] | None:
    """用于兼容模型把 JSON 对象包在解释文本中的情况。"""
    match = re.search(r"\{.*\}", value, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def normalize_resume_tool_input(
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    """用于修正常见工具参数别名，不推断缺失事实。"""
    normalized = dict(tool_input)
    section = normalized.get("section")
    if isinstance(section, str):
        normalized["section"] = RESUME_SECTION_ALIASES.get(section, section)
    for source, target in RESUME_TOOL_ARGUMENT_ALIASES.get(tool_name, {}).items():
        normalized = apply_argument_alias(normalized, source=source, target=target)
    if tool_name == "update_overview" and not normalized.get("section"):
        normalized["section"] = "projects"
    return normalized


def apply_argument_alias(
    tool_input: dict[str, Any],
    *,
    source: str,
    target: str,
) -> dict[str, Any]:
    """用于把单个模型参数别名转换成规范参数名。"""
    normalized = dict(tool_input)
    if target not in normalized and source in normalized:
        normalized[target] = normalized[source]
    if source in normalized and source != target:
        normalized.pop(source)
    return normalized


def validate_resume_tool_input(
    tool_name: str,
    tool_input: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any] | None:
    """用于校验工具是否存在、必填参数和板块权限。"""
    definition = _RESUME_TOOL_DEFINITIONS.get(tool_name)
    if definition is None:
        return resume_tool_error_result(
            tool_name,
            "unknown_tool",
            f"Unknown tool: {tool_name}",
            recoverable=False,
        )
    missing = missing_resume_tool_arguments(definition, tool_input)
    if missing:
        return resume_tool_error_result(
            tool_name,
            "missing_required_argument",
            f"{tool_name} 缺少必填参数: {', '.join(missing)}",
            recoverable=True,
            expected_arguments=sorted(definition.required_args),
            updated_section=section_from_tool_input(tool_input),
        )
    return validate_resume_tool_section(definition, tool_input, context)


def missing_resume_tool_arguments(
    definition: ResumeToolDefinition,
    tool_input: dict[str, Any],
) -> list[str]:
    """用于返回当前工具缺失的必填参数。"""
    return sorted(key for key in definition.required_args if not tool_input.get(key))


def validate_resume_tool_section(
    definition: ResumeToolDefinition,
    tool_input: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any] | None:
    """用于校验目标板块是否可见且受当前工具支持。"""
    target_section = section_from_tool_input(tool_input)
    allowed_sections = context.get("allowed_sections")
    if section_is_hidden(definition, target_section, allowed_sections):
        return resume_tool_error_result(
            definition.name,
            "hidden_section",
            f"板块 {target_section} 当前已隐藏，禁止修改",
            recoverable=False,
            updated_section=target_section,
        )
    if section_is_unsupported(definition, target_section):
        return resume_tool_error_result(
            definition.name,
            "invalid_section",
            f"{definition.name} 不支持修改板块 {target_section}",
            recoverable=True,
            expected_arguments=sorted(definition.required_args),
            updated_section=target_section,
        )
    return None


def section_from_tool_input(tool_input: dict[str, Any]) -> str | None:
    """用于从工具参数中读取目标板块。"""
    section = tool_input.get("section")
    return section if isinstance(section, str) else None


def section_is_hidden(
    definition: ResumeToolDefinition,
    target_section: str | None,
    allowed_sections: Any,
) -> bool:
    """用于判断工具是否正在修改当前不可见板块。"""
    if allowed_sections is None or not target_section:
        return False
    if definition.visibility_tool:
        return False
    return target_section not in allowed_sections


def section_is_unsupported(
    definition: ResumeToolDefinition,
    target_section: str | None,
) -> bool:
    """用于判断工具参数里的板块是否不在工具定义范围内。"""
    if not definition.section_enum:
        return False
    return target_section not in definition.section_enum


def dispatch_resume_tool_call(
    *,
    tool_name: str,
    tool_input: dict[str, Any],
    context: dict[str, Any],
) -> ResumeToolExecutionResult:
    """用于注入上下文并调用工具 handler。"""
    target_section = section_from_tool_input(tool_input)
    try:
        result = execute_resume_tool(
            tool_name=tool_name,
            resume_content=context["resume_content"],
            **contextual_resume_tool_input(tool_name, tool_input, context),
        )
        if isawaitable(result):
            return wrap_async_resume_tool_result(
                result,
                tool_name=tool_name,
                updated_section=target_section,
            )
    except TypeError as exc:
        return resume_tool_error_result(
            tool_name,
            "tool_argument_type_error",
            f"{tool_name} 参数不匹配: {exc}",
            recoverable=True,
            expected_arguments=expected_resume_tool_arguments(tool_name),
            updated_section=target_section,
        )
    except Exception as exc:
        return resume_tool_error_result(
            tool_name,
            "tool_execution_error",
            f"{tool_name} 执行失败: {exc}",
            recoverable=False,
            updated_section=target_section,
        )
    return wrap_resume_tool_success_result(
        tool_name=tool_name,
        result=result,
        updated_section=target_section,
    )


def contextual_resume_tool_input(
    tool_name: str,
    tool_input: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """用于给只读或记忆工具补齐运行上下文字段。"""
    enriched = dict(tool_input)
    if tool_name == "list_job_posts":
        enriched.update({
            "user_id": context.get("user_id"),
            "list_job_posts_reader": context.get("list_job_posts_reader"),
        })
    if tool_name == "read_job_post":
        enriched.update({
            "user_id": context.get("user_id"),
            "read_job_post_reader": context.get("read_job_post_reader"),
        })
    if tool_name in {"read_memory", "update_memory"}:
        enriched.update({
            "user_id": context.get("user_id"),
            "resume_id": context.get("resume_id"),
            "memory_dir": context.get("memory_dir"),
        })
    if tool_name == "update_memory" and context.get("dry_run") is True:
        enriched["dry_run"] = True
    return enriched


async def wrap_async_resume_tool_result(
    pending_result: Awaitable[dict[str, Any]],
    *,
    tool_name: str,
    updated_section: str | None,
) -> dict[str, Any]:
    """用于等待异步工具并包装成统一工具结果结构。"""
    try:
        result = await pending_result
    except TypeError as exc:
        return resume_tool_error_result(
            tool_name,
            "tool_argument_type_error",
            f"{tool_name} 参数不匹配: {exc}",
            recoverable=True,
            expected_arguments=expected_resume_tool_arguments(tool_name),
            updated_section=updated_section,
        )
    except Exception as exc:
        return resume_tool_error_result(
            tool_name,
            "tool_execution_error",
            f"{tool_name} 执行失败: {exc}",
            recoverable=False,
            updated_section=updated_section,
        )
    return wrap_resume_tool_success_result(
        tool_name=tool_name,
        result=result,
        updated_section=updated_section,
    )


def wrap_resume_tool_success_result(
    *,
    tool_name: str,
    result: dict[str, Any],
    updated_section: str | None,
) -> dict[str, Any]:
    """用于把工具成功返回包装成 runtime 统一结构。"""
    return {
        "tool_name": RESUME_TOOL_DISPLAY_NAMES.get(tool_name, tool_name),
        "result": result,
        "display_message": (
            result.get("diff_summary") or result.get("message")
            if isinstance(result, dict)
            else None
        ),
        "qr_image": result.get("image_base64") if isinstance(result, dict) else None,
        "updated_section_name": resume_section_display_name(
            result.get("updated_section") if isinstance(result, dict) else updated_section
        ),
    }


def resume_tool_error_result(
    tool_name: str,
    error_type: str,
    message: str,
    *,
    recoverable: bool,
    expected_arguments: list[str] | None = None,
    updated_section: str | None = None,
) -> dict[str, Any]:
    """用于把工具异常包装成统一失败结果结构。"""
    result: dict[str, Any] = {
        "success": False,
        "error": {
            "type": error_type,
            "message": message,
            "recoverable": recoverable,
        },
        "message": message,
    }
    if expected_arguments is not None:
        result["expected_arguments"] = expected_arguments
    if updated_section is not None:
        result["updated_section"] = updated_section
    return {
        "tool_name": RESUME_TOOL_DISPLAY_NAMES.get(tool_name, tool_name),
        "result": result,
        "display_message": message,
        "qr_image": None,
        "updated_section_name": resume_section_display_name(updated_section),
    }


def expected_resume_tool_arguments(tool_name: str) -> list[str]:
    """用于返回指定工具的必填参数名称。"""
    definition = _RESUME_TOOL_DEFINITIONS.get(tool_name)
    if definition is None:
        return []
    return sorted(definition.required_args)


def execute_resume_tool(
    tool_name: str,
    *,
    resume_content: dict[str, Any],
    **kwargs: Any,
) -> ResumeToolResult:
    """用于按工具名分发到对应的简历工具实现。"""
    handler = _RESUME_TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_name}"}
    return handler(resume_content, **kwargs)


__all__ = [
    "RESUME_AUTO_EXECUTE_TOOL_NAMES",
    "RESUME_SECTION_ALIASES",
    "RESUME_TOOL_CATALOG",
    "RESUME_TOOL_ARGUMENT_ALIASES",
    "RESUME_TOOL_DISPLAY_NAMES",
    "RESUME_TOOL_PROFILES",
    "RESUME_TOOL_REQUIRED_ARGS",
    "RESUME_TOOL_SECTION_ENUMS",
    "RESUME_VISIBILITY_TOOL_NAMES",
    "RESUME_TOOLS_SCHEMA",
    "ResumeToolDefinition",
    "ResumeToolExecutionResult",
    "ResumeToolResult",
    "execute_resume_tool",
    "execute_prepared_resume_tool_call",
    "execute_resume_tool_call",
    "resume_tool_error_result",
]
