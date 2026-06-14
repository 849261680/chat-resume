"""定义可在 Braintrust 项目中复用的简历质量 Scorers。"""

from __future__ import annotations

import re
from typing import Any

import braintrust
from pydantic import BaseModel

BRAINTRUST_PROJECT_NAME = "chat-resume"

_ACTION_WORDS = (
    "主导",
    "设计",
    "搭建",
    "实现",
    "优化",
    "重构",
    "推动",
    "落地",
    "独立",
    "负责",
    "delivered",
    "designed",
    "built",
    "optimized",
    "led",
)
_RESULT_WORDS = (
    "提升",
    "降低",
    "减少",
    "增长",
    "覆盖",
    "支撑",
    "降至",
    "提高",
    "improved",
    "reduced",
    "increased",
)
_VAGUE_WORDS = (
    "认真",
    "良好",
    "一些",
    "相关",
    "日常",
    "负责工作",
    "配合良好",
    "没什么好写",
)
_RISK_CLAIMS = (
    "ceo",
    "特别嘉奖",
    "营收",
    "战略产品",
    "带领",
    "管理",
    "核心架构师",
    "10 亿",
    "99.99999",
    "0.01ms",
)
_JD_HINT_KEYS = (
    "jd",
    "jd_text",
    "job_description",
    "description",
    "requirements",
    "target_role",
)
_ORIGINAL_KEYS = (
    "original",
    "before",
    "resume_before",
    "source",
    "candidate",
)
_STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "from",
    "this",
    "that",
    "you",
    "are",
    "will",
    "have",
}


class ResumeScorerParams(BaseModel):
    """描述 Braintrust 调用简历 scorer 时传入的通用字段。"""

    input: Any = None
    output: Any = None
    expected: Any = None
    metadata: dict[str, Any] | None = None


