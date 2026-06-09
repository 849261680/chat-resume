"""用于编排简历规则评分、语义评审和优先动作。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .resume_rule_score import grade_score, score_resume_rules
from .resume_semantic_review import review_resume_semantics

SemanticReviewer = Callable[[dict[str, Any], list[dict[str, Any]]], dict[str, Any]]


def score_resume(
    resume_content: dict[str, Any],
    *,
    semantic_reviewer: SemanticReviewer = review_resume_semantics,
    score_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """用于计算整份简历的规则分、语义评审、总分和可执行修改建议。"""
    rule_checks = score_resume_rules(resume_content)
    semantic_review = _safe_semantic_review(
        semantic_reviewer, resume_content, rule_checks["dimensions"]
    )
    total = _calibrated_total(rule_checks["score"], semantic_review)
    priority_actions = _merge_priority_actions(rule_checks, semantic_review)
    convergence = _assess_convergence(total, score_history, priority_actions)
    return {
        "success": True,
        "message": _score_message(total, convergence),
        "total_score": total,
        "grade": grade_score(total),
        "rule_checks": rule_checks,
        "semantic_review": semantic_review,
        "diagnosis": _build_diagnosis(total, rule_checks, semantic_review),
        "convergence": convergence,
        "dimensions": rule_checks["dimensions"],
        "top_suggestions": rule_checks["top_suggestions"],
        "priority_actions": priority_actions,
        "agent_next_step": _agent_next_step(priority_actions, convergence),
    }


def _safe_semantic_review(
    semantic_reviewer: SemanticReviewer,
    resume_content: dict[str, Any],
    rule_dimensions: list[dict[str, Any]],
) -> dict[str, Any]:
    """用于捕获语义评审异常并降级为规则评分。"""
    try:
        return semantic_reviewer(resume_content, rule_dimensions)
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": str(exc),
            "score": None,
        }


def _calibrated_total(rule_score: int, semantic_review: dict[str, Any]) -> int:
    """用于把规则分和语义分合并为最终总分。"""
    semantic_score = _semantic_score(semantic_review)
    if semantic_score is None:
        return rule_score
    return round(rule_score * 0.4 + semantic_score * 0.6)


def _semantic_score(semantic_review: dict[str, Any]) -> int | None:
    """用于从语义评审结构中读取可用分数。"""
    overall = semantic_review.get("overall")
    if isinstance(overall, dict) and isinstance(overall.get("score"), int):
        return int(overall["score"])
    return None


def _merge_priority_actions(
    rule_checks: dict[str, Any], semantic_review: dict[str, Any]
) -> list[dict[str, Any]]:
    """用于统一合并规则建议和语义建议。"""
    semantic_actions = semantic_review.get("priority_actions")
    if not isinstance(semantic_actions, list):
        semantic_actions = []
    actions = [*_valid_actions(semantic_actions), *_valid_actions(rule_checks["priority_actions"])]
    return _dedupe_actions(actions)[:6]


def _valid_actions(actions: list[Any]) -> list[dict[str, Any]]:
    """用于过滤非字典动作，避免 provider 异常污染输出。"""
    return [action for action in actions if isinstance(action, dict)]


def _dedupe_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用于按目标和原因去重优先动作。"""
    seen: set[tuple[str, str, str]] = set()
    result = []
    for action in actions:
        key = _action_key(action)
        if key not in seen:
            seen.add(key)
            result.append(action)
    return result


def _action_key(action: dict[str, Any]) -> tuple[str, str, str]:
    """用于生成 priority action 的稳定去重键。"""
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    item_id = str(target.get("item_id", ""))
    bullet_id = str(target.get("bullet_id", ""))
    return item_id, bullet_id, str(action.get("reason", ""))


def _build_diagnosis(
    total: int, rule_checks: dict[str, Any], semantic_review: dict[str, Any]
) -> dict[str, Any]:
    """用于生成面向 Agent 解释和决策的结构化诊断摘要。"""
    primary = _primary_risk(rule_checks, semantic_review)
    return {
        "verdict": _verdict(total, primary),
        "risk_level": _risk_level(total),
        "primary_risk": primary,
        "evidence": _collect_evidence(rule_checks, semantic_review),
    }


