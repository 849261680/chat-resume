"""Prompt 语义标签回归测试 — 参数化版本。

用语义标签替代精确字符串断言：prompt 措辞调整不再导致测试断裂。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.prompts import load_prompt  # noqa: E402
from tests.helpers.prompt_semantic_tags import (  # noqa: E402
    SCHEMA_TAGS,
    assert_tag,
)
from app.tools.resume.registry import RESUME_TOOLS_SCHEMA  # noqa: E402


def _render(**kwargs: str) -> str:
    """渲染 resume_agent 系统提示词模板。"""
    return load_prompt("resume_agent").render(**kwargs)


# ── P1: 参数化 Prompt 语义标签 ────────────────────────────

# 核心语义标签：渲染后必须包含的标签
_REQUIRED_TAGS = [
    "role_definition",
    "no_fabrication",
    "must_use_tools_for_mutations",
    "no_over_optimization",
    "follow_up_text_only",
    "tool_selection_rules",
    "quality_standards",
]

# 参数化：不同岗位/公司的渲染变体
_RENDER_VARIANTS = pytest.mark.parametrize(
    "title,company,jd",
    [
        ("AI Agent 开发工程师", "腾讯", "负责 Agent 产品能力建设"),
        ("前端工程师", "字节跳动", "负责复杂前端交互与性能优化"),
        ("产品经理", "美团", "负责策略优化与跨团队协同"),
        ("运营", "小红书", "负责活动运营与增长分析"),
        ("高级后端工程师", "字节跳动", "负责高并发系统设计与稳定性建设"),
    ],
)


@pytest.mark.parametrize("tag", _REQUIRED_TAGS)
@_RENDER_VARIANTS
def test_prompt_contains_required_semantic_tag(
    tag: str, title: str, company: str, jd: str
):
    """任意岗位参数下，核心语义标签必须始终存在于 prompt 中。"""
    rendered = _render(
        target_title=title,
        target_company=company,
        jd_text=jd,
        resume_json="{}",
    )
    assert_tag(rendered, tag)


# ── 禁止出现的字符串 ───────────────────────────────────────

_FORBIDDEN_STRINGS = [
    "read_user_memory",
    "write_user_memory",
    "可用工具",
    "${toolsList}",
    "${guidelines}",
    "Pi 文档",
    "量化改写优先级",
    "简历优化策略",
    "默认执行 `optimize-first`",
    "工具调用协议",
    "首轮",
]


@pytest.mark.parametrize("forbidden", _FORBIDDEN_STRINGS)
@_RENDER_VARIANTS
def test_prompt_never_contains_forbidden_string(
    forbidden: str, title: str, company: str, jd: str
):
    """泄露内部变量、未授权工具名、过时策略词不应出现在 prompt 中。"""
    rendered = _render(
        target_title=title,
        target_company=company,
        jd_text=jd,
        resume_json="{}",
    )
    assert forbidden not in rendered, (
        f"'{forbidden}' should not appear in system prompt"
    )


# ── P1: 参数化工具 Schema 语义标签 ────────────────────────

_SCHEMA_TAG_CHECKS = [
    ("update_bullet", "bullet_section_constraint"),
    ("update_bullet", "bullet_id_source"),
    ("update_overview", "overview_section_constraint"),
    ("update_item_fields", "is_current_protected"),
]


@pytest.mark.parametrize("tool_name,tag", _SCHEMA_TAG_CHECKS)
def test_tool_description_matches_semantic_tag(tool_name: str, tag: str):
    """每个工具的 description 必须携带对应的语义标签。"""
    schema = RESUME_TOOLS_SCHEMA
    tool = next(t for t in schema if t["function"]["name"] == tool_name)
    desc = tool["function"]["description"]
    assert_tag(desc, tag, registry=SCHEMA_TAGS)


# ── P1: 参数化 Tool Profile 检查 ─────────────────────────

_EDIT_TOOL_NAMES = [
    "update_summary",
    "update_profile",
    "upsert_job_application",
    "update_item_fields",
    "update_skills",
    "show_section",
    "hide_section",
    "update_overview",
    "update_bullet",
    "add_bullet",
    "remove_bullet",
    "score_resume",
    "evaluate_bullet",
    "list_job_posts",
    "read_job_post",
    "read_memory",
    "update_memory",
]


@pytest.mark.parametrize("tool_name", _EDIT_TOOL_NAMES)
def test_tool_exists_in_resume_edit_schema(tool_name: str):
    """resume_edit profile 中每个工具都必须在 RESUME_TOOLS_SCHEMA 中注册。"""
    schema_names = {t["function"]["name"] for t in RESUME_TOOLS_SCHEMA}
    assert tool_name in schema_names, f"{tool_name} missing from RESUME_TOOLS_SCHEMA"


@pytest.mark.parametrize("tool_name", _EDIT_TOOL_NAMES)
def test_tool_schema_has_function_dict(tool_name: str):
    """每个工具 schema 必须有有效的 function 定义。"""
    tool = next(t for t in RESUME_TOOLS_SCHEMA if t["function"]["name"] == tool_name)
    assert "function" in tool
    assert "name" in tool["function"]
    assert "description" in tool["function"]
    assert "parameters" in tool["function"]


# ── P1: 参数化更新类工具的 reason 字段 ─────────────────────

_TOOLS_WITH_REASON_PARAM = [
    "update_bullet",
    "add_bullet",
    "remove_bullet",
    "update_summary",
    "update_overview",
    "update_item_fields",
    "update_skills",
    "update_profile",
    "upsert_job_application",
]


@pytest.mark.parametrize("tool_name", _TOOLS_WITH_REASON_PARAM)
def test_mutation_tool_exposes_optional_reason_field(tool_name: str):
    """所有修改简历的工具必须有可选的 reason 参数。"""
    tool = next(t for t in RESUME_TOOLS_SCHEMA if t["function"]["name"] == tool_name)
    properties = tool["function"]["parameters"]["properties"]
    assert "reason" in properties
    assert properties["reason"]["type"] == "string"
