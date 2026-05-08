"""用于承接简历工具的参数校验和统一执行返回。"""

from __future__ import annotations

from typing import Any

from app.tools.base import ToolExecutor
from app.tools.resume.read_user_memory_tool import read_user_memory
from app.tools.resume.registry import execute_resume_tool
from app.tools.resume.write_user_memory_tool import write_user_memory

TOOL_REQUIRED_ARGS: dict[str, set[str]] = {
    "write_user_memory": {"content"},
    "update_overview": {"section", "item_id", "overview"},
    "update_highlight": {"section", "item_id", "highlight_id", "text"},
    "add_highlight": {"section", "item_id", "text"},
    "remove_highlight": {"section", "item_id", "highlight_id"},
}

TOOL_SECTION_ENUMS: dict[str, set[str]] = {
    "update_overview": {"projects"},
    "update_highlight": {"education", "work_experience", "projects"},
    "add_highlight": {"education", "work_experience", "projects"},
    "remove_highlight": {"education", "work_experience", "projects"},
}

TOOL_DISPLAY_NAMES = {
    "read_user_memory": "读取用户记忆",
    "write_user_memory": "更新用户记忆",
    "update_overview": "优化简介",
    "update_highlight": "优化成果",
    "add_highlight": "新增成果",
    "remove_highlight": "删除成果",
}


class ResumeToolExecutor(ToolExecutor):
    """用于把 runtime 的工具调用转换成可落库的简历编辑结果。"""

    def execute(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """用于执行单次简历工具调用并补齐展示字段。"""
        if tool_name == "read_user_memory":
            return self._execute_read_user_memory(context=context)
        if tool_name == "write_user_memory":
            return self._execute_write_user_memory(
                tool_input=tool_input, context=context
            )

        resume_content = context["resume_content"]
        allowed_sections = context.get("allowed_sections")
        target_section = tool_input.get("section")

        if (
            allowed_sections is not None
            and target_section
            and target_section not in allowed_sections
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
            result = execute_resume_tool(
                tool_name=tool_name,
                resume_content=resume_content,
                **tool_input,
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
                result.get("updated_section") if isinstance(result, dict) else None
            ),
        }

    def _execute_read_user_memory(self, *, context: dict[str, Any]) -> dict[str, Any]:
        """用于读取当前会话用户绑定的长期记忆。"""
        user_id = context.get("user_id")
        if not isinstance(user_id, int):
            return self.error_result(
                "read_user_memory",
                "missing_user_id",
                "当前会话缺少用户身份，无法读取长期记忆",
                recoverable=True,
            )
        result = read_user_memory(user_id=user_id)
        return {
            "tool_name": TOOL_DISPLAY_NAMES["read_user_memory"],
            "result": result,
            "display_message": str(result.get("message", "") or "已读取用户长期记忆"),
            "qr_image": None,
            "updated_section_name": None,
            "requires_confirmation": False,
        }

    def _execute_write_user_memory(
        self,
        *,
        tool_input: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """用于覆盖写入当前会话用户绑定的长期记忆。"""
        user_id = context.get("user_id")
        if not isinstance(user_id, int):
            return self.error_result(
                "write_user_memory",
                "missing_user_id",
                "当前会话缺少用户身份，无法写入长期记忆",
                recoverable=True,
            )
        try:
            result = write_user_memory(
                user_id=user_id, content=str(tool_input.get("content", "") or "")
            )
        except ValueError as exc:
            return self.error_result(
                "write_user_memory",
                "invalid_memory_content",
                str(exc),
                recoverable=True,
                expected_arguments=["content"],
            )
        return {
            "tool_name": TOOL_DISPLAY_NAMES["write_user_memory"],
            "result": result,
            "display_message": str(result.get("message", "") or "已更新用户长期记忆"),
            "qr_image": None,
            "updated_section_name": None,
            "requires_confirmation": False,
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
