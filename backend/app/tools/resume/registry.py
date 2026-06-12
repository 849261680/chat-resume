"""用于集中声明简历工具 schema 和分发关系。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .add_bullet_tool import add_bullet
from .ask_user_tool import ask_user
from .job_post_tool import list_job_posts, read_job_post
from .memory_tool import read_memory, update_memory
from .remove_bullet_tool import remove_bullet
from .resume_item_tool import hide_section, show_section
from .update_bullet_tool import update_bullet
from .update_item_fields_tool import update_item_fields
from .update_overview_tool import update_overview
from .update_profile_tool import update_profile
from .update_skills_tool import update_skills
from .update_summary_tool import update_summary
from .upsert_job_application_tool import upsert_job_application
from .evaluate_bullet_tool import evaluate_bullet

_ITEM_FIELD_SECTIONS = ["education", "work_experience", "projects"]
_BULLET_SECTIONS = ["education", "work_experience", "projects", "open_source"]
ResumeToolResult = dict[str, Any] | Awaitable[dict[str, Any]]


@dataclass(frozen=True)
class ResumeToolDefinition:
    """用于把工具 schema、handler 和分类收敛成一个定义单元。"""

    name: str
    handler: Callable[..., ResumeToolResult]
    schema: dict[str, Any] | None = None
    category: str = "resume"


_RESUME_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": (
                "向用户发起结构化追问，不修改简历。"
                "用于缺少事实边界、职责、量化结果或经历细节时。"
                "question 必须是直接疑问句；调用后等待用户回答。"
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
                "修改技能分类名称或技能列表。"
                "category_id 必须来自当前简历；mode=replace 替换，mode=merge 追加去重。"
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
                        "description": "技能列表",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["replace", "merge"],
                        "description": "replace 替换列表，merge 合并追加",
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
            "name": "update_item_fields",
            "description": (
                "修改工作、项目、教育条目的非 bullet 字段。"
                "section 只能是 education、work_experience、projects；item_id 必须来自当前简历。"
                "不修改亮点文本；改 bullet 用 update_bullet；不允许修改 is_current。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {"type": "string", "enum": _ITEM_FIELD_SECTIONS},
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
                            "location/employment_type；projects 支持 "
                            "name/overview/role/duration/start_date/end_date/"
                            "github_url/demo_url/links。is_current 是内部派生字段，不允许直接修改。"
                        ),
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
                                "items": {"type": "object"},
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
            "name": "evaluate_bullet",
            "description": (
                "评价单条 bullet/亮点质量，只读不改。"
                "从量化、动作、结果影响、主导性和说服力维度打分。"
                "section、item_id、bullet_id 必须来自当前简历。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": _BULLET_SECTIONS,
                    },
                    "item_id": {
                        "type": "string",
                        "description": "经历/项目/教育条目的 id",
                    },
                    "bullet_id": {
                        "type": "string",
                        "description": "要评价的 bullet id",
                    },
                },
                "required": ["section", "item_id", "bullet_id"],
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
                        "enum": _BULLET_SECTIONS,
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
                        "enum": _BULLET_SECTIONS,
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
                        "enum": _BULLET_SECTIONS,
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

RESUME_TOOL_CATALOG: tuple[ResumeToolDefinition, ...] = (
    ResumeToolDefinition("ask_user", ask_user, _SCHEMA_BY_NAME.get("ask_user")),
    ResumeToolDefinition(
        "update_summary",
        update_summary,
        _SCHEMA_BY_NAME.get("update_summary"),
    ),
    ResumeToolDefinition(
        "update_profile",
        update_profile,
        _SCHEMA_BY_NAME.get("update_profile"),
    ),
    ResumeToolDefinition(
        "upsert_job_application",
        upsert_job_application,
        _SCHEMA_BY_NAME.get("upsert_job_application"),
    ),
    ResumeToolDefinition(
        "update_item_fields",
        update_item_fields,
        _SCHEMA_BY_NAME.get("update_item_fields"),
    ),
    ResumeToolDefinition(
        "update_skills",
        update_skills,
        _SCHEMA_BY_NAME.get("update_skills"),
    ),
    ResumeToolDefinition(
        "show_section",
        show_section,
        _SCHEMA_BY_NAME.get("show_section"),
    ),
    ResumeToolDefinition(
        "hide_section",
        hide_section,
        _SCHEMA_BY_NAME.get("hide_section"),
    ),
    ResumeToolDefinition(
        "update_overview",
        update_overview,
        _SCHEMA_BY_NAME.get("update_overview"),
    ),
    ResumeToolDefinition(
        "update_bullet",
        update_bullet,
        _SCHEMA_BY_NAME.get("update_bullet"),
    ),
    ResumeToolDefinition("add_bullet", add_bullet, _SCHEMA_BY_NAME.get("add_bullet")),
    ResumeToolDefinition(
        "remove_bullet",
        remove_bullet,
        _SCHEMA_BY_NAME.get("remove_bullet"),
    ),
    ResumeToolDefinition(
        "evaluate_bullet",
        evaluate_bullet,
        _SCHEMA_BY_NAME.get("evaluate_bullet"),
    ),
    ResumeToolDefinition(
        "list_job_posts",
        list_job_posts,
        _SCHEMA_BY_NAME.get("list_job_posts"),
    ),
    ResumeToolDefinition(
        "read_job_post",
        read_job_post,
        _SCHEMA_BY_NAME.get("read_job_post"),
    ),
    ResumeToolDefinition("read_memory", read_memory, _SCHEMA_BY_NAME.get("read_memory")),
    ResumeToolDefinition(
        "update_memory",
        update_memory,
        _SCHEMA_BY_NAME.get("update_memory"),
    ),
)

RESUME_TOOLS_SCHEMA: list[dict[str, Any]] = [
    definition.schema
    for definition in RESUME_TOOL_CATALOG
    if definition.schema is not None
]
_RESUME_TOOL_HANDLERS = {
    definition.name: definition.handler for definition in RESUME_TOOL_CATALOG
}


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
    "RESUME_TOOL_CATALOG",
    "RESUME_TOOLS_SCHEMA",
    "ResumeToolDefinition",
    "ResumeToolResult",
    "execute_resume_tool",
]
