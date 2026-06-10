"""用于把候选人长期背景整理成简历 Agent 可读上下文。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.tools.resume.memory_tool import MemoryEntry, MemoryMarkdownStore

logger = logging.getLogger(__name__)

_MISSING_PROFILE_FIELDS = (
    "目标岗位/投递方向",
    "候选人定位",
    "核心技能/技术栈",
    "项目经历证据",
)
_KIND_LABELS = {
    "target_strategy": "目标策略",
    "fact_constraint": "事实约束",
    "preference": "表达偏好",
}


@dataclass(frozen=True)
class CandidateProfileContext:
    """用于表达系统提示词中的候选人背景档案。"""

    markdown: str
    has_entries: bool


def load_candidate_profile_context(
    *,
    user_id: int | None,
    resume_id: int | None,
    memory_dir: str | None = None,
) -> CandidateProfileContext:
    """用于读取用户级和简历级记忆并生成候选人背景档案。"""
    if user_id is None:
        return _empty_profile_context()

    store = MemoryMarkdownStore(memory_dir=memory_dir, user_id=user_id)
    entries = _read_profile_entries(store, resume_id=resume_id)
    if not entries:
        return _empty_profile_context()
    return CandidateProfileContext(
        markdown=_format_profile_entries(entries),
        has_entries=True,
    )


def _read_profile_entries(
    store: MemoryMarkdownStore,
    *,
    resume_id: int | None,
) -> list[MemoryEntry]:
    """用于容错读取当前用户和当前简历相关的背景记忆。"""
    entries = list(store.read(scope="user"))
    if resume_id is None:
        return entries
    try:
        return [*entries, *store.read(scope="resume", resume_id=resume_id)]
    except ValueError:
        logger.warning("candidate_profile.resume_memory_read_failed")
        return entries


def _empty_profile_context() -> CandidateProfileContext:
    """用于生成未建立背景档案时的提示词占位。"""
    missing = "、".join(_MISSING_PROFILE_FIELDS)
    return CandidateProfileContext(
        markdown=(
            "候选人背景档案尚未建立。\n"
            f"缺失关键信息：{missing}。\n"
            "如果用户要求优化、改写或面向岗位定制简历，先提出最多 3 个关键问题。"
        ),
        has_entries=False,
    )


def _format_profile_entries(entries: list[MemoryEntry]) -> str:
    """用于把记忆条目渲染成紧凑 Markdown 列表。"""
    lines = ["候选人背景档案已建立，以下内容优先于模型猜测："]
    for entry in entries[:12]:
        label = _KIND_LABELS.get(entry.kind, entry.kind or "背景")
        scope = "当前简历" if entry.scope.startswith("resume:") else "用户"
        lines.append(f"- [{scope}/{label}] {entry.content}")
    lines.append("缺失或不确定的信息必须向用户追问，不得自行补全。")
    return "\n".join(lines)


__all__ = ["CandidateProfileContext", "load_candidate_profile_context"]
