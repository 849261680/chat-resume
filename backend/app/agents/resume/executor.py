"""用于承接简历工具的参数校验和统一执行返回。"""

from __future__ import annotations

from collections.abc import Awaitable
from inspect import isawaitable
from typing import Any, Literal, overload

from app.tools.base import ToolExecutor
from app.tools.resume.registry import execute_resume_tool

TOOL_REQUIRED_ARGS: dict[str, set[str]] = {
    "update_summary": {"text"},
    "update_profile": {"fields"},
    "update_item_fields": {"section", "item_id", "fields"},
    "upsert_job_application": {"fields"},
    "update_skills": {"category_id", "items"},
    "show_section": {"section"},
    "hide_section": {"section"},
    "update_overview": {"section", "item_id", "overview"},
    "update_bullet": {"section", "item_id", "bullet_id", "text"},
    "add_bullet": {"section", "item_id", "text"},
    "remove_bullet": {"section", "item_id", "bullet_id"},
    "update_highlight": {"section", "item_id", "highlight_id", "text"},
    "add_highlight": {"section", "item_id", "text"},
    "remove_highlight": {"section", "item_id", "highlight_id"},
    "score_resume": set(),
    "list_job_posts": set(),
    "read_job_post": {"job_post_id"},
    "read_memory": {"scope"},
    "update_memory": {"operation", "scope"},
}

TOOL_SECTION_ENUMS: dict[str, set[str]] = {
    "update_overview": {"projects"},
    "update_item_fields": {"education", "work_experience", "projects"},
    # 接受模块 id 以及 _SECTION_ALIASES 归一化后的 content key（如 work→work_experience）
    "show_section": {
        "personal",
        "summary",
        "education",
        "work",
        "work_experience",
        "projects",
        "open_source",
        "skills",
    },
    "hide_section": {
        "personal",
        "summary",
        "education",
        "work",
        "work_experience",
        "projects",
        "open_source",
        "skills",
    },
    "update_bullet": {"education", "work_experience", "projects"},
    "add_bullet": {"education", "work_experience", "projects"},
    "remove_bullet": {"education", "work_experience", "projects"},
    "update_highlight": {"education", "work_experience", "projects"},
    "add_highlight": {"education", "work_experience", "projects"},
    "remove_highlight": {"education", "work_experience", "projects"},
}

