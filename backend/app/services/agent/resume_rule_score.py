"""用于提供简历评分的确定性规则检查层。"""

from __future__ import annotations

import re
from typing import Any, Iterator

# 规则评分维度的基础权重,无 JD 时 jd_match 会被剔除并按比例归一到 100。
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
# 弱动词后面紧跟强动词的最大间距（弱动词长度+间隔）
_WEAK_STRONG_MAX_GAP = 6
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

# 同义词组:每组内的任一关键词命中视为全部命中。
_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("微服务", "Microservice", "microservice", "服务拆分", "服务化"),
    ("高并发", "High Concurrency", "大并发", "高吞吐"),
    ("性能优化", "Performance Optimization", "性能调优", "调优"),
    ("前端", "Frontend", "frontend", "Web 前端"),
    ("后端", "Backend", "backend", "服务端"),
    ("消息队列", "Message Queue", "MQ", "消息中间件", "Kafka", "RabbitMQ"),
    ("向量数据库", "Vector Database", "向量检索", "向量存储"),
    ("检索增强", "RAG", "Retrieval Augmented"),
    ("可观测", "Observability", "监控", "可观测性", "链路追踪"),
    ("机器学习", "Machine Learning", "ML"),
    ("深度学习", "Deep Learning", "DL", "神经网络"),
    ("数据分析", "Data Analysis", "数据分析"),
    ("推荐系统", "Recommendation System", "推荐引擎", "推荐算法"),
    ("系统设计", "System Design", "架构设计", "架构"),
    ("工作流", "Workflow", "工作流引擎", "流程引擎"),
    ("Agent", "AI Agent", "智能体"),
    ("项目管理", "Project Management"),
    ("团队协作", "Team Collaboration"),
    ("全栈", "Full Stack", "fullstack", "full-stack"),
)

# JD 中暗示必需技能的句式模式
_REQUIRED_PATTERNS = re.compile(
    r"(必须|要求|需要|必备|required|must have|essential|mandatory)",
    re.IGNORECASE,
)
_PREFERRED_PATTERNS = re.compile(
    r"(优先|加分|nice to have|preferred|plus|bonus|preferred)",
    re.IGNORECASE,
)
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
    """用于遍历经历板块下的 bullet,产出板块、条目 id、bullet id 和文本。"""
    for section in _BULLET_SECTIONS:
        for item in resume_content.get(section) or []:
            item_id = str(item.get("id", ""))
            yield from _iter_item_bullets(section, item_id, item)


def flatten_resume_text(resume_content: dict[str, Any]) -> str:
    """用于把简历正文(排除 JD)压平成可搜索文本。"""
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
        (bool(str(summary).strip()), "缺少个人总结", "补充 2-4 句个人总结,突出核心优势"),
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
            "suggestion": "补充可量化的影响,如提升 X%、覆盖 N 用户、缩短到 M 秒",
        }
        for section, item_id, bullet_id, text in bullets
        if not _NUMBER_RE.search(text)
    ]
    ratio = (len(bullets) - len(findings)) / len(bullets)
    return {"key": "quantification", "ratio": ratio, "findings": findings[:6]}


def _score_expression(resume_content: dict[str, Any]) -> dict[str, Any]:
    """用于衡量 bullet 表达的结构完整性、动词强度和用词精准度。"""
    bullets = list(iter_bullets(resume_content))
    if not bullets:
        return {"key": "expression", "ratio": 0.0, "findings": []}
    findings = []
    for section, item_id, bullet_id, text in bullets:
        issues = _expression_issues(text)
        if issues:
            findings.append({
                "section": section,
                "item_id": item_id,
                "bullet_id": bullet_id,
                "issue": issues[0],
                "suggestion": _expression_suggestion(issues),
            })
    ratio = (len(bullets) - len(findings)) / len(bullets)
    return {"key": "expression", "ratio": ratio, "findings": findings[:6]}


