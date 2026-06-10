"""用于表达简历 Agent 的业务会话状态和上下文摘要。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.schemas.resume import dump_resume_content_for_frontend

_DEFAULT_SUMMARY_THRESHOLD_CHARS = 12000
_TEXT_LIMIT = 220


@dataclass(slots=True)
class ResumeContextSummary:
    """用于保存可复用的简历上下文压缩结果。"""

    enabled: bool
    resume_snapshot: dict[str, Any]
    confirmed_changes: list[str] = field(default_factory=list)
    recent_messages: list[dict[str, str]] = field(default_factory=list)
    jd_text: str = ""

    def to_prompt_payload(self) -> dict[str, Any]:
        """用于把摘要转换成提示词可读 JSON。"""
        return {
            "summary_mode": self.enabled,
            "resume_snapshot": self.resume_snapshot,
            "confirmed_changes": self.confirmed_changes,
            "recent_messages": self.recent_messages,
            "jd_text": self.jd_text,
        }


@dataclass(slots=True)
class ResumeAgentModelConfig:
    """用于记录一轮 Resume Agent 调用的模型与工具配置。"""

    model: str
    tool_profile: str
    tool_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ResumeAgentSession:
    """用于重建业务版 Resume Agent 会话状态。"""

    transcript: list[dict[str, str]] = field(default_factory=list)
    model_config: ResumeAgentModelConfig | None = None
    pending_tool_call: dict[str, Any] | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    context_summary: ResumeContextSummary | None = None

    def to_conversation_history(self) -> list[dict[str, str]]:
        """用于返回下一轮 LLM 可复用的 user/assistant transcript。"""
        return [
            item
            for item in self.transcript
            if item.get("role") in {"user", "assistant"} and item.get("content")
        ]

    @classmethod
    def from_events(
        cls,
        events: Iterable[Any],
        *,
        resume_content: dict[str, Any] | None = None,
    ) -> "ResumeAgentSession":
        """用于从持久化事件重建下一轮所需的最小业务状态。"""
        session = cls()
        confirmed_diff_items: list[dict[str, Any]] = []
        for event in events:
            event_type = str(getattr(event, "event_type", ""))
            payload = getattr(event, "payload", {}) or {}
            if event_type == "user_message":
                content = str(payload.get("content") or "")
                session.transcript.append({"role": "user", "content": content})
            elif event_type == "agent_response":
                content = str(payload.get("content") or "")
                session.transcript.append({"role": "assistant", "content": content})
            elif event_type == "tool_call_previewed":
                session.pending_tool_call = payload.get("tool_call")
            elif event_type == "tool_call_confirmed":
                confirmed_diff_items.extend(_payload_diff_items(payload))
            elif event_type == "stream_event":
                _apply_stream_metadata(session, payload)

        if resume_content is not None:
            session.context_summary = build_resume_context_summary(
                resume_content=resume_content,
                confirmed_diff_items=confirmed_diff_items,
                conversation_history=session.to_conversation_history(),
                force=True,
            )
        return session


def maybe_compact_resume_context(
    *,
    resume_content: dict[str, Any],
    confirmed_diff_items: list[dict[str, Any]] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    threshold_chars: int = _DEFAULT_SUMMARY_THRESHOLD_CHARS,
) -> dict[str, Any]:
    """用于在长上下文超过阈值时返回摘要 JSON，短上下文保持原样。"""
    frontend_content = dump_resume_content_for_frontend(resume_content)
    rendered = json.dumps(frontend_content, ensure_ascii=False, indent=2)
    history_chars = sum(len(str(item.get("content") or "")) for item in conversation_history or [])
    if len(rendered) + history_chars <= threshold_chars:
        return frontend_content
    summary = build_resume_context_summary(
        resume_content=frontend_content,
        confirmed_diff_items=confirmed_diff_items or [],
        conversation_history=conversation_history or [],
        force=True,
    )
    return summary.to_prompt_payload()


def build_resume_context_summary(
    *,
    resume_content: dict[str, Any],
    confirmed_diff_items: list[dict[str, Any]],
    conversation_history: list[dict[str, str]],
    force: bool = False,
) -> ResumeContextSummary:
    """用于生成包含关键事实、JD 和已确认 diff 的简历摘要。"""
    frontend_content = dump_resume_content_for_frontend(resume_content)
    job_application = frontend_content.get("job_application", {})
    jd_text = ""
    if isinstance(job_application, dict):
        jd_text = _preview(job_application.get("jd_text"), limit=1200)
    snapshot = {
        "profile": _section_summary(frontend_content, "profile"),
        "work_experience": _list_section_summary(frontend_content, "work_experience"),
        "projects": _list_section_summary(frontend_content, "projects"),
        "open_source": _list_section_summary(frontend_content, "open_source"),
        "education": _list_section_summary(frontend_content, "education"),
        "job_application": {
            "target_title": str(job_application.get("target_title") or "")
            if isinstance(job_application, dict)
            else "",
            "target_company": str(job_application.get("target_company") or "")
            if isinstance(job_application, dict)
            else "",
        },
    }
    return ResumeContextSummary(
        enabled=force,
        resume_snapshot=snapshot,
        confirmed_changes=_confirmed_change_summaries(confirmed_diff_items),
        recent_messages=_recent_messages(conversation_history),
        jd_text=jd_text,
    )


def _apply_stream_metadata(session: ResumeAgentSession, payload: dict[str, Any]) -> None:
    """用于从公开 runtime 事件提取模型配置和 usage。"""
    if payload.get("event_type") == "llm_request":
        tool_names = [str(name) for name in payload.get("tool_names", []) if name]
        session.model_config = ResumeAgentModelConfig(
            model=str(payload.get("model") or ""),
            tool_profile=str(payload.get("tool_profile") or ""),
            tool_names=tool_names,
        )
    if payload.get("event_type") == "llm_response" and isinstance(payload.get("usage"), dict):
        session.usage = dict(payload["usage"])


def _payload_diff_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """用于从确认事件载荷中读取 diff 列表。"""
    diff_items = payload.get("diff_items")
    if not isinstance(diff_items, list):
        return []
    return [item for item in diff_items if isinstance(item, dict)]


def _section_summary(content: dict[str, Any], section: str) -> Any:
    """用于读取单对象 section 的摘要。"""
    value = content.get(section)
    if isinstance(value, dict):
        return {str(key): _preview(item) for key, item in value.items()}
    return value


def _list_section_summary(content: dict[str, Any], section: str) -> list[dict[str, Any]]:
    """用于压缩列表型简历 section，同时保留 id 与关键文本。"""
    items = content.get(section)
    if not isinstance(items, list):
        return []
    summaries: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        highlights = item.get("highlights")
        summaries.append(
            {
                "id": item.get("id"),
                "name": item.get("name") or item.get("company") or item.get("school"),
                "title": item.get("title") or item.get("position") or item.get("degree"),
                "summary": _preview(item.get("summary") or item.get("overview")),
                "highlights": _highlight_summaries(highlights),
            }
        )
    return summaries


def _highlight_summaries(highlights: Any) -> list[dict[str, str]]:
    """用于保留 highlights 的 id 和短文本。"""
    if not isinstance(highlights, list):
        return []
    summaries: list[dict[str, str]] = []
    for item in highlights[:12]:
        if isinstance(item, dict):
            summaries.append(
                {
                    "id": str(item.get("id") or ""),
                    "text": _preview(item.get("text")),
                }
            )
    return summaries


def _confirmed_change_summaries(diff_items: list[dict[str, Any]]) -> list[str]:
    """用于把已确认 diff 压缩成可放回上下文的短句。"""
    summaries: list[str] = []
    for item in diff_items[-12:]:
        before = _preview(item.get("before"), limit=80)
        after = _preview(item.get("after"), limit=120)
        reason = _preview(item.get("reason"), limit=60)
        summaries.append(f"{before} -> {after}; reason={reason}")
    return summaries


def _recent_messages(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """用于截取最近几轮对话作为摘要补充。"""
    recent: list[dict[str, str]] = []
    for item in history[-6:]:
        role = str(item.get("role") or "")
        if role not in {"user", "assistant"}:
            continue
        recent.append({"role": role, "content": _preview(item.get("content"), limit=300)})
    return recent


def _preview(value: Any, *, limit: int = _TEXT_LIMIT) -> str:
    """用于生成稳定短文本。"""
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


__all__ = [
    "ResumeAgentModelConfig",
    "ResumeAgentSession",
    "ResumeContextSummary",
    "build_resume_context_summary",
    "maybe_compact_resume_context",
]
