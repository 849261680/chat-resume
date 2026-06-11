"""用于评估最终简历是否达到顶级投递质量。"""

from __future__ import annotations

import re
from typing import Any

_NUMBER_CLAIM_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|万|千|ms|s|秒|人|用户|DAU|QPS)?", re.IGNORECASE)
_TECH_TERMS = (
    "Redis",
    "Kafka",
    "RabbitMQ",
    "Kubernetes",
    "K8s",
    "Docker",
    "Spring Cloud",
    "Spring Boot",
    "Dubbo",
    "MySQL",
    "PostgreSQL",
    "MongoDB",
    "ElasticSearch",
    "Elasticsearch",
    "React",
    "Vue",
    "TypeScript",
    "FastAPI",
    "Django",
    "RAG",
    "LangChain",
    "GraphQL",
    "Prometheus",
    "SSE",
    "ReAct",
    "Agent",
    "向量数据库",
    "微服务",
    "高并发",
)
_ACTION_WORDS = (
    "设计",
    "搭建",
    "推动",
    "重构",
    "实现",
    "开发",
    "优化",
    "构建",
    "建立",
    "改造",
    "落地",
    "迁移",
    "解决",
    "修复",
    "主导",
    "串联",
    "Design",
    "Built",
    "Implemented",
    "Optimized",
)
_RESULT_WORDS = (
    "提升",
    "降低",
    "缩短",
    "减少",
    "增长",
    "覆盖",
    "支撑",
    "保障",
    "拦截",
    "修复",
    "持续",
    "定位",
    "improved",
    "reduced",
    "increased",
    "supported",
    "reducing",
    "improving",
    "streamline",
)
_WEAK_PREFIXES = ("负责", "参与", "协助", "帮助", "配合", "完成")
_ROLE_TERMS = (
    "Agent",
    "Runtime",
    "工具调用",
    "评测",
    "eval",
    "前端",
    "后端",
    "接口",
    "数据库",
    "性能",
    "工程化",
    "React",
    "FastAPI",
    "PostgreSQL",
    "JD",
    "diff",
)
_ROLE_ALIASES = {
    "性能": ("加载时间", "首屏", "延迟", "响应时间", "耗时"),
}
_CAPABILITY_CLAIMS = (
    "索引优化",
    "数据库优化",
    "数据库查询优化",
    "查询优化",
    "性能优化",
    "参数校验",
    "稳定性建设",
    "稳定性",
    "服务治理",
    "生产级",
)
_TOP_RESUME_THRESHOLD = 85


def score_final_resume_quality(
    *,
    resume_before: dict[str, Any],
    resume_after: dict[str, Any],
    jd_text: str = "",
    user_message: str = "",
    applicable: bool = True,
) -> dict[str, Any]:
    """用于给最终简历成品打顶级质量分。"""
    if not applicable:
        return _not_applicable()

    source_text = _collect_text([_resume_body(resume_before), user_message])
    after_text = _collect_text(_resume_body(resume_after))
    highlights = _scored_highlights(resume_before, resume_after)
    unsupported = _unsupported_claims(after_text, source_text)
    dimensions = {
        "role_fit": _score_role_fit(after_text, jd_text),
        "star_strength": _score_star_strength(highlights),
        "evidence_density": _score_evidence_density(highlights),
        "fact_trust": _score_fact_trust(unsupported),
        "interview_readiness": _score_interview_readiness(highlights),
    }
    score = _weighted_score(dimensions)
    failure_codes = _failure_codes(score, dimensions, unsupported)
    return {
        "applicable": True,
        "passed": not failure_codes,
        "score": score,
        "threshold": _TOP_RESUME_THRESHOLD,
        "level": _level(score),
        "failure_codes": failure_codes,
        "dimensions": dimensions,
        "fact_check": {"unsupported_claims": unsupported},
    }


def _not_applicable() -> dict[str, Any]:
    """用于返回无需评估最终成品的结果。"""
    return {
        "applicable": False,
        "passed": True,
        "score": None,
        "threshold": _TOP_RESUME_THRESHOLD,
        "level": "not_applicable",
        "failure_codes": [],
        "dimensions": {},
        "fact_check": {"unsupported_claims": []},
    }


def _weighted_score(dimensions: dict[str, dict[str, Any]]) -> int:
    """用于按权重汇总最终质量分。"""
    weights = {
        "role_fit": 0.20,
        "star_strength": 0.25,
        "evidence_density": 0.20,
        "fact_trust": 0.25,
        "interview_readiness": 0.10,
    }
    total = sum(dimensions[key]["score"] * weight for key, weight in weights.items())
    return round(total)


