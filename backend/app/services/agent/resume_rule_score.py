"""用于提供简历评分的确定性规则检查层。"""

from __future__ import annotations

import re
from typing import Any, Iterator

# 规则评分维度的基础权重，无 JD 时 jd_match 会被剔除并按比例归一到 100。
_BASE_WEIGHTS = {
    "completeness": 30,
    "quantification": 25,
    "expression": 20,
    "jd_match": 25,
}
_DIMENSION_NAMES = {
    "completeness": "完整度",
    "quantification": "量化程度",
    "expression": "表达质量",
    "jd_match": "JD 匹配",
}
_BULLET_SECTIONS = ("education", "work_experience", "projects")
_NUMBER_RE = re.compile(r"\d")
_WEAK_PREFIXES = ("负责", "参与", "协助", "帮助", "配合", "完成")
_ENGLISH_KEYWORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9+#.\-]{1,}\b")
_COMMON_CN_KEYWORDS = (
    "性能优化", "前端", "后端", "全栈", "数据分析", "项目管理", "团队协作",
    "系统设计", "高并发", "微服务", "工作流", "向量数据库", "消息队列",
    "Agent", "机器学习", "深度学习", "推荐系统", "可观测", "检索增强",
)
_EN_STOPWORDS = {
    "and", "or", "the", "for", "with", "you", "our", "will", "are", "etc",
    "to", "of", "in", "on", "at", "as", "is", "be", "we", "an", "by",
}
_SECTION_PRIORITY = {"work_experience": 0, "projects": 1, "education": 2}


def score_resume_rules(resume_content: dict[str, Any]) -> dict[str, Any]:
    """用于返回完整的确定性规则评分结果。"""
    dimensions = [
        _score_completeness(resume_content),
        _score_quantification(resume_content),
        _score_expression(resume_content),
    ]
    jd_text = extract_jd_text(resume_content)
    if jd_text:
        dimensions.append(_score_jd_match(resume_content, jd_text))

    scored = _apply_weights(dimensions)
    score = round(sum(item["score"] for item in scored))
    return {
        "score": score,
        "grade": grade_score(score),
        "dimensions": scored,
        "top_suggestions": _collect_top_suggestions(scored),
        "priority_actions": build_rule_priority_actions(scored),
    }


def grade_score(total: int) -> str:
    """用于把总分映射成等级标签。"""
    thresholds = ((90, "A"), (80, "B"), (70, "C"), (60, "D"))
    return next((label for line, label in thresholds if total >= line), "F")


