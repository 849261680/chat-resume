"""用于承接 Resume Agent 单次运行的事件、追踪和摘要生命周期。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any

from app.agents.resume.event_publisher import (
    emit_resume_runtime_event,
    publish_resume_runtime_event,
)
from app.agents.resume.stream_events import llm_response_event, prompt_rendered_event
from app.agents.resume.tool_execution import ResumeToolExecutionStage
from app.infra.config import settings
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.types.stream import ResumeStreamEvent

logger = logging.getLogger("app.agents.resume.runtime")


class ResumeRunLifecycle:
    """用于管理 Resume Agent run 的可见事件、trace 和结构化摘要。"""

    def __init__(self, model_name_provider: Callable[[], str]):
        """用于保存当前运行时的模型名称来源。"""
        self.model_name_provider = model_name_provider

    @staticmethod
    def new_stream_state() -> dict[str, Any]:
        """用于创建单次运行的流式状态容器。"""
        return {
            "started_at": perf_counter(),
            "chunk_index": 0,
            "response_parts": [],
            "last_assistant_text": "",
            "confirmed_diff_items": [],
            "tool_profile": "",
            "tool_names": [],
            "visible_tool_call_ids": set(),
            "unexpected_tool_call_names": set(),
            "prompt_chars": 0,
            "message_count": 0,
            "tool_count": 0,
            "provider": "",
            "model": "",
            "tool_call_count": 0,
            "tool_requested_count": 0,
            "tool_executed_count": 0,
            "tool_confirmed_count": 0,
            "tool_rejected_count": 0,
            "guardrail_rejected_count": 0,
            "first_token_latency_ms": None,
            "llm_total_ms": 0.0,
            "usage": {},
            "confirmation_wait_ms": 0.0,
            "mutation_claim_retry_count": 0,
        }

    def llm_response_event(
        self,
        agent: AgentDefinition,
        state: dict[str, Any],
    ) -> ResumeStreamEvent:
        """用于生成模型响应完成事件。"""
        return llm_response_event(
            agent_name=agent.prompt_spec.name,
            model=self.model_name_provider(),
            response_content="".join(state["response_parts"]),
            tool_call_count=int(state.get("tool_call_count") or 0),
            latency_ms=round((perf_counter() - state["started_at"]) * 1000, 2),
            first_token_latency_ms=state.get("first_token_latency_ms"),
            usage=state.get("usage") if isinstance(state.get("usage"), dict) else {},
            confirmation_wait_ms=float(state.get("confirmation_wait_ms") or 0.0),
        )

    @staticmethod
    def prompt_rendered_event(
        agent: AgentDefinition,
        system_prompt: str,
        user_message: str,
    ) -> ResumeStreamEvent:
        """用于生成提示词渲染完成事件。"""
        return prompt_rendered_event(
            agent_name=agent.prompt_spec.name,
            system_prompt=system_prompt,
            user_message_preview=str(user_message)[:1500],
        )

    def trace_run_start(
        self,
        agent: AgentDefinition,
        run_id: str,
        mode: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None,
    ) -> None:
        """用于记录 run 开始 trace。"""
        self.trace(
            "agent.trace.run.started",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode=mode,
            user_message_preview=self.preview_text(user_message),
            history_count=len(conversation_history or []),
            tool_names=list(agent.tool_profiles.get(agent.default_tool_profile, set())),
        )

    def trace_prompt(
        self,
        agent: AgentDefinition,
        run_id: str,
        system_prompt: str,
    ) -> None:
        """用于记录 prompt 渲染 trace。"""
        self.trace(
            "agent.trace.prompt.rendered",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            prompt_chars=len(system_prompt),
        )

    def trace_llm_response(
        self,
        agent: AgentDefinition,
        run_id: str,
        event: ResumeStreamEvent,
    ) -> None:
        """用于记录模型响应 trace。"""
        self.trace(
            "agent.trace.llm.response",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            model=self.model_name_provider(),
            response_preview=self.preview_text(event.get("response_content")),
            response_chars=len(str(event.get("response_content") or "")),
            latency_ms=event.get("latency_ms"),
            first_token_latency_ms=event.get("first_token_latency_ms"),
            usage=event.get("usage"),
            confirmation_wait_ms=event.get("confirmation_wait_ms"),
        )

    def trace_run_completed(
        self,
        agent: AgentDefinition,
        run_id: str,
        mode: str,
        state: dict[str, Any],
    ) -> None:
        """用于记录 run 完成 trace。"""
        self.trace(
            "agent.trace.run.completed",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode=mode,
            latency_ms=round((perf_counter() - state["started_at"]) * 1000, 2),
        )

    def log_run_summary(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        mode: str,
        state: dict[str, Any],
        success: bool,
        error_type: str | None,
    ) -> None:
        """用于记录一次 Resume Agent run 的单条结构化摘要。"""
        total_ms = round((perf_counter() - state["started_at"]) * 1000, 2)
        final_status = "completed" if success else "failed"
        error_value = error_type or "-"
        logger.info(
            "resume_agent.run.summary",
            extra={
                "agent_trace": True,
                "agent_name": agent.prompt_spec.name,
                "run_id": run_id,
                "mode": mode,
                "provider": str(state.get("provider") or ""),
                "model": str(state.get("model") or self.model_name_provider()),
                "prompt_chars": int(state.get("prompt_chars") or 0),
                "message_count": int(state.get("message_count") or 0),
                "tool_count": int(state.get("tool_count") or 0),
                "first_token_ms": state.get("first_token_latency_ms"),
                "llm_total_ms": round(float(state.get("llm_total_ms") or 0.0), 2),
                "total_ms": total_ms,
                "tool_requested": int(state.get("tool_requested_count") or 0),
                "tool_executed": int(state.get("tool_executed_count") or 0),
                "tool_confirmed": int(state.get("tool_confirmed_count") or 0),
                "tool_rejected": int(state.get("tool_rejected_count") or 0),
                "approval_wait_ms": round(float(state.get("confirmation_wait_ms") or 0.0), 2),
                "guardrail_rejected": int(state.get("guardrail_rejected_count") or 0),
                "final_status": final_status,
                "error": error_value,
                "tool_call_count": int(state.get("tool_call_count") or 0),
                "confirmation_wait_ms": round(
                    float(state.get("confirmation_wait_ms") or 0.0),
                    2,
                ),
                "elapsed_ms": total_ms,
                "success": success,
                "error_type": error_value,
            },
        )

    @staticmethod
    async def publish_event(
        *,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        event: ResumeStreamEvent,
    ) -> None:
        """用于发布 runtime callback 和 SSE 队列事件。"""
        await publish_resume_runtime_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=event,
        )

    @staticmethod
    def emit_event(
        event_callback: RuntimeEventCallback | None,
        event: ResumeStreamEvent,
    ) -> None:
        """用于向同步调用方发布 runtime 事件。"""
        emit_resume_runtime_event(event_callback, event)

    @staticmethod
    def preview_text(value: Any, limit: int = 240) -> str:
        """用于生成 trace 里的安全文本预览。"""
        return ResumeToolExecutionStage.preview_text(value, limit=limit)

    @staticmethod
    def trace(message: str, **fields: Any) -> None:
        """用于记录受开关控制的结构化 trace。"""
        if not settings.AGENT_TRACE_LOG_ENABLED:
            return
        level = int(fields.pop("log_level", logging.INFO))
        logger.log(level, message, extra={"agent_trace": True, **fields})

    @classmethod
    def trace_chunk(cls, message: str, **fields: Any) -> None:
        """用于在需要排查流式细节时记录单个 chunk。"""
        if not settings.AGENT_TRACE_CHUNK_LOG_ENABLED:
            return
        cls.trace(message, **fields)