def _as_text(value: Any) -> str:
    """把 Braintrust 传入的任意值转换成可评分文本。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        direct_output = value.get("optimized_bullet") or value.get("output")
        if isinstance(direct_output, str):
            return direct_output
        return " ".join(_as_text(item) for item in value.values())
    if isinstance(value, list | tuple):
        return " ".join(_as_text(item) for item in value)
    return str(value)


def _walk_values(value: Any) -> list[tuple[str, Any]]:
    """展开嵌套字典，便于按字段名查找输入文本。"""
    if not isinstance(value, dict):
        return []

    values: list[tuple[str, Any]] = []
    for key, item in value.items():
        values.append((str(key), item))
        values.extend(_walk_values(item))
    return values


def _find_text_by_keys(keys: tuple[str, ...], *sources: Any) -> str:
    """按常见字段名从 Braintrust input/expected/metadata 中找文本。"""
    normalized = {key.lower() for key in keys}
    for source in sources:
        for key, value in _walk_values(source):
            if key.lower() in normalized:
                text = _as_text(value).strip()
                if text:
                    return text
    return ""


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    """判断文本是否命中任一关键词。"""
    lowered = text.lower()
    return any(word.lower() in lowered for word in words)


def _metric_count(text: str) -> int:
    """统计简历 bullet 中可量化指标的数量。"""
    pattern = r"(\d+(?:\.\d+)?\s?(?:%|pp|万|亿|tb|gb|ms|s|h|min|条|个|人|次|天|月)?)|p\d{2}"
    return len(re.findall(pattern, text.lower()))


def _clamp_score(score: float) -> float:
    """把浮点数约束在 Braintrust score 的 0 到 1 范围内。"""
    return max(0.0, min(1.0, round(score, 4)))


def _star_components(text: str) -> dict[str, float]:
    """计算简历 bullet 的 STAR 相关基础特征。"""
    stripped = text.strip()
    if not stripped:
        return {"action": 0.0, "specificity": 0.0, "metric": 0.0, "result": 0.0, "clarity": 0.0}

    length = len(stripped)
    metric_hits = _metric_count(stripped)
    vague_penalty = 0.25 if _contains_any(stripped, _VAGUE_WORDS) else 0.0
    return {
        "action": 1.0 if _contains_any(stripped, _ACTION_WORDS) else 0.0,
        "specificity": 1.0 if length >= 18 and not vague_penalty else 0.5,
        "metric": min(1.0, metric_hits / 2),
        "result": 1.0 if _contains_any(stripped, _RESULT_WORDS) else 0.0,
        "clarity": _clamp_score(1.0 - vague_penalty - (0.2 if length > 120 else 0.0)),
    }


def _weighted_average(parts: dict[str, float], weights: dict[str, float]) -> float:
    """按权重合并多个评分维度。"""
    total_weight = sum(weights.values())
    if total_weight <= 0:
        return 0.0
    total = sum(parts.get(name, 0.0) * weight for name, weight in weights.items())
    return _clamp_score(total / total_weight)


def _extract_keywords(text: str) -> set[str]:
    """从 JD 或目标职位文本中抽取可匹配的关键词。"""
    english = {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", text.lower())
        if token not in _STOPWORDS
    }
    domain_words = {
        word.lower()
        for word in (
            "python",
            "fastapi",
            "react",
            "typescript",
            "agent",
            "llm",
            "rag",
            "简历",
            "后端",
            "前端",
            "性能",
            "评测",
            "监控",
            "数据",
            "架构",
        )
        if word.lower() in text.lower()
    }
    return english | domain_words


def star_quality_scorer(
    input: Any = None,
    output: Any = None,
    expected: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """评估输出 bullet 是否具备动作、上下文、量化结果和清晰度。"""
    del input, expected, metadata
    text = _as_text(output)
    parts = _star_components(text)
    weights = {"action": 0.2, "specificity": 0.2, "metric": 0.25, "result": 0.25, "clarity": 0.1}
    return {
        "name": "Resume STAR quality score",
        "score": _weighted_average(parts, weights),
        "metadata": parts,
    }


def jd_match_scorer(
    input: Any = None,
    output: Any = None,
    expected: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """评估输出 bullet 与 JD 或目标岗位关键词的匹配程度。"""
    jd_text = _find_text_by_keys(_JD_HINT_KEYS, input, expected, metadata)
    keywords = _extract_keywords(jd_text)
    if not keywords:
        return {
            "name": "Resume JD match score",
            "score": 0.5,
            "metadata": {"missing_jd": True, "matched_keywords": []},
        }

    output_text = _as_text(output).lower()
    matched = sorted(keyword for keyword in keywords if keyword in output_text)
    denominator = min(len(keywords), 12)
    return {
        "name": "Resume JD match score",
        "score": _clamp_score(len(matched) / denominator),
        "metadata": {
            "missing_jd": False,
            "keyword_count": len(keywords),
            "matched_keywords": matched,
        },
    }


def hallucination_safety_scorer(
    input: Any = None,
    output: Any = None,
    expected: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """评估输出是否引入高风险、难以从原文支持的夸大信息。"""
    del expected
    original = _find_text_by_keys(_ORIGINAL_KEYS, input, metadata)
    original_text = original.lower()
    output_text = _as_text(output).lower()
    unsupported = [
        claim
        for claim in _RISK_CLAIMS
        if claim in output_text and claim not in original_text
    ]
    return {
        "name": "Resume hallucination safety",
        "score": _clamp_score(1.0 - len(unsupported) * 0.25),
        "metadata": {
            "hallucination_count": len(unsupported),
            "unsupported_claims": unsupported,
            "missing_original": not bool(original),
        },
    }


def uplift_score_scorer(
    input: Any = None,
    output: Any = None,
    expected: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """评估输出相对原始 bullet 是否有可见质量提升。"""
    del expected
    original = _find_text_by_keys(_ORIGINAL_KEYS, input, metadata)
    output_text = _as_text(output)
    if not original:
        return {
            "name": "Resume uplift score",
            "score": 0.5,
            "metadata": {"missing_original": True},
        }

    original_score = star_quality_scorer(output=original)["score"]
    output_score = star_quality_scorer(output=output_text)["score"]
    unchanged_penalty = 0.35 if original.strip() == output_text.strip() else 0.0
    score = 0.5 + float(output_score) - float(original_score) - unchanged_penalty
    return {
        "name": "Resume uplift score",
        "score": _clamp_score(score),
        "metadata": {
            "missing_original": False,
            "original_star_score": original_score,
            "output_star_score": output_score,
            "unchanged": original.strip() == output_text.strip(),
        },
    }


def final_resume_score_scorer(
    input: Any = None,
    output: Any = None,
    expected: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """合并核心维度，给出面向简历优化目标的总分。"""
    star = star_quality_scorer(input=input, output=output, expected=expected, metadata=metadata)
    uplift = uplift_score_scorer(input=input, output=output, expected=expected, metadata=metadata)
    jd_match = jd_match_scorer(input=input, output=output, expected=expected, metadata=metadata)
    safety = hallucination_safety_scorer(input=input, output=output, expected=expected, metadata=metadata)
    parts = {
        "star_quality": float(star["score"]),
        "uplift": float(uplift["score"]),
        "jd_match": float(jd_match["score"]),
        "hallucination_safety": float(safety["score"]),
    }
    weights = {"star_quality": 0.35, "uplift": 0.25, "jd_match": 0.2, "hallucination_safety": 0.2}
    return {
        "name": "Resume final score",
        "score": _weighted_average(parts, weights),
        "metadata": parts,
    }


project = braintrust.projects.create(name=BRAINTRUST_PROJECT_NAME)

project.scorers.create(
    name="Resume final score",
    slug="resume-final-score",
    description="Composite score for resume bullet quality, uplift, JD match, and hallucination safety.",
    parameters=ResumeScorerParams,
    handler=final_resume_score_scorer,
    metadata={"__pass_threshold": 0.75},
    if_exists="replace",
    tags=["resume", "quality"],
)

project.scorers.create(
    name="Resume uplift score",
    slug="resume-uplift-score",
    description="Checks whether the optimized bullet improves over the original bullet.",
    parameters=ResumeScorerParams,
    handler=uplift_score_scorer,
    metadata={"__pass_threshold": 0.7},
    if_exists="replace",
    tags=["resume", "quality"],
)

project.scorers.create(
    name="Resume JD match score",
    slug="resume-jd-match-score",
    description="Measures keyword overlap between the optimized bullet and JD or target role text.",
    parameters=ResumeScorerParams,
    handler=jd_match_scorer,
    metadata={"__pass_threshold": 0.6},
    if_exists="replace",
    tags=["resume", "quality"],
)

project.scorers.create(
    name="Resume STAR quality score",
    slug="resume-star-quality-score",
    description="Scores action, specificity, metric, result, and clarity signals in a resume bullet.",
    parameters=ResumeScorerParams,
    handler=star_quality_scorer,
    metadata={"__pass_threshold": 0.75},
    if_exists="replace",
    tags=["resume", "quality"],
)

project.scorers.create(
    name="Resume hallucination safety",
    slug="resume-hallucination-safety",
    description="Penalizes unsupported high-risk claims that are not present in the original bullet.",
    parameters=ResumeScorerParams,
    handler=hallucination_safety_scorer,
    metadata={"__pass_threshold": 0.85},
    if_exists="replace",
    tags=["resume", "safety"],
)