TOOL_DISPLAY_NAMES = {
    "update_summary": "优化总结",
    "update_profile": "优化个人信息",
    "upsert_job_application": "更新求职目标",
    "update_item_fields": "优化条目字段",
    "update_skills": "优化技能",
    "show_section": "显示板块",
    "hide_section": "隐藏板块",
    "update_overview": "优化简介",
    "update_bullet": "优化要点",
    "add_bullet": "新增要点",
    "remove_bullet": "删除要点",
    "update_highlight": "优化要点",
    "add_highlight": "新增要点",
    "remove_highlight": "删除要点",
    "score_resume": "简历评分",
    "list_job_posts": "读取JD列表",
    "read_job_post": "读取JD",
    "read_resume": "读取简历",
    "read_memory": "读取记忆",
    "update_memory": "更新记忆",
}
_SYNC_TOOL_NAME = Literal[
    "update_summary",
    "update_profile",
    "update_item_fields",
    "upsert_job_application",
    "update_skills",
    "show_section",
    "hide_section",
    "update_overview",
    "update_bullet",
    "add_bullet",
    "remove_bullet",
    "update_highlight",
    "add_highlight",
    "remove_highlight",
    "read_resume",
    "score_resume",
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
    ) -> dict[str, Any] | Awaitable[dict[str, Any]]:
        """用于声明动态工具名可能返回同步或异步结果。"""
        ...

    def execute(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any] | Awaitable[dict[str, Any]]:
        """用于执行单次简历工具调用并补齐展示字段。"""
        resume_content = context["resume_content"]
        allowed_sections = context.get("allowed_sections")
        target_section = tool_input.get("section")

        _VISIBILITY_TOOLS = {"show_section", "hide_section"}
        if (
            allowed_sections is not None
            and target_section
            and target_section not in allowed_sections
            and tool_name not in _VISIBILITY_TOOLS
        ):
            return self.error_result(
                tool_name,
                "hidden_section",
                f"板块 {target_section} 当前已隐藏，禁止修改",
                recoverable=False,
                updated_section=target_section,
            )

        supported_sections = TOOL_SECTION_ENUMS.get(tool_name)
        if supported_sections is not None and target_section not in supported_sections:
            return self.error_result(
                tool_name,
                "invalid_section",
                f"{tool_name} 不支持修改板块 {target_section}",
                recoverable=True,
                expected_arguments=sorted(TOOL_REQUIRED_ARGS.get(tool_name, set())),
                updated_section=target_section,
            )

        try:
            if tool_name == "list_job_posts":
                tool_input = {
                    **tool_input,
                    "user_id": context.get("user_id"),
                    "list_job_posts_reader": context.get("list_job_posts_reader"),
                }
            if tool_name == "read_job_post":
                tool_input = {
                    **tool_input,
                    "user_id": context.get("user_id"),
                    "read_job_post_reader": context.get("read_job_post_reader"),
                }
            if tool_name in {"read_memory", "update_memory"}:
                tool_input = {
                    **tool_input,
                    "user_id": context.get("user_id"),
                    "resume_id": context.get("resume_id"),
                    "memory_dir": context.get("memory_dir"),
                }
            if tool_name == "update_memory" and context.get("dry_run") is True:
                tool_input = {**tool_input, "dry_run": True}
            result = execute_resume_tool(
                tool_name=tool_name,
                resume_content=resume_content,
                **tool_input,
            )
            if isawaitable(result):
                return self._wrap_async_result(
                    result,
                    tool_name=tool_name,
                    updated_section=target_section,
                )
        except TypeError as exc:
            return self.error_result(
                tool_name,
                "tool_argument_type_error",
                f"{tool_name} 参数不匹配: {exc}",
                recoverable=True,
                expected_arguments=sorted(TOOL_REQUIRED_ARGS.get(tool_name, set())),
                updated_section=target_section,
            )
        except Exception as exc:
            return self.error_result(
                tool_name,
                "tool_execution_error",
                f"{tool_name} 执行失败: {exc}",
                recoverable=False,
                updated_section=target_section,
            )

        return self._wrap_success_result(
            tool_name=tool_name,
            result=result,
            updated_section=target_section,
        )

    async def _wrap_async_result(
        self,
        pending_result: Awaitable[dict[str, Any]],
        *,
        tool_name: str,
        updated_section: str | None,
    ) -> dict[str, Any]:
        """用于等待异步工具并包装成统一工具结果结构。"""
        try:
            result = await pending_result
        except TypeError as exc:
            return self.error_result(
                tool_name,
                "tool_argument_type_error",
                f"{tool_name} 参数不匹配: {exc}",
                recoverable=True,
                expected_arguments=sorted(TOOL_REQUIRED_ARGS.get(tool_name, set())),
                updated_section=updated_section,
            )
        except Exception as exc:
            return self.error_result(
                tool_name,
                "tool_execution_error",
                f"{tool_name} 执行失败: {exc}",
                recoverable=False,
                updated_section=updated_section,
            )
        return self._wrap_success_result(
            tool_name=tool_name,
            result=result,
            updated_section=updated_section,
        )

    def _wrap_success_result(
        self,
        *,
        tool_name: str,
        result: dict[str, Any],
        updated_section: str | None,
    ) -> dict[str, Any]:
        """用于把工具成功返回包装成 runtime 统一结构。"""
        return {
            "tool_name": TOOL_DISPLAY_NAMES.get(tool_name, tool_name),
            "result": result,
            "display_message": (
                result.get("diff_summary") or result.get("message")
                if isinstance(result, dict)
                else None
            ),
            "qr_image": result.get("image_base64")
            if isinstance(result, dict)
            else None,
            "updated_section_name": self._get_section_name(
                result.get("updated_section")
                if isinstance(result, dict)
                else updated_section
            ),
        }

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
        """用于把工具异常包装成统一的失败结果结构。"""
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
            "tool_name": TOOL_DISPLAY_NAMES.get(tool_name, tool_name),
            "result": result,
            "display_message": message,
            "qr_image": None,
            "updated_section_name": self._get_section_name(updated_section),
        }

    @staticmethod
    def _get_section_name(section_key: str | None) -> str | None:
        """用于把内部板块 key 转成前端更容易展示的中文名称。"""
        section_names = {
            "personal_info": "个人信息",
            "education": "教育经历",
            "work_experience": "工作经历",
            "skills": "技能专长",
            "projects": "项目经历",
            "summary": "个人总结",
            "job_application": "求职目标",
            "languages": "语言能力",
        }
        if not section_key:
            return None
        return section_names.get(section_key, section_key)


__all__ = [
    "ResumeToolExecutor",
    "TOOL_DISPLAY_NAMES",
    "TOOL_REQUIRED_ARGS",
    "TOOL_SECTION_ENUMS",
]
