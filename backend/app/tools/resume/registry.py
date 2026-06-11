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
from .score_resume_tool import score_resume_tool
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
                "触发条件：优化前缺少必要事实，例如工作经历、个人信息、项目经历、量化结果、职责边界。"
                "必须提供一个直接问用户的疑问句和几个可选答案；前端会额外提供“自己输入文字”。"
                "question 不要写成任务说明或陈述句，例如不要写“我需要了解三个关键信息”。"
                "调用后当前 ReAct 轮会停止，等待用户回答。"
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
                "隐藏某个简历板块（只改显示开关，不删内容）。"
                "触发条件：用户明确说'隐藏/不显示/去掉'某个板块。"
                "section 用模块 id：personal、summary、education、work、projects、open_source、skills。"
                "反引用 show_section 可恢复显示。"
                "不要主动隐藏板块——只响应用户的明确指令。"
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
                "显示某个简历板块（只改显示开关，不写内容）。"
                "触发条件：用户明确说'显示/加上/展示'某个板块。"
                "section 用模块 id：personal、summary、education、work、projects、open_source、skills。"
                "板块内容为空时只显示标题；如需有意义的内容，配合 update_summary 等写入工具。"
                "不要主动显示板块——只响应用户的明确指令。"
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
                "修改技能板块中某个技能分类的名称或技能列表。"
                "触发条件：用户要求调整技能分类、补充技能关键词、替换技能列表。"
                "category_id 必须来自当前简历 JSON 中已有的技能分类条目。"
                "mode=replace 替换整个列表，mode=merge 追加不重复的技能。"
                "约束：只能补充简历中已有证据或用户明确提供的技能，不得编造。"
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
                "修改工作/项目/教育条目的元数据字段（如职位、公司、项目名、学历等）。"
                "触发条件：用户要求修改公司名、职位头衔、项目角色、学历专业等非 bullet 字段。"
                "section 只能是 education、work_experience、projects。"
                "item_id 必须来自当前简历 JSON 中已有的条目。"
                "注意：这个工具不修改 bullet/亮点文本，改亮点用 update_bullet。"
                "不允许修改 is_current（内部派生字段）。不要编造事实。"
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
                "修改个人信息（求职意向、headline、地点、链接等）。"
                "触发条件：用户要求修改自己的求职定位、一句话介绍、地点或社交链接。"
                "支持字段：position、headline、location、github、linkedin、website、links。"
                "约束：不要主动修改个人信息，除非用户明确要求。"
                "修改 name/email/phone/address 时必须提供 source（来自用户输入或上传简历）。"
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
                "设置或更新简历的求职目标（目标公司、目标岗位、JD 原文）。"
                "触发条件：用户说'我要投XX公司'、'目标岗位是XX'、'这是JD'、'更新求职目标'。"
                "fields 只传用户明确要求修改的字段（target_company/target_title/jd_text），"
                "未传字段保持原样。"
                "注意：这个工具只改求职目标上下文，不修改简历内容本身。"
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
                "修改简历的'个人总结/自我评价'板块文本。"
                "触发条件：用户明确要求修改个人总结、自我评价、职业概述。"
                "不要在用户只要求优化亮点或项目时主动调用此工具。"
                "不得编造经历、数字、年限或结果。"
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
                "修改 projects 板块中某个项目条目的 overview 简介文本。"
                "触发条件：用户明确要求修改某个项目的简介/概述/描述。"
                "section 必须是 projects，item_id 必须来自当前简历 JSON。"
                "不要在用户只要求优化 bullet 时主动调用——改亮点用 update_bullet。"
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
            "description": (
                "列出当前用户保存过的 JD 摘要列表，只读。"
                "触发条件：用户要求查看、选择、对比历史 JD。"
                "不修改简历。"
            ),
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
            "description": (
                "按 job_post_id 读取一条完整 JD 原文，只读。"
                "触发条件：用户要求基于某个历史 JD 优化简历。"
                "不修改简历。"
            ),
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
            "name": "score_resume",
            "description": (
                "对当前简历做综合评分，只读不改。"
                "触发条件：用户要求给简历打分、评估质量、找出薄弱点。"
                "返回规则检查（完整度、量化、表达、JD 匹配）和语义评审。"
                "这个工具不修改简历，只返回评估结果。"
                "不要在用户要求直接修改简历时调用——先改再评分，不要只评分不改。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_bullet",
            "description": (
                "评价单条 bullet/亮点的质量，只读不改。"
                "触发条件：用户要求评价、分析某条具体亮点写得好不好。"
                "从量化程度、动作表达、结果影响、主导性和说服力五个维度打分。"
                "不要在用户要求直接修改时调用——先改再评价，不要只评价不改。"
                "section 只能是 education、work_experience、projects、open_source。"
                "item_id 和 bullet_id 必须来自当前简历 JSON。"
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
                "读取用户长期记忆（偏好、约束、已拒绝的写法），只读。"
                "触发条件：需要了解用户的长期偏好或事实约束时调用。"
                "不修改简历。"
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
                "记录用户明确表达的长期偏好或约束。"
                "触发条件：用户明确表达了偏好（如'不要用量化指标'）或事实约束。"
                "约束：只能记录用户明确表达的内容，不得推断或编造。"
                "不要在用户只要求优化简历时主动记录——只记录用户显式表达的偏好。"
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
                "修改（重写）已有的一条 bullet/亮点文本。"
                "触发条件：用户要求优化、重写、改写、量化某条已有的亮点或要点。"
                "选择规则：bullet 已存在且需要改内容 → 用这个工具；"
                "bullet 不存在需要新增 → 用 add_bullet。"
                "section 只能是 education、work_experience、projects、open_source。"
                "item_id 和 bullet_id 必须来自当前简历 JSON。"
                "text 必须与原文有实质差异（新增/重写了任务、技术、结果中至少一项），"
                "不要传入原文。"
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
                            "新的 bullet 文本。必须完整替换原 bullet，并且与原文存在实质差异："
                            "新增、删除或重写了任务、技术方案、问题、结果、影响中的至少一项。"
                            "不得传入原文，也不得仅调整空格、标点、语序或 reason。"
                            "只能写入当前简历、用户补充或背景档案中可追溯的事实；"
                            "JD 只能提供匹配方向，缺少来源的 JD 能力、实现细节或量化结果不能写入 text，"
                            "需要补充事实时，ask_user 用于向用户确认。"
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "本次修改的简短理由，供前端展示。reason 不能替代 text 修改；"
                            "如果 text 与原 bullet 无实质差异，不要调用该工具。"
                        ),
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
                "新增（追加）一条 bullet/亮点到已有的工作、项目、教育或开源条目下。"
                "触发条件：用户要求补充、添加、增加新的亮点或成果；"
                "或 JD 中的关键能力在现有 bullet 中无法通过修改来自然融入，需要新增一条来覆盖。"
                "选择规则：bullet 已存在要改内容 → 用 update_bullet；"
                "bullet 不存在要新增 → 用这个工具。"
                "section 只能是 education、work_experience、projects、open_source。"
                "item_id 必须来自当前简历 JSON 中已有的条目。"
                "约束：必须基于用户明确提供的事实，不得编造。"
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
                "删除某条已有的 bullet/亮点。"
                "触发条件：用户明确要求删除某条亮点、去掉某条要点。"
                "section 只能是 education、work_experience、projects、open_source。"
                "item_id 和 bullet_id 必须来自当前简历 JSON。"
                "不要未经用户同意主动删除亮点。"
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
        "score_resume",
        score_resume_tool,
        _SCHEMA_BY_NAME.get("score_resume"),
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
