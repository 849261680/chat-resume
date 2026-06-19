"""用于统一简历评分、最终质量门禁和轨迹评测判断。"""

from __future__ import annotations

from typing import Any

from app.agents.resume.excellent_trajectory import evaluate_excellent_resume_trajectory
from app.agents.resume.final_resume_quality import score_final_resume_quality
from app.services.agent.resume_score import (
    AsyncSemanticReviewer,
    SemanticReviewer,
    score_resume,
)
from app.services.agent.resume_semantic_review import review_resume_semantics


async def judge_resume_quality(
    *,
    resume_before: dict[str, Any],
    resume_after: dict[str, Any],
    jd_text: str = "",
    user_message: str = "",
    trajectory: dict[str, Any] | None = None,
    trajectory_case: dict[str, Any] | None = None,
    async_semantic_reviewer: AsyncSemanticReviewer | None = None,
    fallback_semantic_reviewer: SemanticReviewer = review_resume_semantics,
    score_history: list[dict[str, Any]] | None = None,
    final_applicable: bool = True,
) -> dict[str, Any]:
    """用于返回 AGENT 是否把简历改好的统一判断。"""
    resume_score = await score_resume(
        resume_after,
        async_semantic_reviewer=async_semantic_reviewer,
        fallback_semantic_reviewer=fallback_semantic_reviewer,
        score_history=score_history,
    )
    final_quality = score_final_resume_quality(
        resume_before=resume_before,
        resume_after=resume_after,
        jd_text=jd_text,
        user_message=user_message,
        applicable=final_applicable,
    )
    trajectory_quality = _trajectory_quality(
        trajectory=trajectory,
        trajectory_case=trajectory_case,
    )
    failure_codes = _failure_codes(
        final_quality=final_quality,
        trajectory_quality=trajectory_quality,
    )
    return {
        "success": True,
        "passed": not failure_codes,
        "overall_score": _overall_score(resume_score, final_quality),
        "threshold": final_quality.get("threshold"),
        "level": final_quality.get("level") or resume_score.get("grade"),
        "failure_codes": failure_codes,
        "evidence": _evidence(resume_score, final_quality, trajectory_quality),
        "priority_actions": resume_score.get("priority_actions", []),
        "agent_next_step": resume_score.get("agent_next_step", ""),
        "layers": {
            "resume_score": resume_score,
            "final_resume_quality": final_quality,
            "trajectory": trajectory_quality,
        },
    }


def _trajectory_quality(
    *,
    trajectory: dict[str, Any] | None,
    trajectory_case: dict[str, Any] | None,
) -> dict[str, Any]:
    """用于在有黄金样例时执行轨迹评测。"""
    if trajectory is None or trajectory_case is None:
        return {"applicable": False, "passed": True, "failure_codes": []}
    result = evaluate_excellent_resume_trajectory(
        case=trajectory_case,
        trajectory=trajectory,
    )
    return {"applicable": True, **result}


def _failure_codes(
    *,
    final_quality: dict[str, Any],
    trajectory_quality: dict[str, Any],
) -> list[str]:
    """用于把各层失败代码统一加来源前缀。"""
    failures = [
        f"final_resume_quality:{code}"
        for code in _string_items(final_quality.get("failure_codes"))
    ]
    failures.extend(
        f"trajectory:{code}"
        for code in _string_items(trajectory_quality.get("failure_codes"))
    )
    return failures


def _overall_score(
    resume_score: dict[str, Any],
    final_quality: dict[str, Any],
) -> int | float | None:
    """用于优先返回最终质量分，缺失时回退整份简历评分。"""
    final_score = final_quality.get("score")
    if isinstance(final_score, int | float):
        return final_score
    score = resume_score.get("total_score")
    return score if isinstance(score, int | float) else None


def _evidence(
    resume_score: dict[str, Any],
    final_quality: dict[str, Any],
    trajectory_quality: dict[str, Any],
) -> list[dict[str, Any]]:
    """用于把规则/语义、事实检查和轨迹证据合并成统一证据列表。"""
    evidence = _diagnosis_evidence(resume_score)
    unsupported = final_quality.get("fact_check", {}).get("unsupported_claims", [])
    evidence.extend(
        {"source": "final_resume_quality", "issue": str(item), "suggestion": "移除或补充事实来源", "target": {}}
        for item in unsupported
    )
    evidence.extend(
        {"source": "trajectory", "issue": code, "suggestion": "修正 Agent 工具轨迹", "target": {}}
        for code in _string_items(trajectory_quality.get("failure_codes"))
    )
    return evidence[:12]


def _diagnosis_evidence(resume_score: dict[str, Any]) -> list[dict[str, Any]]:
    """用于从整份简历评分中读取诊断证据。"""
    diagnosis = resume_score.get("diagnosis")
    if not isinstance(diagnosis, dict):
        return []
    evidence = diagnosis.get("evidence")
    if not isinstance(evidence, list):
        return []
    return [item for item in evidence if isinstance(item, dict)]


def _string_items(value: Any) -> list[str]:
    """用于把未知列表过滤成字符串列表。"""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


__all__ = ["judge_resume_quality"]