def _failure_codes(
    score: int,
    dimensions: dict[str, dict[str, Any]],
    unsupported: list[str],
) -> list[str]:
    """用于把维度失败压缩成报告失败码。"""
    failures = []
    if unsupported:
        failures.append("unsupported_claims")
    if not dimensions["role_fit"]["passed"]:
        failures.append("low_role_fit")
    if not dimensions["star_strength"]["passed"]:
        failures.append("insufficient_star")
    if not dimensions["evidence_density"]["passed"]:
        failures.append("weak_evidence")
    if not dimensions["interview_readiness"]["passed"]:
        failures.append("low_interview_readiness")
    if score < _TOP_RESUME_THRESHOLD:
        failures.append("final_score_below_threshold")
    return failures


def _score_role_fit(after_text: str, jd_text: str) -> dict[str, Any]:
    """用于评估最终简历与目标岗位关键词的贴合度。"""
    wanted = [term for term in _ROLE_TERMS if term.lower() in jd_text.lower()]
    if not wanted:
        return {"score": 80, "passed": True, "matched": [], "required": []}
    matched = [term for term in wanted if _role_term_matches(term, after_text)]
    ratio = len(matched) / len(wanted)
    return {
        "score": round(min(100, 50 + ratio * 50)),
        "passed": len(matched) >= min(2, len(wanted)),
        "matched": matched,
        "required": wanted,
    }
def _role_term_matches(term: str, after_text: str) -> bool:
    """用于判断岗位关键词是否被正文或等价证据命中。"""
    lowered = after_text.lower()
    if term.lower() in lowered:
        return True
    aliases = _ROLE_ALIASES.get(term, ())
    return any(alias.lower() in lowered for alias in aliases)




def _score_star_strength(highlights: list[str]) -> dict[str, Any]:
    """用于评估亮点是否具备动作、方案和结果链条。"""
    if not highlights:
        return {"score": 0, "passed": False, "strong_count": 0, "total": 0}
    strong = [text for text in highlights if _is_star_bullet(text)]
    ratio = len(strong) / len(highlights)
    required = min(2, len(highlights))
    return {
        "score": round(ratio * 100),
        "passed": ratio >= 0.6 and len(strong) >= required,
        "strong_count": len(strong),
        "total": len(highlights),
    }


def _score_evidence_density(highlights: list[str]) -> dict[str, Any]:
    """用于评估亮点中的可验证证据密度。"""
    if not highlights:
        return {"score": 0, "passed": False, "evidence_count": 0, "total": 0}
    evidenced = [text for text in highlights if _has_evidence(text)]
    ratio = len(evidenced) / len(highlights)
    required = min(2, len(highlights))
    return {
        "score": round(ratio * 100),
        "passed": ratio >= 0.6 and len(evidenced) >= required,
        "evidence_count": len(evidenced),
        "total": len(highlights),
    }


def _score_fact_trust(unsupported: list[str]) -> dict[str, Any]:
    """用于评估最终简历是否引入无来源事实。"""
    score = 100 if not unsupported else max(0, 100 - len(unsupported) * 25)
    return {"score": score, "passed": not unsupported, "unsupported_count": len(unsupported)}


def _score_interview_readiness(highlights: list[str]) -> dict[str, Any]:
    """用于评估亮点是否足够支撑面试追问。"""
    ready = [text for text in highlights if _is_interview_ready(text)]
    total = len(highlights)
    score = round(len(ready) / total * 100) if total else 0
    required = min(2, total)
    return {
        "score": score,
        "passed": len(ready) >= required,
        "ready_count": len(ready),
        "total": total,
    }


def _is_star_bullet(text: str) -> bool:
    """用于判断单条亮点是否接近 STAR 结构。"""
    has_action = any(word in text for word in _ACTION_WORDS)
    has_result = any(word in text for word in _RESULT_WORDS) or bool(_NUMBER_CLAIM_RE.search(text))
    starts_weak = text.startswith(_WEAK_PREFIXES) and not has_result
    has_specifics = _has_tech(text) or len(text) >= 45
    return has_action and has_result and has_specifics and not starts_weak


def _has_evidence(text: str) -> bool:
    """用于判断单条亮点是否包含数字、技术或明确结果证据。"""
    has_number = bool(_NUMBER_CLAIM_RE.search(text))
    has_result = any(word in text for word in _RESULT_WORDS)
    return has_number or (_has_tech(text) and has_result)


def _is_interview_ready(text: str) -> bool:
    """用于判断单条亮点是否具备可追问的技术链路。"""
    has_action = any(word in text for word in _ACTION_WORDS)
    has_context = _has_context_connector(text)
    return has_action and has_context and len(text) >= 45
