"""用于封装简历优化 Agent 的业务入口。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, cast

from app.prompts import load_prompt
from app.runtime.contracts import AgentDefinition
from app.tools.resume.registry import (
    RESUME_AUTO_EXECUTE_TOOL_NAMES,
    RESUME_TOOL_PROFILES,
    RESUME_TOOLS_SCHEMA,
    execute_resume_tool_call,
)
from app.types.stream import ResumeStreamEvent

from .candidate_profile import load_candidate_profile_context
from .prompt_context import build_resume_prompt_context, strip_redundant_fields
from .runtime import ResumeAgentRuntime
from .stream_events import normalize_resume_stream_payload

logger = logging.getLogger(__name__)

_LOG_VALUE_LIMIT = 64


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


class ResumeAgent:
    """用于组合提示词、运行时和工具执行器，形成完整简历 Agent。"""

    def __init__(self):
        """用于初始化简历 Agent 运行所需的固定依赖。"""
        self.prompt_spec = load_prompt("resume_agent")
        self.runtime: Any = ResumeAgentRuntime()
        self.definition = AgentDefinition(
            prompt_spec=self.prompt_spec,
            tools_schema=RESUME_TOOLS_SCHEMA,
            tool_executor=self._run_tool,
            prompt_context_builder=build_resume_prompt_context,
            auto_execute_tool_names=RESUME_AUTO_EXECUTE_TOOL_NAMES,
            default_tool_profile="resume_edit",
            tool_profiles=RESUME_TOOL_PROFILES,
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
        return cast(
            Dict[str, Any],
            execute_resume_tool_call(
                tool_name=tool_name,
                raw_arguments=raw_args,
                context=context,
            ),
        )

    def _collect_qr_images(self, tool_calls: List[Dict[str, Any]]) -> List[str]:
        """用于保留统一扩展点，后续如有二维码结果可在这里汇总。"""
        return []


__all__ = ["ResumeAgent"]