def _primary_risk(
    rule_checks: dict[str, Any], semantic_review: dict[str, Any]
) -> dict[str, Any]:
    """用于优先从语义评审中找主风险，语义不可用时回退规则短板。"""
    semantic_risk = _semantic_primary_risk(semantic_review)
    if semantic_risk:
        return semantic_risk
    return _rule_primary_risk(rule_checks["dimensions"])


def _semantic_primary_risk(semantic_review: dict[str, Any]) -> dict[str, Any]:
    """用于从语义维度中找最低分风险。"""
    dimensions = semantic_review.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        return {}
    weakest = min(_valid_actions(dimensions), key=lambda item: item.get("score", 100))
    return {
        "dimension_key": str(weakest.get("key", "semantic_review")),
        "dimension_name": "语义评审",
        "score": weakest.get("score"),
        "max": 100,
        "reason": str(weakest.get("evidence", "")),
    }


def _rule_primary_risk(scored: list[dict[str, Any]]) -> dict[str, Any]:
    """用于找出规则评分中相对得分最低的维度。"""
    if not scored:
        return {}
    weakest = min(scored, key=lambda item: item["score"] / (item["max"] or 1))
    return {
        "dimension_key": weakest["key"],
        "dimension_name": weakest["name"],
        "score": weakest["score"],
        "max": weakest["max"],
        "reason": _rule_dimension_reason(weakest),
    }


def _rule_dimension_reason(dimension: dict[str, Any]) -> str:
    """用于把规则 findings 压缩成一句主风险原因。"""
    first = (dimension.get("findings") or [{}])[0]
    if first.get("issue"):
        return str(first["issue"])
    return f"{dimension['name']}当前没有明显扣分项。"


def _collect_evidence(
    rule_checks: dict[str, Any], semantic_review: dict[str, Any]
) -> list[dict[str, Any]]:
    """用于汇总规则证据和语义证据。"""
    evidence = _semantic_evidence(semantic_review)
    evidence.extend(_rule_evidence(rule_checks["dimensions"]))
    return evidence[:10]


def _semantic_evidence(semantic_review: dict[str, Any]) -> list[dict[str, Any]]:
    """用于把语义维度转成诊断证据。"""
    dimensions = semantic_review.get("dimensions")
    if not isinstance(dimensions, list):
        return []
    return [
        {
            "source": "semantic_review",
            "dimension_key": str(item.get("key", "")),
            "dimension_name": "语义评审",
            "issue": str(item.get("evidence", "")),
            "suggestion": str(item.get("suggestion", "")),
            "target": {},
        }
        for item in _valid_actions(dimensions)
    ]