def _has_context_connector(text: str) -> bool:
    """用于识别中文标点或英文连接词提供的动作链路。"""
    if "，" in text or "," in text or "、" in text:
        return True
    lowered = text.lower()
    return any(f" {word} " in lowered for word in ("to", "that", "and", "for"))




def _has_tech(text: str) -> bool:
    """用于判断文本是否包含技术栈或 Agent 领域词。"""
    lowered = text.lower()
    return any(term.lower() in lowered for term in _TECH_TERMS)


def _unsupported_claims(after_text: str, source_text: str) -> list[str]:
    """用于找出最终简历中没有来源支撑的事实主张。"""
    source_lower = source_text.lower()
    claims = (
        _extract_number_claims(after_text)
        + _extract_tech_terms(after_text)
        + _extract_capability_claims(after_text)
    )
    return _dedupe([claim for claim in claims if not _claim_supported(claim, source_lower)])



def _claim_supported(claim: str, source_lower: str) -> bool:
    """用于判断最终简历事实是否可由来源文本支撑。"""
    claim_lower = claim.lower()
    if claim_lower in source_lower or _compact_fact(claim_lower) in _compact_fact(source_lower):
        return True
    return claim in {"稳定性", "稳定性建设"} and _has_stability_evidence(source_lower)

def _has_stability_evidence(source_lower: str) -> bool:
    """用于识别监控和故障定位事实对稳定性表达的支撑。"""
    evidence_terms = ("prometheus", "监控", "故障", "告警", "定位", "排查")
    return any(term in source_lower for term in evidence_terms)


def _compact_fact(value: str) -> str:
    """用于忽略数字和单位之间的空白差异。"""
    return "".join(value.split())

def _extract_number_claims(text: str) -> list[str]:
    """用于提取数字型事实。"""
    return [match.group(0).strip() for match in _NUMBER_CLAIM_RE.finditer(text)]


def _extract_tech_terms(text: str) -> list[str]:
    """用于提取技术栈事实。"""
    lowered = text.lower()
    return [term for term in _TECH_TERMS if term.lower() in lowered]


def _extract_capability_claims(text: str) -> list[str]:
    """用于提取容易被 JD 诱导编造的能力型事实。"""
    lowered = text.lower()
    return [claim for claim in _CAPABILITY_CLAIMS if claim.lower() in lowered]


def _scored_highlights(
    resume_before: dict[str, Any],
    resume_after: dict[str, Any],
) -> list[str]:
    """用于优先评分本轮新增或改写的亮点文本。"""
    after_highlights = _resume_highlights(resume_after)
    before_highlights = set(_resume_highlights(resume_before))
    changed = [text for text in after_highlights if text not in before_highlights]
    return changed or after_highlights


def _resume_highlights(resume: dict[str, Any]) -> list[str]:
    """用于从简历结构中提取所有亮点文本。"""
    highlights = []
    for section in ("work_experience", "projects", "open_source"):
        highlights.extend(_section_highlights(resume.get(section)))
    return highlights


def _section_highlights(section_value: Any) -> list[str]:
    """用于从单个简历板块中提取亮点文本。"""
    if not isinstance(section_value, list):
        return []
    highlights = []
    for item in section_value:
        if isinstance(item, dict):
            highlights.extend(_item_highlights(item))
    return highlights


def _item_highlights(item: dict[str, Any]) -> list[str]:
    """用于从单个经历条目中提取亮点文本。"""
    raw_highlights = item.get("highlights")
    if not isinstance(raw_highlights, list):
        return []
    return [_highlight_text(value) for value in raw_highlights if _highlight_text(value)]


def _highlight_text(value: Any) -> str:
    """用于兼容字符串和对象形式的亮点。"""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict) and isinstance(value.get("text"), str):
        return value["text"].strip()
    return ""


def _collect_text(value: Any) -> str:
    """用于把简历结构压平成可检索文本。"""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(
            _collect_text(item)
            for key, item in value.items()
            if key not in {"id", "bullet_id", "item_id"}
        )
    if isinstance(value, list):
        return " ".join(_collect_text(item) for item in value)
    return "" if value is None else str(value)


def _resume_body(resume: dict[str, Any]) -> dict[str, Any]:
    """用于移除不应参与事实检查的投递元数据。"""
    return {key: value for key, value in resume.items() if key != "job_application"}


def _dedupe(items: list[str]) -> list[str]:
    """用于在保持顺序的前提下去重。"""
    seen: set[str] = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _level(score: int) -> str:
    """用于把数值分转成可读等级。"""
    if score >= 90:
        return "top"
    if score >= 85:
        return "strong"
    if score >= 70:
        return "acceptable"
    return "weak"


__all__ = ["score_final_resume_quality"]
