"""用于覆盖简历 Agent 对开源经历的上下文和工具支持。"""

from __future__ import annotations

from app.agents.resume.session import maybe_compact_resume_context
from app.tools.resume.registry import (
    RESUME_TOOL_SECTION_ENUMS,
    RESUME_TOOLS_SCHEMA,
    execute_prepared_resume_tool_call,
)
from app.tools.resume.update_bullet_tool import update_bullet


def test_compacted_resume_context_keeps_open_source():
    """用于验证长上下文摘要仍保留开源经历。"""
    resume_content = {
        "open_source": [
            {
                "id": "oss_1",
                "name": "ChatResume",
                "role": "Contributor",
                "highlights": [
                    {
                        "id": "oss_hl_1",
                        "text": "修复 Agent 工具调用回归，补充端到端测试。",
                    }
                ],
            }
        ],
        "projects": [{"id": "proj_1", "name": "项目", "highlights": []}],
    }

    compacted = maybe_compact_resume_context(
        resume_content=resume_content,
        conversation_history=[{"role": "user", "content": "x" * 20}],
        threshold_chars=1,
    )

    snapshot = compacted["resume_snapshot"]
    assert snapshot["open_source"][0]["id"] == "oss_1"
    assert snapshot["open_source"][0]["highlights"][0]["text"].startswith("修复 Agent")


def test_open_source_is_allowed_by_bullet_tool_contracts():
    """用于验证工具 schema、executor 和底层工具都支持开源经历要点。"""
    schema_by_name = {tool["function"]["name"]: tool for tool in RESUME_TOOLS_SCHEMA}
    bullet_tools = ["update_bullet", "add_bullet", "remove_bullet"]

    for tool_name in bullet_tools:
        section_enum = schema_by_name[tool_name]["function"]["parameters"]["properties"]["section"]["enum"]
        assert "open_source" in section_enum
        assert "open_source" in RESUME_TOOL_SECTION_ENUMS[tool_name]

    resume_content = {
        "open_source": [
            {
                "id": "oss_1",
                "name": "ChatResume",
                "highlights": [{"id": "oss_hl_1", "text": "修复问题"}],
            }
        ]
    }
    result = update_bullet(
        resume_content,
        section="open_source",
        item_id="oss_1",
        bullet_id="oss_hl_1",
        text="修复 Agent 工具调用问题，补充回归测试。",
    )

    assert result["success"] is True
    assert resume_content["open_source"][0]["highlights"][0]["text"].startswith("修复 Agent")


def test_open_source_is_allowed_by_resume_item_tools():
    """用于验证新增和更新条目工具支持开源经历字段。"""
    schema_by_name = {tool["function"]["name"]: tool for tool in RESUME_TOOLS_SCHEMA}
    item_tools = ["add_resume_item", "update_item_fields", "remove_resume_item"]

    for tool_name in item_tools:
        section_enum = schema_by_name[tool_name]["function"]["parameters"]["properties"]["section"]["enum"]
        assert "open_source" in section_enum
        assert "open_source" in RESUME_TOOL_SECTION_ENUMS[tool_name]

    resume_content: dict[str, object] = {}
    add_result = execute_prepared_resume_tool_call(
        tool_name="add_resume_item",
        tool_input={
            "section": "open_source",
            "item_id": "oss_1",
            "fields": {
                "name": "ChatResume",
                "overview": "开源简历优化 Agent",
                "role": "Maintainer",
                "github_url": "https://github.com/example/chat-resume",
            },
        },
        context={"resume_content": resume_content, "allowed_sections": {"open_source"}},
    )
    update_result = execute_prepared_resume_tool_call(
        tool_name="update_item_fields",
        tool_input={
            "section": "open_source",
            "item_id": "oss_1",
            "fields": {"role": "Core Maintainer"},
        },
        context={"resume_content": resume_content, "allowed_sections": {"open_source"}},
    )
    remove_result = execute_prepared_resume_tool_call(
        tool_name="remove_resume_item",
        tool_input={
            "section": "open_source",
            "item_id": "oss_1",
            "reason": "用户要求删除该开源经历",
        },
        context={"resume_content": resume_content, "allowed_sections": {"open_source"}},
    )

    assert add_result["result"]["success"] is True
    assert update_result["result"]["success"] is True
    assert remove_result["result"]["success"] is True
    assert resume_content["open_source"] == []