def _score_jd_match(resume_content: dict[str, Any], jd_text: str) -> dict[str, Any]:
    """用于按同义词感知、权重化的关键词匹配率衡量简历与 JD 的匹配度。"""
    keywords = _extract_jd_keywords(jd_text)
    if not keywords:
        return {"key": "jd_match", "ratio": 0.0, "findings": []}
    resume_text = flatten_resume_text(resume_content).lower()
    synonym_index = _build_synonym_index()
    weighted_hits = 0.0
    total_weight = 0.0
    missing: list[dict[str, Any]] = []
    for entry in keywords:
        keyword = entry["keyword"]
        weight = entry["weight"]
        total_weight += weight
        if _keyword_matches_resume(keyword, resume_text, synonym_index):
            weighted_hits += weight
        else:
            missing.append({
                "issue": f"JD 关键词「{keyword}」未在简历中体现",
                "suggestion": f"如有真实经历,补充与「{keyword}」相关的事实和结果",
                "missing_keyword": keyword,
                "weight": weight,
            })
    ratio = weighted_hits / total_weight if total_weight else 0.0
    missing.sort(key=lambda m: m["weight"], reverse=True)
    findings = missing[:6]
    return {"key": "jd_match", "ratio": ratio, "findings": findings}


def _has_contact(personal: dict[str, Any]) -> bool:
    """用于判断个人信息里是否存在联系方式。"""
    email = str(personal.get("email", "")).strip()
    phone = str(personal.get("phone", "")).strip()
    return bool(email or phone)


def _expression_issues(text: str) -> list[str]:
    """用于返回单条 bullet 的全部表达问题,无问题时返回空列表。"""
    stripped = text.strip()
    issues: list[str] = []
    # 长度检查
    if len(stripped) < 8:
        issues.append("要点过短,信息量不足")
        return issues
    if len(stripped) > 150:
        issues.append("要点过长,建议拆分为多条")
    # 弱动词开头:只有弱动词后面没有具体方案和结果时才扣分
    if stripped.startswith(_WEAK_PREFIXES) and not _has_concrete_result(stripped):
        issues.append("以弱动词开头且缺少具体方案或结果")
    # 结构检查:是否包含动作和结果两层信息
    if not _has_structure(stripped):
        issues.append("缺少「动作→结果」结构,像职责描述而非成果证据")
    # 空洞修饰检查
    if _has_hollow_modifier(stripped):
        issues.append('包含空洞修饰(如"显著提升""大幅优化"),缺少具体数据支撑')
    return issues


def _expression_suggestion(issues: list[str]) -> str:
    """用于根据具体问题给出针对性建议。"""
    for issue in issues:
        if "弱动词" in issue:
            return "用强动作动词(设计/搭建/推动/重构)开头,或补充具体方案和结果"
        if "结构" in issue:
            return "改成「做了什么→怎么做的→结果如何」的结构"
        if "空洞" in issue:
            return '把空洞修饰替换成具体数字,如"提升40%""缩短到200ms"'
        if "过长" in issue:
            return "拆成多条,每条聚焦一个成果"
    return "用强动作动词开头,说清任务-方案-结果"


# 强动作动词:出现任何一个说明 bullet 有具体的行动内容
_STRONG_ACTION_WORDS = (
    "设计", "搭建", "推动", "重构", "实现", "开发", "优化", "构建",
    "建立", "改造", "落地", "迁移", "替换", "解决", "修复", "编写",
    "提出", "主导", "独立", "创建", "部署", "上线", "发布",
)

# 结果连接词:出现说明有动作→结果的过渡
_RESULT_CONNECTORS = (
    ",将", ",使", ",让", ",从", ",到", "降至", "升到", "提升",
    "降低", "缩短", "减少", "增长", "覆盖", "支撑", "节省", "节省",
    ",满足", ",实现", ",达到", ",解决", ",消除", ",避免",
)

# 空洞修饰:有数字修饰的形容词不算空洞
_HOLLOW_MODIFIERS = (
    "显著提升", "大幅优化", "明显改善", "有效提高", "极大提升",
    "大幅提高", "显著降低", "大幅下降", "全面提升", "全面优化",
    "极大改善", "明显提升", "有效解决", "大幅减少",
)


