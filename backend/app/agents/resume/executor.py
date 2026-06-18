"""用于承接简历工具的参数校验和统一执行返回。"""

from __future__ import annotations

from typing import Any, Literal, cast, overload

from app.tools.base import ToolExecutor
from app.tools.resume.registry import (
    RESUME_TOOL_DISPLAY_NAMES,
    RESUME_TOOL_REQUIRED_ARGS,
    RESUME_TOOL_SECTION_ENUMS,
    execute_prepared_resume_tool_call,
    resume_tool_error_result,
)

TOOL_REQUIRED_ARGS = RESUME_TOOL_REQUIRED_ARGS
TOOL_SECTION_ENUMS = RESUME_TOOL_SECTION_ENUMS
TOOL_DISPLAY_NAMES = RESUME_TOOL_DISPLAY_NAMES
_SYNC_TOOL_NAME = Literal[
    "ask_user",
    "update_summary",
    "update_profile",
    "add_resume_item",
    "remove_resume_item",
    "update_item_fields",
    "upsert_job_application",
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


class ResumeToolExecutor(ToolExecutor):
    """用于把 runtime 的工具调用转换成可落库的简历编辑结果。"""

    @overload
    def execute(
        self,
        *,
        tool_name: _SYNC_TOOL_NAME,
        tool_input: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """用于声明同步简历工具直接返回结果。"""
        ...

    @overload
    def execute(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """用于声明动态工具名可能返回同步或异步结果。"""
        ...

    def execute(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """用于兼容旧调用方并委托工具目录执行。"""
        return cast(
            dict[str, Any],
            execute_prepared_resume_tool_call(
                tool_name=tool_name,
                tool_input=tool_input,
                context=context,
            ),
        )

    def error_result(
        self,
        tool_name: str,
        error_type: str,
        message: str,
        *,
        recoverable: bool,
        expected_arguments: list[str] | None = None,
        updated_section: str | None = None,
    ) -> dict[str, Any]:
        """用于兼容旧测试并委托工具目录构造错误结果。"""
        return resume_tool_error_result(
            tool_name,
            error_type,
            message,
            recoverable=recoverable,
            expected_arguments=expected_arguments,
            updated_section=updated_section,
        )


__all__ = [
    "ResumeToolExecutor",
    "TOOL_DISPLAY_NAMES",
    "TOOL_REQUIRED_ARGS",
    "TOOL_SECTION_ENUMS",
]
