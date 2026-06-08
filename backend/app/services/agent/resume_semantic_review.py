"""用于提供简历评分的本地语义评审层。"""

from __future__ import annotations

import re
from typing import Any

from .resume_rule_score import extract_jd_text, flatten_resume_text, iter_bullets

_NUMBER_RE = re.compile(r"\d")
_WEAK_PREFIXES = ("负责", "参与", "协助", "帮助", "配合", "完成")
_OWNERSHIP_WORDS = ("主导", "设计", "搭建", "重构", "推动", "落地", "负责架构", "独立")
_IMPACT_WORDS = ("提升", "降低", "缩短", "减少", "增长", "支撑", "覆盖", "节省", "稳定")
_THEMES = {
    "frontend": ("前端", "React", "Vue", "组件", "页面", "TypeScript"),
    "backend": ("后端", "接口", "服务", "FastAPI", "Python", "Redis", "数据库"),
    "platform": ("平台", "工程化", "组件库", "工作流", "工具链", "自动化"),
    "performance": ("性能", "延迟", "P99", "优化", "高并发", "吞吐"),
    "agent": ("Agent", "工具调用", "ReAct", "记忆", "规划", "LLM"),
    "data": ("数据", "分析", "指标", "实时", "管线", "可观测"),
}
_SECTION_PRIORITY = {"work_experience": 0, "projects": 1, "education": 2}


def review_resume_semantics(
    resume_content: dict[str, Any], _rule_dimensions: list[dict[str, Any]]
) -> dict[str, Any]:
    """用于按招聘经理视角生成语义评审结果。"""
    bullets = _collect_bullets(resume_content)
    jd_text = extract_jd_text(resume_content)
    jd_themes = _theme_hits(jd_text)
    resume_themes = _theme_hits(flatten_resume_text(resume_content))
    dimensions = [
        _role_fit_dimension(jd_text, jd_themes, resume_themes),
        _project_persuasiveness_dimension(bullets),
        _responsibility_depth_dimension(bullets),
        _impact_clarity_dimension(bullets),
        _interview_readiness_dimension(jd_themes, resume_themes, bullets),
    ]
    weak_signals = _weak_signals(jd_themes, resume_themes, bullets)
    score = round(sum(item["score"] for item in dimensions) / len(dimensions))
    return {
        "status": "available",
        "method": "local_semantic_heuristic",
        "overall": {
            "score": score,
            "level": _level(score),
            "reason": _overall_reason(dimensions),
        },
        "dimensions": dimensions,
        "selling_points": _selling_points(resume_themes),
        "weak_signals": weak_signals,
        "interview_risks": _interview_risks(weak_signals),
        "priority_actions": _priority_actions(weak_signals),
    }


def _collect_bullets(resume_content: dict[str, Any]) -> list[dict[str, str]]:
    """用于把经历 bullet 整理成带定位信息的列表。"""
    return [
        {
            "section": section,
            "item_id": item_id,
            "bullet_id": bullet_id,
            "text": text,
        }
        for section, item_id, bullet_id, text in iter_bullets(resume_content)
    ]


def _role_fit_dimension(
    jd_text: str, jd_themes: set[str], resume_themes: set[str]
) -> dict[str, Any]:
    """用于评估简历经历场景与目标岗位职责的相似度。"""
    if not jd_text:
        return _dimension("role_fit", 70, "未提供 JD，无法判断具体岗位职责贴合度", "补充目标 JD 后再复评岗位匹配")
    missing = sorted(jd_themes - resume_themes)
    score = 90 if not missing else max(45, 90 - len(missing) * 15)
    evidence = _theme_evidence(jd_themes, resume_themes)
    suggestion = "把经历描述连接到 JD 的核心职责，而不是只堆关键词"
    return _dimension("role_fit", score, evidence, suggestion)