def _has_concrete_result(text: str) -> bool:
    """用于判断弱动词开头的 bullet 是否包含具体方案和结果。"""
    # 必须有数字或结果连接词才算有具体结果
    has_number = bool(_NUMBER_RE.search(text))
    has_result_connector = any(conn in text for conn in _RESULT_CONNECTORS)
    if has_number or has_result_connector:
        return True
    # 弱动词后面紧跟强动词+技术方案描述（超过 15 字），说明内容足够具体
    for prefix in _WEAK_PREFIXES:
        if text.startswith(prefix):
            rest = text[len(prefix):]
            for action in _STRONG_ACTION_WORDS:
                idx = rest.find(action)
                if 0 <= idx <= _WEAK_STRONG_MAX_GAP and len(text) >= 12:
                    return True
            break
    return False


def _has_structure(text: str) -> bool:
    """用于判断 bullet 是否包含动作→结果的结构。"""
    has_action = any(word in text for word in _STRONG_ACTION_WORDS)
    has_result = any(conn in text for conn in _RESULT_CONNECTORS) or bool(
        _NUMBER_RE.search(text)
    )
    return has_action or has_result


def _has_hollow_modifier(text: str) -> bool:
    """用于判断是否包含无数据支撑的空洞修饰。"""
    for modifier in _HOLLOW_MODIFIERS:
        if modifier not in text:
            continue
        # 只要整个 bullet 里任何位置有数字,就不算空洞
        if _NUMBER_RE.search(text):
            return False
        return True
    return False


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


def _extract_jd_keywords(jd_text: str) -> list[dict[str, Any]]:
    """用于从 JD 中提取带权重的关键词,最多 20 个。"""
    keywords: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for kw in _COMMON_CN_KEYWORDS:
        if kw in jd_text and kw not in seen_names:
            seen_names.add(kw)
            keywords.append({
                "keyword": kw,
                "weight": _infer_keyword_weight(kw, jd_text),
            })
    for match in _ENGLISH_KEYWORD_RE.finditer(jd_text):
        token = match.group(0)
        if _valid_en_keyword(token) and token not in seen_names:
            seen_names.add(token)
            keywords.append({
                "keyword": token,
                "weight": _infer_keyword_weight(token, jd_text),
            })
    return _dedupe_keywords(keywords)[:20]


def _infer_keyword_weight(keyword: str, jd_text: str) -> float:
    """用于根据 JD 子句上下文推断关键词权重。必需=2.0,普通=1.0,加分=0.5。"""
    pos = jd_text.lower().find(keyword.lower())
    if pos < 0:
        return 1.0
    # 向前回溯到最近的子句分隔符
    sentence_start = 0
    for sep in ("。", "\n", "；", "，", ";", "•", "·", ","):
        idx = jd_text.rfind(sep, 0, pos)
        if idx >= 0:
            sentence_start = max(sentence_start, idx + 1)
    # 向后到最近的子句分隔符
    kw_end = pos + len(keyword)
    sentence_end = len(jd_text)
    for sep in ("。", "\n", "；", "，", ";", "•", "·", ","):
        idx = jd_text.find(sep, kw_end)
        if idx >= 0:
            sentence_end = min(sentence_end, idx)
    clause = jd_text[sentence_start:sentence_end]
    # 优先判断加分,再判断必需
    if _PREFERRED_PATTERNS.search(clause):
        return 0.5
    if _REQUIRED_PATTERNS.search(clause):
        return 2.0
    return 1.0


def _build_synonym_index() -> dict[str, set[str]]:
    """用于构建关键词到同义词集合的映射。"""
    index: dict[str, set[str]] = {}
    for group in _SYNONYM_GROUPS:
        lowered = {member.lower() for member in group}
        for member in group:
            index[member.lower()] = lowered
    return index


def _keyword_matches_resume(
    keyword: str,
    resume_text: str,
    synonym_index: dict[str, set[str]],
) -> bool:
    """用于判断关键词(含同义词)是否在简历文本中命中。"""
    if keyword.lower() in resume_text:
        return True
    synonyms = synonym_index.get(keyword.lower())
    if synonyms is None:
        return False
    return any(syn in resume_text for syn in synonyms)


def _dedupe_keywords(keywords: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用于按关键词去重,保留权重最高的条目。"""
    best: dict[str, dict[str, Any]] = {}
    for entry in keywords:
        key = entry["keyword"].lower()
        if key not in best or entry["weight"] > best[key]["weight"]:
            best[key] = entry
    return list(best.values())


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
