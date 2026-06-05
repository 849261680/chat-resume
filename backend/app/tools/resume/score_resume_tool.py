"""用于把简历评分暴露为简历 Agent 只读工具。"""

from __future__ import annotations

from typing import Any


def score_resume_tool(resume_content: dict[str, Any]) -> dict[str, Any]:
    """用于基于当前简历内容生成确定性评分结果，只读不改简历。"""
    from app.services.agent.resume_score import score_resume

    return score_resume(resume_content)


__all__ = ["score_resume_tool"]