def build_rule_priority_actions(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用于把规则 findings 转成 Agent 可执行动作。"""
    actions = []
    for dimension in _dimensions_by_weakness(scored):
        actions.extend(_dimension_actions(dimension))
    actions.sort(key=_action_sort_key)
    return actions[:5]


def extract_jd_text(resume_content: dict[str, Any]) -> str:
    """用于从简历内容中读取目标岗位 JD 文本。"""
    job_application = resume_content.get("job_application")
    if not isinstance(job_application, dict):
        return ""
    return str(job_application.get("jd_text") or "").strip()


def iter_bullets(resume_content: dict[str, Any]) -> Iterator[tuple[str, str, str, str]]:
    """用于遍历经历板块下的 bullet，产出板块、条目 id、bullet id 和文本。"""
    for section in _BULLET_SECTIONS:
        for item in resume_content.get(section) or []:
            item_id = str(item.get("id", ""))
            yield from _iter_item_bullets(section, item_id, item)


def flatten_resume_text(resume_content: dict[str, Any]) -> str:
    """用于把简历正文（排除 JD）压平成可搜索文本。"""
    return "\n".join(
        _flatten_value(value)
        for key, value in resume_content.items()
        if key != "job_application"
    )


def _apply_weights(dimensions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用于把各维度命中比例换算成归一到 100 的实际得分。"""
    weight_sum = sum(_BASE_WEIGHTS[item["key"]] for item in dimensions) or 1
    scored = []
    for item in dimensions:
        max_score = _BASE_WEIGHTS[item["key"]] / weight_sum * 100
        scored.append({
            "key": item["key"],
            "name": _DIMENSION_NAMES[item["key"]],
            "score": round(item["ratio"] * max_score, 1),
            "max": round(max_score, 1),
            "findings": item["findings"],
        })
    return scored


def _collect_top_suggestions(scored: list[dict[str, Any]]) -> list[str]:
    """用于从得分最低的维度里汇总最多 4 条优先修改建议。"""
    weakest = sorted(scored, key=lambda item: item["score"] / (item["max"] or 1))
    suggestions: list[str] = []
    for dimension in weakest:
        suggestions.extend(finding["suggestion"] for finding in dimension["findings"])
    return _dedupe(suggestions)[:4]


def _dimensions_by_weakness(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用于按相对短板程度排序维度。"""
    return sorted(scored, key=lambda item: item["score"] / (item["max"] or 1))


def _dimension_actions(dimension: dict[str, Any]) -> list[dict[str, Any]]:
    """用于把单个维度的 findings 转成候选动作。"""
    return [
        {
            "source": "rule_checks",
            "dimension_key": dimension["key"],
            "dimension_name": dimension["name"],
            "title": finding["suggestion"],
            "reason": finding["issue"],
            "target": _finding_target(finding),
            "section": finding.get("section", ""),
            "tool_hint": _tool_hint(finding),
        }
        for finding in dimension["findings"]
    ]


def _action_sort_key(action: dict[str, Any]) -> tuple[int, int]:
    """用于优先选择工作或项目 bullet 这类可直接编辑的动作。"""
    has_target = 0 if action["target"] else 1
    section_rank = _SECTION_PRIORITY.get(str(action.get("section") or ""), 9)
    return has_target, section_rank


def _finding_target(finding: dict[str, Any]) -> dict[str, str]:
    """用于从 finding 中提取可编辑的 item/bullet 定位信息。"""
    item_id = str(finding.get("item_id") or "")
    bullet_id = str(finding.get("bullet_id") or "")
    if item_id and bullet_id:
        return {"item_id": item_id, "bullet_id": bullet_id}
    return {}


def _tool_hint(finding: dict[str, Any]) -> str:
    """用于给 Agent 提供下一步可考虑调用的编辑工具名称。"""
    if _finding_target(finding):
        return "update_bullet"
    if finding.get("missing_keyword"):
        return "add_bullet"
    return "update_resume"


def _score_completeness(resume_content: dict[str, Any]) -> dict[str, Any]:
    """用于检查必填板块和字段是否齐全。"""
    personal = resume_content.get("personal_info") or {}
    summary = (resume_content.get("summary") or {}).get("text", "")
    checks = [
        (bool(str(personal.get("name", "")).strip()), "缺少姓名", "补充候选人姓名"),
        (_has_contact(personal), "缺少联系方式", "补充邮箱或手机号等联系方式"),
        (bool(str(summary).strip()), "缺少个人总结", "补充 2-4 句个人总结，突出核心优势"),
        (_has_any(resume_content, ("work_experience", "projects")), "缺少工作或项目经历", "补充至少一段工作或项目经历"),
        (_has_any(resume_content, ("education",)), "缺少教育经历", "补充教育经历"),
        (_has_any(resume_content, ("skills",)), "缺少技能板块", "补充技能板块并分类列出关键技能"),
    ]
    findings = [
        {"issue": issue, "suggestion": suggestion}
        for passed, issue, suggestion in checks
        if not passed
    ]
    ratio = sum(1 for passed, _, _ in checks if passed) / len(checks)
    return {"key": "completeness", "ratio": ratio, "findings": findings}


def _score_quantification(resume_content: dict[str, Any]) -> dict[str, Any]:
    """用于衡量经历 bullet 中含量化结果的比例。"""
    bullets = list(iter_bullets(resume_content))
    if not bullets:
        return {"key": "quantification", "ratio": 0.0, "findings": []}
    findings = [
        {
            "section": section,
            "item_id": item_id,
            "bullet_id": bullet_id,
            "issue": "该要点缺少量化结果",
            "suggestion": "补充可量化的影响，如提升 X%、覆盖 N 用户、缩短到 M 秒",
        }
        for section, item_id, bullet_id, text in bullets
        if not _NUMBER_RE.search(text)
    ]
    ratio = (len(bullets) - len(findings)) / len(bullets)
    return {"key": "quantification", "ratio": ratio, "findings": findings[:6]}


def _score_expression(resume_content: dict[str, Any]) -> dict[str, Any]:
    """用于衡量 bullet 表达是否使用强动作动词且长度适中。"""
    bullets = list(iter_bullets(resume_content))
    if not bullets:
        return {"key": "expression", "ratio": 0.0, "findings": []}
    findings = [
        {
            "section": section,
            "item_id": item_id,
            "bullet_id": bullet_id,
            "issue": _expression_issue(text),
            "suggestion": "用强动作动词开头，控制在一行内，并说清任务-方案-结果",
        }
        for section, item_id, bullet_id, text in bullets
        if _expression_issue(text)
    ]
    ratio = (len(bullets) - len(findings)) / len(bullets)
    return {"key": "expression", "ratio": ratio, "findings": findings[:6]}


def _score_jd_match(resume_content: dict[str, Any], jd_text: str) -> dict[str, Any]:
    """用于按确定性关键词覆盖率衡量简历与 JD 的匹配度。"""
    keywords = _extract_jd_keywords(jd_text)
    if not keywords:
        return {"key": "jd_match", "ratio": 0.0, "findings": []}
    resume_text = flatten_resume_text(resume_content).lower()
    missing = [kw for kw in keywords if kw.lower() not in resume_text]
    ratio = (len(keywords) - len(missing)) / len(keywords)
    findings = [
        {
            "issue": f"JD 关键词「{keyword}」未在简历中体现",
            "suggestion": f"如有真实经历，补充与「{keyword}」相关的事实和结果",
            "missing_keyword": keyword,
        }
        for keyword in missing[:6]
    ]
    return {"key": "jd_match", "ratio": ratio, "findings": findings}


def _has_contact(personal: dict[str, Any]) -> bool:
    """用于判断个人信息里是否存在联系方式。"""
    email = str(personal.get("email", "")).strip()
    phone = str(personal.get("phone", "")).strip()
    return bool(email or phone)


def _expression_issue(text: str) -> str:
    """用于判断单条 bullet 的表达问题，无问题时返回空串。"""
    stripped = text.strip()
    if len(stripped) < 8:
        return "要点过短，信息量不足"
    if len(stripped) > 120:
        return "要点过长，建议拆分或精简"
    if stripped.startswith(_WEAK_PREFIXES):
        return "以弱动词开头，建议换成强动作动词"
    return ""


def _iter_item_bullets(
    section: str, item_id: str, item: dict[str, Any]
) -> Iterator[tuple[str, str, str, str]]:
    """用于产出单个条目下的全部 bullet。"""
    for highlight in item.get("highlights") or []:
        text = str(highlight.get("text", "")).strip()
        if text:
            yield section, item_id, str(highlight.get("id", "")), text


def _has_any(resume_content: dict[str, Any], sections: tuple[str, ...]) -> bool:
    """用于判断给定板块里是否存在至少一个条目。"""
    return any(resume_content.get(section) for section in sections)


def _extract_jd_keywords(jd_text: str) -> list[str]:
    """用于从 JD 中提取确定性关键词，最多 20 个。"""
    keywords = [kw for kw in _COMMON_CN_KEYWORDS if kw in jd_text]
    keywords.extend(
        match.group(0)
        for match in _ENGLISH_KEYWORD_RE.finditer(jd_text)
        if _valid_en_keyword(match.group(0))
    )
    return _dedupe(keywords)[:20]


def _valid_en_keyword(keyword: str) -> bool:
    """用于判断英文 token 是否适合作为 JD 关键词。"""
    return len(keyword) >= 2 and keyword.lower() not in _EN_STOPWORDS


def _flatten_value(value: Any) -> str:
    """用于把任意结构化值递归压平成文本。"""
    if isinstance(value, dict):
        return "\n".join(_flatten_value(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_flatten_value(item) for item in value)
    return str(value) if value is not None else ""


def _dedupe(items: list[str]) -> list[str]:
    """用于在保持顺序的前提下去重。"""
    seen: set[str] = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


__all__ = [
    "extract_jd_text",
    "flatten_resume_text",
    "grade_score",
    "iter_bullets",
    "score_resume_rules",
]
