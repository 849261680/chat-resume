"""用于封装简历优化 Agent 的业务入口。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, cast

from app.prompts import load_prompt
from app.runtime.contracts import AgentDefinition
from app.tools.resume.registry import RESUME_TOOLS_SCHEMA
from app.types.stream import ResumeStreamEvent

from .candidate_profile import load_candidate_profile_context
from .executor import TOOL_REQUIRED_ARGS, ResumeToolExecutor
from .prompt_context import build_resume_prompt_context, strip_redundant_fields
from .runtime import ResumeAgentRuntime
from .stream_events import normalize_resume_stream_payload

logger = logging.getLogger(__name__)

_AUTO_EXECUTE_TOOL_NAMES: set[str] = {
    "ask_user",
    "score_resume",
    "evaluate_bullet",
    "list_job_posts",
    "read_job_post",
    "read_memory",
    "update_memory",
}
_TOOL_PROFILES: dict[str, set[str]] = {
    "resume_edit": {
        "ask_user",
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
    },
    "read_only": {
        "ask_user",
        "score_resume",
        "list_job_posts",
        "read_job_post",
        "read_memory",
    },
}
_LOG_VALUE_LIMIT = 64
_SECTION_ALIASES = {
    "work": "work_experience",
    "work_experiences": "work_experience",
    "experience": "work_experience",
    "project": "projects",
    "project_experience": "projects",
    "edu": "education",
}
_ARGUMENT_ALIASES_BY_TOOL = {
    "update_bullet": {"highlight_id": "bullet_id"},
    "remove_bullet": {"highlight_id": "bullet_id"},
    "update_overview": {"text": "overview", "description": "overview"},
    "update_skills": {"skills": "items"},
}


def _parse_tool_arguments(raw: Any) -> Dict[str, Any]:
    """用于把模型返回的工具参数统一解析成字典。"""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError(f"无法解析工具参数类型: {type(raw)}, value={raw!r}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "tool_args.json_parse_failed",
            extra={"error_type": type(exc).__name__, "raw_chars": len(raw)},
        )
        import re

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise


def _summarize_log_value(value: Any) -> Any:
    """用于处理summarize日志值。"""
    if isinstance(value, str):
        normalized = " ".join(value.split())
        if len(normalized) <= _LOG_VALUE_LIMIT:
            return normalized
        return f"{normalized[:_LOG_VALUE_LIMIT]}..."
    if isinstance(value, dict):
        return {
            str(key): _summarize_log_value(item)
            for key, item in list(value.items())[:8]
        }
    if isinstance(value, list):
        return [_summarize_log_value(item) for item in value[:5]]
    return value


def _normalize_tool_args(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    """用于修正常见模型工具参数别名，不推断缺失事实。"""
    normalized = dict(tool_args)
    section = normalized.get("section")
    if isinstance(section, str):
        normalized["section"] = _SECTION_ALIASES.get(section, section)

    for source, target in _ARGUMENT_ALIASES_BY_TOOL.get(tool_name, {}).items():
        if target not in normalized and source in normalized:
            normalized[target] = normalized[source]
        if source in normalized and source != target:
            normalized.pop(source)
    return normalized


class ResumeAgent:
    """用于组合提示词、运行时和工具执行器，形成完整简历 Agent。"""

    def __init__(self):
        """用于初始化简历 Agent 运行所需的固定依赖。"""
        self.tool_executor = ResumeToolExecutor()
        self.prompt_spec = load_prompt("resume_agent")
        self.runtime: Any = ResumeAgentRuntime()
        self.definition = AgentDefinition(
            prompt_spec=self.prompt_spec,
            tools_schema=RESUME_TOOLS_SCHEMA,
            tool_executor=self._run_tool,
            prompt_context_builder=build_resume_prompt_context,
            auto_execute_tool_names=_AUTO_EXECUTE_TOOL_NAMES,
            default_tool_profile="resume_edit",
            tool_profiles=_TOOL_PROFILES,
        )

    async def optimize(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        allowed_sections: Optional[set[str]] = None,
        user_id: Optional[int] = None,
        resume_id: Optional[int] = None,
        list_job_posts_reader: Any = None,
        read_job_post_reader: Any = None,
    ) -> Dict[str, Any]:
        """用于执行一次非流式简历优化请求。"""
        runtime_result = await self.runtime.run(
            agent=self.definition,
            user_message=user_message,
            context={
                "resume_content": resume_content,
                "allowed_sections": allowed_sections,
                "user_id": user_id,
                "resume_id": resume_id,
                "candidate_profile": load_candidate_profile_context(
                    user_id=user_id,
                    resume_id=resume_id,
                ).markdown,
                "list_job_posts_reader": list_job_posts_reader,
                "read_job_post_reader": read_job_post_reader,
            },
            conversation_history=conversation_history,
        )
        return {
            "content": runtime_result["content"],
            "qr_images": self._collect_qr_images(runtime_result["tool_calls"]),
            "tool_calls": runtime_result["tool_calls"],
            "resume_content": resume_content,
        }

    async def optimize_stream(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        confirmation_queue: Optional[asyncio.Queue] = None,
        allowed_sections: Optional[set[str]] = None,
        event_callback=None,
        user_id: Optional[int] = None,
        resume_id: Optional[int] = None,
        list_job_posts_reader: Any = None,
        read_job_post_reader: Any = None,
        visible_modules: Optional[List[str]] = None,
    ) -> AsyncGenerator[ResumeStreamEvent, None]:
        """用于执行一次带工具确认能力的流式简历优化请求。"""
        # 把当前可见模块作为基线写入 content meta，供 show/hide_section 工具读取与改写
        if visible_modules is not None and isinstance(resume_content, dict):
            resume_content.setdefault("_visible_modules", list(visible_modules))
        context: dict[str, Any] = {
            "resume_content": resume_content,
            "allowed_sections": allowed_sections,
            "user_id": user_id,
            "resume_id": resume_id,
            "candidate_profile": load_candidate_profile_context(
                user_id=user_id,
                resume_id=resume_id,
            ).markdown,
            "list_job_posts_reader": list_job_posts_reader,
            "read_job_post_reader": read_job_post_reader,
            "visible_modules": visible_modules or [],
        }
        async for event in self.runtime.run_stream(
            agent=self.definition,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            confirmation_queue=confirmation_queue,
            event_callback=event_callback,
        ):
            yield normalize_resume_stream_payload(
                event,
                resume_content=context.get("resume_content")
                if event.get("context") is not None
                else None,
            )

    @staticmethod
    def _strip_redundant_fields(resume_content: Dict[str, Any]) -> Dict[str, Any]:
        """用于复用精简后的简历上下文，减少提示词噪音。"""
        return strip_redundant_fields(resume_content)

    def _build_prompt_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """用于生成提示词渲染所需的简历上下文字段。"""
        return build_resume_prompt_context(context)

    def _prepare_tool_args(
        self,
        tool_name: str,
        raw_args: Any,
    ) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """用于校验和补齐工具参数，避免模型参数异常直接落到业务层。"""
        try:
            tool_args = _parse_tool_arguments(raw_args)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return None, self.tool_executor.error_result(
                tool_name,
                "invalid_arguments_json",
                f"工具参数不是合法 JSON，无法执行 {tool_name}: {exc}",
                recoverable=True,
                expected_arguments=sorted(TOOL_REQUIRED_ARGS.get(tool_name, set())),
            )

        if not isinstance(tool_args, dict):
            return None, self.tool_executor.error_result(
                tool_name,
                "invalid_arguments_type",
                f"工具参数必须是对象，实际收到 {type(tool_args).__name__}",
                recoverable=True,
                expected_arguments=sorted(TOOL_REQUIRED_ARGS.get(tool_name, set())),
            )

        tool_args = _normalize_tool_args(tool_name, tool_args)

        if tool_name == "update_overview" and not tool_args.get("section"):
            tool_args["section"] = "projects"

        required = TOOL_REQUIRED_ARGS.get(tool_name)
        if required is None:
            return None, self.tool_executor.error_result(
                tool_name,
                "unknown_tool",
                f"Unknown tool: {tool_name}",
                recoverable=False,
            )

        if required:
            missing = sorted(key for key in required if not tool_args.get(key))
            if missing:
                return None, self.tool_executor.error_result(
                    tool_name,
                    "missing_required_argument",
                    f"{tool_name} 缺少必填参数: {', '.join(missing)}",
                    recoverable=True,
                    expected_arguments=sorted(required),
                    updated_section=tool_args.get("section"),
                )

        return tool_args, None

    def _run_tool(
        self,
        tool_call: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """用于把一次工具调用转交给简历工具执行器。"""
        tool_name = tool_call["function"]["name"]
        raw_args = tool_call["function"]["arguments"]
        logger.debug(
            "[tool_call] %s args=%r",
            tool_name,
            _summarize_log_value(raw_args),
        )
        tool_args, error_result = self._prepare_tool_args(tool_name, raw_args)
        if error_result is not None:
            return error_result
        assert tool_args is not None
        return cast(Dict[str, Any], self.tool_executor.execute(
            tool_name=tool_name,
            tool_input=tool_args,
            context=context,
        ))

    def _collect_qr_images(self, tool_calls: List[Dict[str, Any]]) -> List[str]:
        """用于保留统一扩展点，后续如有二维码结果可在这里汇总。"""
        return []


__all__ = ["ResumeAgent"]
