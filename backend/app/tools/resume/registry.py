"""用于集中声明简历工具 schema 和分发关系。"""

from __future__ import annotations

from typing import Any

from .add_highlight_tool import add_highlight
from .remove_highlight_tool import remove_highlight
from .update_highlight_tool import update_highlight
from .update_overview_tool import update_overview

_HIGHLIGHT_SECTIONS = ["education", "work_experience", "projects"]

RESUME_TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_user_memory",
            "description": (
                "读取当前登录用户的长期记忆 Markdown 文件，"
                "用于了解用户过往确认过的偏好、策略和事实。"
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
            "name": "write_user_memory",
            "description": (
                "覆盖写入当前登录用户的长期记忆 Markdown 文件。"
                "写入前应先读取现有记忆，并保留仍然有效的长期信息。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": (
                            "要写回的完整 Markdown 内容，"
                            "应保留有效旧记忆并合并本轮新增的长期信息。"
                        ),
                    }
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_overview",
            "description": (
                "更新 projects 板块中某个项目的 overview 简介，不修改其他事实字段。"
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
            "name": "update_highlight",
            "description": "精准更新某个条目下单条 highlight 的文本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": _HIGHLIGHT_SECTIONS,
                    },
                    "item_id": {
                        "type": "string",
                        "description": "经历/项目/教育条目的 id",
                    },
                    "highlight_id": {
                        "type": "string",
                        "description": "要修改的亮点 id",
                    },
                    "text": {
                        "type": "string",
                        "description": "新的亮点文本",
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "本次修改的简短理由，供前端展示，如“补充岗位关键词”"
                        ),
                    },
                },
                "required": ["section", "item_id", "highlight_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_highlight",
            "description": "向某个条目新增一条 highlight。",
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": _HIGHLIGHT_SECTIONS,
                    },
                    "item_id": {
                        "type": "string",
                        "description": "经历/项目/教育条目的 id",
                    },
                    "text": {
                        "type": "string",
                        "description": "新增的亮点文本",
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
            "name": "remove_highlight",
            "description": "从某个条目删除一条 highlight。",
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": _HIGHLIGHT_SECTIONS,
                    },
                    "item_id": {
                        "type": "string",
                        "description": "经历/项目/教育条目的 id",
                    },
                    "highlight_id": {
                        "type": "string",
                        "description": "要删除的亮点 id",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次删除的简短理由，供前端展示",
                    },
                },
                "required": ["section", "item_id", "highlight_id"],
            },
        },
    },
]

_RESUME_TOOL_HANDLERS = {
    "update_overview": update_overview,
    "update_highlight": update_highlight,
    "add_highlight": add_highlight,
    "remove_highlight": remove_highlight,
}


def execute_resume_tool(
    tool_name: str,
    *,
    resume_content: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """用于按工具名分发到对应的简历工具实现。"""
    handler = _RESUME_TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_name}"}
    return handler(resume_content, **kwargs)


__all__ = ["RESUME_TOOLS_SCHEMA", "execute_resume_tool"]