def _project_persuasiveness_dimension(bullets: list[dict[str, str]]) -> dict[str, Any]:
    """用于评估项目是否体现真实问题、约束和结果。"""
    if not bullets:
        return _dimension("project_persuasiveness", 30, "缺少经历 bullet", "补充项目背景、难点、方案和结果")
    strong = [item for item in bullets if _has_impact(item["text"]) and _has_number(item["text"])]
    score = min(95, 45 + round(len(strong) / len(bullets) * 50))
    return _dimension("project_persuasiveness", score, "项目说服力取决于难点、动作和结果是否同时出现", "优先把泛泛职责改成业务问题、技术方案和可验证结果")


def _responsibility_depth_dimension(bullets: list[dict[str, str]]) -> dict[str, Any]:
    """用于评估候选人的职责深度和 ownership。"""
    if not bullets:
        return _dimension("responsibility_depth", 30, "缺少可判断职责深度的经历", "补充个人负责范围和决策动作")
    owned = [item for item in bullets if _has_ownership(item["text"])]
    weak = [item for item in bullets if item["text"].startswith(_WEAK_PREFIXES)]
    score = min(95, 55 + len(owned) * 12 - len(weak) * 8)
    return _dimension("responsibility_depth", max(35, score), "职责深度看候选人是否推动方案，而不只是参与执行", "用主导、设计、推动、落地等事实动作体现 ownership")


def _impact_clarity_dimension(bullets: list[dict[str, str]]) -> dict[str, Any]:
    """用于评估结果和业务影响是否清晰。"""
    if not bullets:
        return _dimension("impact_clarity", 30, "缺少结果证据", "补充可验证的影响指标")
    quantified = [item for item in bullets if _has_number(item["text"])]
    score = min(95, 40 + round(len(quantified) / len(bullets) * 55))
    return _dimension("impact_clarity", score, "招聘方需要通过结果判断价值，而不是只看技术动作", "补充性能、效率、规模、成本或稳定性指标")


def _interview_readiness_dimension(
    jd_themes: set[str], resume_themes: set[str], bullets: list[dict[str, str]]
) -> dict[str, Any]:
    """用于评估简历亮点被追问时是否站得住。"""
    unsupported = jd_themes - resume_themes
    vague = [item for item in bullets if _is_vague(item["text"])]
    score = max(35, 88 - len(unsupported) * 10 - len(vague) * 8)
    return _dimension("interview_readiness", score, "可面试性取决于每个卖点是否有事实支撑", "把容易被追问的亮点补成背景、动作、结果和口径")


def _dimension(key: str, score: int, evidence: str, suggestion: str) -> dict[str, Any]:
    """用于创建统一的语义维度结果。"""
    return {
        "key": key,
        "score": max(0, min(100, score)),
        "evidence": evidence,
        "risk": _risk(score),
        "suggestion": suggestion,
    }


