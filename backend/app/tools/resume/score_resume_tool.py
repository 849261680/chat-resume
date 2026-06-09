"""用于把简历评分暴露为简历 Agent 只读工具。"""

from __future__ import annotations

from typing import Any


def score_resume_tool(resume_content: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """用于基于当前简历内容生成规则评分和语义评审，只读不改简历。"""
    from app.services.agent.resume_score import score_resume

    score_history = kwargs.get("score_history")
    return score_resume(
        resume_content,
        score_history=score_history if isinstance(score_history, list) else None,
    )


__all__ = ["score_resume_tool"]