def _rule_evidence(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用于把规则 findings 转成诊断证据。"""
    evidence: list[dict[str, Any]] = []
    for dimension in scored:
        evidence.extend(_rule_finding_evidence(dimension))
        if not dimension["findings"]:
            evidence.append(_rule_strength_evidence(dimension))
    return evidence


def _rule_finding_evidence(dimension: dict[str, Any]) -> list[dict[str, Any]]:
    """用于把单个规则维度的 finding 转成诊断证据。"""
    return [
        {
            "source": "rule_checks",
            "dimension_key": dimension["key"],
            "dimension_name": dimension["name"],
            "issue": finding["issue"],
            "suggestion": finding["suggestion"],
            "target": _finding_target(finding),
        }
        for finding in dimension["findings"][:3]
    ]


def _rule_strength_evidence(dimension: dict[str, Any]) -> dict[str, Any]:
    """用于生成无扣分规则维度的正向证据。"""
    return {
        "source": "rule_checks",
        "dimension_key": dimension["key"],
        "dimension_name": dimension["name"],
        "issue": "该维度暂无明显短板",
        "suggestion": "保持当前写法，优先处理其他低分维度",
        "target": {},
    }


def _finding_target(finding: dict[str, Any]) -> dict[str, str]:
    """用于从 finding 中提取可编辑的 item/bullet 定位信息。"""
    item_id = str(finding.get("item_id") or "")
    bullet_id = str(finding.get("bullet_id") or "")
    if item_id and bullet_id:
        return {"item_id": item_id, "bullet_id": bullet_id}
    return {}


def _risk_level(total: int) -> str:
    """用于把总分转成便于 UI 或 Agent 展示的风险等级。"""
    if total >= 85:
        return "low"
    if total >= 70:
        return "medium"
    return "high"


def _verdict(total: int, primary: dict[str, Any]) -> str:
    """用于生成一句简短的总体判断。"""
    if total >= 85:
        return "简历基础质量较好，建议围绕最低分维度做小幅增强。"
    name = primary.get("dimension_name") or "核心维度"
    return f"当前最大短板是{name}，应先处理证据最明确、可直接编辑的经历要点。"


def _agent_next_step(
    priority_actions: list[dict[str, Any]],
    convergence: dict[str, Any] | None = None,
) -> str:
    """用于根据是否存在优先动作和收敛状态生成 Agent 复评提示。"""
    if convergence and convergence.get("should_stop"):
        return convergence.get("stop_reason", "简历已达到当前优化天花板。")
    if not priority_actions:
        return "当前没有明确扣分动作；可询问用户目标岗位或新的 JD，然后再次调用 score_resume 复评。"
    return (
        "先处理 priority_actions[0] 指向的最高优先级问题；如果包含 "
        "item_id/bullet_id，调用对应编辑工具更新该 bullet，然后再次调用 "
        "score_resume 复评。"
    )


def _assess_convergence(
    current_score: int,
    score_history: list[dict[str, Any]] | None,
    priority_actions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """用于评估分数收敛状态，返回 None 表示首次评分无历史可比。"""
    if not score_history:
        return None
    previous_scores = [
        snap["total_score"]
        for snap in score_history
        if isinstance(snap.get("total_score"), (int, float))
    ]
    if not previous_scores:
        return None
    initial_score = previous_scores[0]
    last_score = previous_scores[-1]
    improvement_from_last = current_score - last_score
    total_improvement = current_score - initial_score
    # 收敛判断：达到目标分数
    if current_score >= 85:
        return {
            "status": "converged",
            "should_stop": True,
            "stop_reason": f"总分 {current_score} 已达到优秀水平（≥85），优化完成。",
            "initial_score": initial_score,
            "last_score": last_score,
            "current_score": current_score,
            "total_improvement": total_improvement,
            "rounds": len(previous_scores) + 1,
        }
    # 收敛判断：连续两轮无提升
    if improvement_from_last <= 0 and len(previous_scores) >= 1:
        # 再检查倒数第二轮
        if len(previous_scores) >= 2 and previous_scores[-1] <= previous_scores[-2]:
            return {
                "status": "plateaued",
                "should_stop": True,
                "stop_reason": (
                    f"连续 2 轮评分无提升（{previous_scores[-2]}→{previous_scores[-1]}→{current_score}），"
                    f"已达当前内容天花板。"
                ),
                "initial_score": initial_score,
                "last_score": last_score,
                "current_score": current_score,
                "total_improvement": total_improvement,
                "rounds": len(previous_scores) + 1,
            }
    # 收敛判断：无更多可改项
    if not priority_actions:
        return {
            "status": "no_actions",
            "should_stop": True,
            "stop_reason": "所有可检测问题已处理完毕，无需继续优化。",
            "initial_score": initial_score,
            "last_score": last_score,
            "current_score": current_score,
            "total_improvement": total_improvement,
            "rounds": len(previous_scores) + 1,
        }
    # 仍在进步中
    return {
        "status": "improving",
        "should_stop": False,
        "stop_reason": "",
        "initial_score": initial_score,
        "last_score": last_score,
        "current_score": current_score,
        "total_improvement": total_improvement,
        "rounds": len(previous_scores) + 1,
    }


def _score_message(total: int, convergence: dict[str, Any] | None) -> str:
    """用于生成面向用户的评分结果描述。"""
    if convergence and convergence.get("should_stop"):
        return convergence.get("stop_reason", "已完成简历评分。")
    return f"已完成简历评分，当前 {total} 分。"
