"""用于封装简历优化 Agent 的业务入口。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.prompts import load_prompt
from app.runtime.loop import AgentDefinition, AgentRuntime
from app.tools.resume.registry import RESUME_TOOLS_SCHEMA

from .executor import TOOL_REQUIRED_ARGS, ResumeToolExecutor
from .prompt_context import build_resume_prompt_context, strip_redundant_fields

logger = logging.getLogger(__name__)

_TOOLS_WITH_OPTIONAL_ARGS_ONLY = {"read_user_memory"}
_AUTO_EXECUTE_TOOL_NAMES = {
    "read_user_memory",
    "write_user_memory",
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


class ResumeAgent:
    """用于组合提示词、运行时和工具执行器，形成完整简历 Agent。"""

    def __init__(self):
        """用于初始化简历 Agent 运行所需的固定依赖。"""
        self.tool_executor = ResumeToolExecutor()
        self.prompt_spec = load_prompt("resume_agent")
        self.runtime = AgentRuntime()
        self.definition = AgentDefinition(
            prompt_spec=self.prompt_spec,
            tools_schema=RESUME_TOOLS_SCHEMA,
            tool_executor=self._run_tool,
            prompt_context_builder=build_resume_prompt_context,
            max_iterations=6,
            auto_execute_tool_names=_AUTO_EXECUTE_TOOL_NAMES,
        )

    async def optimize(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        allowed_sections: Optional[set[str]] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """用于执行一次非流式简历优化请求。"""
        runtime_result = await self.runtime.run(
            agent=self.definition,
            user_message=user_message,
            context={
                "resume_content": resume_content,
                "allowed_sections": allowed_sections,
                "user_id": user_id,
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
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """用于执行一次带工具确认能力的流式简历优化请求。"""
        context = {
            "resume_content": resume_content,
            "allowed_sections": allowed_sections,
            "user_id": user_id,
        }
        async for event in self.runtime.run_stream(
            agent=self.definition,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            confirmation_queue=confirmation_queue,
            event_callback=event_callback,
        ):
            yield {
                "content": event.get("content", ""),
                "qr_images": event.get("qr_images", []),
                "tool_calls": event.get("tool_calls", []),
                "resume_content": context.get("resume_content")
                if event.get("context") is not None
                else None,
                "tool_pending": event.get("tool_pending"),
                "tool_confirmed": event.get("tool_confirmed"),
                "tool_rejected": event.get("tool_rejected"),
                "tool_call_failed": event.get("tool_call_failed"),
                "call_id": event.get("call_id"),
                "tool_call": event.get("tool_call"),
                "tool_name": event.get("tool_name"),
                "tool_input": event.get("tool_input"),
                "diff_summary": event.get("diff_summary"),
                "diff_items": event.get("diff_items"),
                "result": event.get("result"),
                "display_message": event.get("display_message"),
                "internal_only": event.get("internal_only"),
                "prompt_rendered": event.get("prompt_rendered"),
                "llm_request": event.get("llm_request"),
                "llm_response": event.get("llm_response"),
                "agent_name": event.get("agent_name"),
                "system_prompt": event.get("system_prompt"),
                "user_message_preview": event.get("user_message_preview"),
                "model": event.get("model"),
                "messages": event.get("messages"),
                "params": event.get("params"),
                "tool_names": event.get("tool_names"),
                "response_content": event.get("response_content"),
                "latency_ms": event.get("latency_ms"),
                "tool_call_count": event.get("tool_call_count"),
                "done": event.get("done", False),
            }

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

        if tool_name == "update_overview" and not tool_args.get("section"):
            tool_args["section"] = "projects"

        required = TOOL_REQUIRED_ARGS.get(tool_name)
        if required is None and tool_name not in _TOOLS_WITH_OPTIONAL_ARGS_ONLY:
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
        logger.debug("[tool_call] %s raw_args=%r", tool_name, raw_args)
        tool_args, error_result = self._prepare_tool_args(tool_name, raw_args)
        if error_result is not None:
            return error_result
        assert tool_args is not None
        return self.tool_executor.execute(
            tool_name=tool_name,
            tool_input=tool_args,
            context=context,
        )

    def _collect_qr_images(self, tool_calls: List[Dict[str, Any]]) -> List[str]:
        """用于保留统一扩展点，后续如有二维码结果可在这里汇总。"""
        return []


__all__ = ["ResumeAgent"]