def _weak_signals(
    jd_themes: set[str], resume_themes: set[str], bullets: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """用于提取影响招聘经理判断的弱信号。"""
    signals = _bullet_weak_signals(bullets)
    signals.extend(_missing_theme_signals(jd_themes - resume_themes))
    signals.sort(key=_weak_signal_sort_key)
    return signals[:6]


def _weak_signal_sort_key(signal: dict[str, Any]) -> tuple[int, int]:
    """用于优先处理工作或项目经历上的可编辑弱信号。"""
    has_target = 0 if signal.get("target") else 1
    section_rank = _SECTION_PRIORITY.get(str(signal.get("section", "")), 9)
    return has_target, section_rank


def _bullet_weak_signals(bullets: list[dict[str, str]]) -> list[dict[str, Any]]:
    """用于从 bullet 中提取可定位的语义弱信号。"""
    signals = []
    for item in bullets:
        if _is_vague(item["text"]):
            signals.append(_weak_bullet_signal(item, "职责描述偏泛，缺少难点或结果"))
    return signals


def _missing_theme_signals(missing_themes: set[str]) -> list[dict[str, Any]]:
    """用于把未被简历支撑的 JD 主题转成弱信号。"""
    return [
        {
            "issue": f"JD 核心职责「{theme}」缺少经历支撑",
            "target": {},
            "rewrite_direction": "如有真实经历，补充相关项目背景、个人动作和结果证据",
            "tool_hint": "add_bullet",
        }
        for theme in sorted(missing_themes)
    ]


def _weak_bullet_signal(item: dict[str, str], issue: str) -> dict[str, Any]:
    """用于创建带 bullet 定位的弱信号。"""
    return {
        "issue": issue,
        "target": {"item_id": item["item_id"], "bullet_id": item["bullet_id"]},
        "section": item["section"],
        "rewrite_direction": "补充项目约束、个人决策、技术方案和可验证结果",
        "tool_hint": "update_bullet",
    }


def _priority_actions(weak_signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用于把语义弱信号转成统一优先动作。"""
    return [
        {
            "source": "semantic_review",
            "dimension_key": "semantic_review",
            "dimension_name": "语义评审",
            "title": signal["rewrite_direction"],
            "reason": signal["issue"],
            "target": signal.get("target", {}),
            "section": signal.get("section", ""),
            "tool_hint": signal.get("tool_hint", "update_resume"),
        }
        for signal in weak_signals
    ]


def _theme_hits(text: str) -> set[str]:
    """用于从文本中提取职责主题。"""
    return {
        theme
        for theme, keywords in _THEMES.items()
        if any(keyword.lower() in text.lower() for keyword in keywords)
    }


def _theme_evidence(jd_themes: set[str], resume_themes: set[str]) -> str:
    """用于说明 JD 主题和简历主题的覆盖关系。"""
    matched = "、".join(sorted(jd_themes & resume_themes)) or "无明显重合主题"
    missing = "、".join(sorted(jd_themes - resume_themes)) or "无明显缺口"
    return f"已支撑主题：{matched}；缺口主题：{missing}"


def _selling_points(resume_themes: set[str]) -> list[str]:
    """用于把命中的职责主题转成候选人卖点。"""
    labels = {
        "frontend": "前端工程能力",
        "backend": "后端工程能力",
        "platform": "平台化和工程效率",
        "performance": "性能优化",
        "agent": "Agent 工具链经验",
        "data": "数据和可观测能力",
    }
    return [labels[theme] for theme in sorted(resume_themes)]


def _interview_risks(weak_signals: list[dict[str, Any]]) -> list[str]:
    """用于把弱信号转成面试追问风险。"""
    return [
        f"如果被追问：{signal['issue']}，当前简历证据不足。"
        for signal in weak_signals[:4]
    ]


def _overall_reason(dimensions: list[dict[str, Any]]) -> str:
    """用于生成语义评审的一句话结论。"""
    weakest = min(dimensions, key=lambda item: item["score"])
    return f"语义层最大短板是 {weakest['key']}：{weakest['evidence']}"


def _level(score: int) -> str:
    """用于把语义分转成等级。"""
    if score >= 85:
        return "strong"
    if score >= 70:
        return "medium"
    return "weak"


def _risk(score: int) -> str:
    """用于把单项语义分转成风险标签。"""
    if score >= 80:
        return "low"
    if score >= 60:
        return "medium"
    return "high"


def _has_number(text: str) -> bool:
    """用于判断文本是否包含量化证据。"""
    return bool(_NUMBER_RE.search(text))


def _has_impact(text: str) -> bool:
    """用于判断文本是否包含结果影响表达。"""
    return any(word in text for word in _IMPACT_WORDS)


def _has_ownership(text: str) -> bool:
    """用于判断文本是否体现 ownership。"""
    return any(word in text for word in _OWNERSHIP_WORDS)


def _is_vague(text: str) -> bool:
    """用于判断 bullet 是否像职责描述而非成果证据。"""
    return text.startswith(_WEAK_PREFIXES) or not _has_number(text)


__all__ = ["review_resume_semantics"]
