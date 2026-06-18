"""工具 Schema 契约测试 — 参数化版本。

验证所有 resume 工具的 schema 结构一致性和字段完整性。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.tools.resume.registry import (  # noqa: E402
    RESUME_AUTO_EXECUTE_TOOL_NAMES,
    RESUME_TOOL_ARGUMENT_ALIASES,
    RESUME_TOOL_CATALOG,
    RESUME_TOOL_DISPLAY_NAMES,
    RESUME_TOOL_PROFILES,
    RESUME_TOOL_REQUIRED_ARGS,
    RESUME_TOOL_SECTION_ENUMS,
    RESUME_VISIBILITY_TOOL_NAMES,
    RESUME_TOOLS_SCHEMA,
    execute_resume_tool_call,
)
from tests.helpers.prompt_semantic_tags import SCHEMA_TAGS, assert_tag  # noqa: E402


# ── 参数化数据 ──────────────────────────────────────────────

# 所有已知的 resume 工具
_ALL_RESUME_TOOLS: list[str] = [
    "update_summary",
    "update_profile",
    "upsert_job_application",
    "add_resume_item",
    "remove_resume_item",
    "update_item_fields",
    "update_skills",
    "show_section",
    "hide_section",
    "update_overview",
    "update_bullet",
    "add_bullet",
    "remove_bullet",
    "list_job_posts",
    "read_job_post",
    "read_memory",
    "update_memory",
]

# 工具 → 必需参数
_TOOL_REQUIRED_PARAMS: dict[str, list[str]] = {
    "update_summary": ["text"],
    "update_profile": ["fields"],
    "upsert_job_application": ["fields"],
    "add_resume_item": ["section", "fields"],
    "remove_resume_item": ["section", "item_id"],
    "update_item_fields": ["section", "item_id", "fields"],
    "update_skills": ["category_id"],
    "update_bullet": ["section", "item_id", "bullet_id", "text"],
    "add_bullet": ["section", "item_id", "text"],
    "remove_bullet": ["section", "item_id", "bullet_id"],
}

# 工具 → 禁止暴露的参数
_TOOL_FORBIDDEN_PARAMS: dict[str, list[str]] = {
    "update_item_fields": ["technologies"],
}

# 语义标签 → (工具, 参数字段) — None=主 description, str=param description
_SCHEMA_TAG_CHECKS: list[tuple[str, str, str | None]] = [
    ("bullet_section_constraint", "update_bullet", None),
    ("bullet_id_source", "update_bullet", None),
    ("overview_section_constraint", "update_overview", None),
    ("is_current_protected", "update_item_fields", None),
    ("text_must_differ", "update_bullet", None),
    ("no_passthrough", "update_bullet", None),
    # reason_not_substitute 在 reason 参数描述中，不在主 description
    ("reason_not_substitute", "update_bullet", "reason"),
]


# ── 参数化测试 ──────────────────────────────────────────────


@pytest.mark.parametrize("tool_name", _ALL_RESUME_TOOLS)
class TestResumeToolSchema:
    """所有 resume 工具 schema 的结构契约。"""

    def test_has_valid_structure(self, tool_name: str):
        """每个工具必须有 type/function/name/description/parameters。"""
        tool = next(
            t for t in RESUME_TOOLS_SCHEMA if t["function"]["name"] == tool_name
        )
        assert tool["type"] == "function"
        assert "function" in tool
        func = tool["function"]
        assert "name" in func
        assert func["name"] == tool_name
        assert "description" in func
        assert isinstance(func["description"], str)
        assert len(func["description"]) > 10
        assert "parameters" in func
        params = func["parameters"]
        assert params["type"] == "object"
        assert "properties" in params

    def test_section_param_is_enum_when_present(self, tool_name: str):
        """包含 section 参数的工具必须将其约束为 enum。"""
        tool = next(
            t for t in RESUME_TOOLS_SCHEMA if t["function"]["name"] == tool_name
        )
        properties = tool["function"]["parameters"]["properties"]
        if "section" in properties:
            section_schema = properties["section"]
            assert "enum" in section_schema, (
                f"{tool_name}.section must be enum"
            )


@pytest.mark.parametrize("tool_name,required_params", _TOOL_REQUIRED_PARAMS.items())
def test_tool_has_required_params(tool_name: str, required_params: list[str]):
    """必需参数必须出现在 properties 中。"""
    tool = next(t for t in RESUME_TOOLS_SCHEMA if t["function"]["name"] == tool_name)
    properties = tool["function"]["parameters"]["properties"]
    required = tool["function"]["parameters"].get("required", [])
    for param in required_params:
        assert param in properties, (
            f"{tool_name}: '{param}' missing from properties"
        )
        assert param in required, (
            f"{tool_name}: '{param}' must be in required list"
        )


@pytest.mark.parametrize("tool_name,forbidden", _TOOL_FORBIDDEN_PARAMS.items())
def test_tool_excludes_forbidden_params(tool_name: str, forbidden: list[str]):
    """禁止字段不能出现在 properties 中。"""
    tool = next(t for t in RESUME_TOOLS_SCHEMA if t["function"]["name"] == tool_name)
    properties = tool["function"]["parameters"]["properties"]
    for param in forbidden:
        assert param not in properties, (
            f"{tool_name}: '{param}' should not be exposed"
        )


def test_update_bullet_text_requires_source_backed_facts():
    """update_bullet 的 text 参数必须声明当前事实来源边界。"""
    tool = next(
        t for t in RESUME_TOOLS_SCHEMA if t["function"]["name"] == "update_bullet"
    )
    desc = tool["function"]["parameters"]["properties"]["text"]["description"]

    assert "当前简历、用户补充或背景档案" in desc
    assert "不得传入原文" in desc
    assert "只调整空格、标点或语序" in desc


def test_update_skills_schema_supports_add_update_and_remove():
    """update_skills 必须用一个工具覆盖技能分类的增删改。"""
    tool = next(t for t in RESUME_TOOLS_SCHEMA if t["function"]["name"] == "update_skills")
    function = tool["function"]
    properties = function["parameters"]["properties"]

    assert function["parameters"]["required"] == ["category_id"]
    assert properties["mode"]["enum"] == ["replace", "merge", "remove"]
    assert "创建新分类" in function["description"]
    assert "删除整个分类" in function["description"]
    assert "remove 不需要" in properties["skills"]["description"]


def test_tool_catalog_is_single_source_for_runtime_metadata():
    """工具目录必须携带运行时元数据并派生旧导出常量。"""
    by_name = {definition.name: definition for definition in RESUME_TOOL_CATALOG}

    derived_profiles: dict[str, set[str]] = {}
    for definition in RESUME_TOOL_CATALOG:
        for profile in definition.profiles:
            derived_profiles.setdefault(profile, set()).add(definition.name)

    assert set(by_name) == {tool["function"]["name"] for tool in RESUME_TOOLS_SCHEMA}
    assert RESUME_TOOL_PROFILES == derived_profiles
    assert RESUME_TOOL_REQUIRED_ARGS == {
        name: set(definition.required_args)
        for name, definition in by_name.items()
    }
    assert RESUME_TOOL_DISPLAY_NAMES == {
        name: definition.display_name
        for name, definition in by_name.items()
        if definition.display_name
    }
    assert RESUME_TOOL_SECTION_ENUMS == {
        name: set(definition.section_enum)
        for name, definition in by_name.items()
        if definition.section_enum
    }
    assert RESUME_TOOL_ARGUMENT_ALIASES == {
        name: dict(definition.argument_aliases)
        for name, definition in by_name.items()
        if definition.argument_aliases
    }
    assert RESUME_AUTO_EXECUTE_TOOL_NAMES == {
        name for name, definition in by_name.items() if definition.auto_execute
    }
    assert RESUME_VISIBILITY_TOOL_NAMES == {
        name for name, definition in by_name.items() if definition.visibility_tool
    }


def test_tool_catalog_executes_raw_json_arguments_with_wrapped_result():
    """工具目录执行入口必须解析 JSON 参数并返回统一 runtime 结果。"""
    resume = {
        "projects": [{"id": "proj_1", "name": "Chat Resume", "overview": "旧简介"}]
    }

    result = execute_resume_tool_call(
        tool_name="update_overview",
        raw_arguments='{"item_id":"proj_1","text":"新简介"}',
        context={"resume_content": resume, "allowed_sections": {"projects"}},
    )

    assert isinstance(result, dict)
    assert result["tool_name"] == "优化简介"
    assert result["result"]["success"] is True
    assert resume["projects"][0]["overview"] == "新简介"


def test_tool_catalog_preserves_hidden_section_guard():
    """工具目录执行入口必须集中拦截隐藏板块修改。"""
    result = execute_resume_tool_call(
        tool_name="add_bullet",
        raw_arguments={
            "section": "projects",
            "item_id": "proj_1",
            "text": "新增成果",
        },
        context={"resume_content": {"projects": []}, "allowed_sections": {"skills"}},
    )

    assert isinstance(result, dict)
    assert result["result"]["success"] is False
    assert result["result"]["error"]["type"] == "hidden_section"
    assert result["result"]["error"]["recoverable"] is False


@pytest.mark.parametrize("tag,tool_name,field_path", _SCHEMA_TAG_CHECKS)
def test_tool_carries_semantic_tag(tag: str, tool_name: str, field_path: str | None):
    """指定工具（或参数字段）必须包含对应语义标签。"""
    tool = next(
        t for t in RESUME_TOOLS_SCHEMA if t["function"]["name"] == tool_name
    )
    if field_path is None:
        desc = tool["function"]["description"]
    else:
        desc = tool["function"]["parameters"]["properties"][field_path]["description"]
    assert_tag(desc, tag, registry=SCHEMA_TAGS)
