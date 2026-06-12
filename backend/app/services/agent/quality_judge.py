"""LLM-as-Judge 质量评估框架。

对 Agent 输出进行自动化质量评判，无需人工评审。
基于业务规则 + 结构分析（不调用真实 LLM）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityDimension:
    """单个质量维度的评判结果。"""

    name: str
    score: float  # 0-100
    max_score: float
    passed: bool
    findings: list[str] = field(default_factory=list)


@dataclass
class QualityJudgment:
    """LLM-as-Judge 综合评判结果。"""

    overall_score: float
    pass_threshold: float
    passed: bool
    dimensions: list[QualityDimension]
    summary: str = ""


# ── 评判规则 ────────────────────────────────────────────────


def judge_tool_call_relevance(
    user_message: str,
    tool_call_name: str,
    _tool_call_args: dict[str, Any],
) -> QualityDimension:
    """评判工具调用是否与用户意图匹配。"""
    findings: list[str] = []

    # 新增 vs 修改识别
    add_keywords = ["新增", "补充", "添加", "加一条", "加一个"]
    modify_keywords = ["优化", "改写", "重写", "修改", "改一下"]
    delete_keywords = ["删除", "去掉", "移除", "删掉"]

    user_wants_add = any(kw in user_message for kw in add_keywords)
    user_wants_modify = any(kw in user_message for kw in modify_keywords)
    user_wants_delete = any(kw in user_message for kw in delete_keywords)

    is_add_tool = tool_call_name == "add_bullet"
    is_modify_tool = tool_call_name == "update_bullet"
    is_delete_tool = tool_call_name == "remove_bullet"
    is_bullet_tool = is_add_tool or is_modify_tool or is_delete_tool

    if user_wants_add and not is_add_tool and is_bullet_tool:
        findings.append(f"用户要求新增，但调用了 {tool_call_name} 而非 add_bullet")
    if user_wants_modify and not is_modify_tool and is_bullet_tool:
        findings.append(f"用户要求修改，但调用了 {tool_call_name} 而非 update_bullet")
    if user_wants_delete and not is_delete_tool and is_bullet_tool:
        findings.append(f"用户要求删除，但调用了 {tool_call_name} 而非 remove_bullet")

    score = 100.0 - len(findings) * 25.0
    return QualityDimension(
        name="工具选择正确性",
        score=max(0.0, score),
        max_score=100.0,
        passed=len(findings) == 0,
        findings=findings,
    )


def judge_tool_args_completeness(
    tool_name: str,
    tool_args: dict[str, Any],
    required_params: list[str],
) -> QualityDimension:
    """评判工具参数是否完整有效。"""
    findings: list[str] = []

    for param in required_params:
        if param not in tool_args or not tool_args[param]:
            findings.append(f"缺少必填参数: {param}")

    # text 参数检查
    if "text" in tool_args and tool_args["text"]:
        text = str(tool_args["text"])
        if len(text) < 5:
            findings.append("text 参数过短 (< 5 字符)")
        if len(text) > 500:
            findings.append("text 参数过长 (> 500 字符)")

    score = 100.0 - len(findings) * 30.0
    return QualityDimension(
        name="参数完整性",
        score=max(0.0, score),
        max_score=100.0,
        passed=len(findings) == 0,
        findings=findings,
    )


def judge_output_safety(text: str) -> QualityDimension:
    """评判 Agent 输出是否安全（不编造、不幻觉）。"""
    findings: list[str] = []

    fabrication_signals = [
        "我相信",
        "应该是",
        "可能是",
        "估计是",
        "大概是",
        "据悉",
        "据了解",
    ]
    for signal in fabrication_signals:
        if signal in text:
            findings.append(f"包含不确定表述: '{signal}'")

    # 检查是否有编造的迹象
    if "年薪" in text and "万" in text:
        findings.append("可能编造了薪资信息")

    score = 100.0 - len(findings) * 20.0
    return QualityDimension(
        name="输出安全性",
        score=max(0.0, score),
        max_score=100.0,
        passed=len(findings) == 0,
        findings=findings,
    )


def judge_bullet_quality(text: str) -> QualityDimension:
    """评判优化后的 bullet 文本质量。"""
    findings: list[str] = []

    # 量化检查
    has_number = any(c.isdigit() for c in text)
    has_percent = "%" in text or "倍" in text
    if not has_number:
        findings.append("缺少量化数据")

    # 长度检查
    if len(text) < 10:
        findings.append("bullet 文本过短")
    if len(text) > 200:
        findings.append("bullet 文本过长")

    # STAR 元素检查
    action_verbs = [
        "设计", "搭建", "推动", "重构", "优化", "主导",
        "实现", "构建", "开发", "建立", "制定", "管理",
    ]
    has_action = any(verb in text for verb in action_verbs)
    if not has_action:
        findings.append("缺少动作动词（STAR 的 Action）")

    score = 100.0
    if not has_number:
        score -= 30
    if not has_action:
        score -= 20
    if len(text) < 10:
        score -= 20
    if has_percent:
        score += 5  # bonus for quantified result

    return QualityDimension(
        name="Bullet 质量",
        score=min(100.0, max(0.0, score)),
        max_score=100.0,
        passed=len(findings) == 0,
        findings=findings,
    )


# ── 综合评判 ──────────────────────────────────────────────


def judge_agent_output(
    *,
    user_message: str,
    tool_calls: list[dict[str, Any]] | None = None,
    final_text: str = "",
    pass_threshold: float = 70.0,
) -> QualityJudgment:
    """对一次 Agent 交互进行综合质量评判。"""
    dimensions: list[QualityDimension] = []

    # 工具选择评判
    if tool_calls:
        for tc in tool_calls:
            dim = judge_tool_call_relevance(
                user_message,
                tc.get("name", tc.get("tool_name", "")),
                tc.get("arguments", {}),
            )
            dimensions.append(dim)

    # 输出安全评判
    if final_text:
        dimensions.append(judge_output_safety(final_text))

    # Bullet 质量评判（如果输出包含优化后的文本）
    if tool_calls and final_text:
        for tc in tool_calls:
            args = tc.get("arguments", {})
            if "text" in args:
                dimensions.append(judge_bullet_quality(str(args["text"])))
                break

    if not dimensions:
        dimensions.append(QualityDimension(
            name="无评判",
            score=100.0,
            max_score=100.0,
            passed=True,
        ))

    total_score = sum(d.score for d in dimensions)
    total_max = sum(d.max_score for d in dimensions)
    overall = (total_score / total_max * 100) if total_max > 0 else 100.0

    return QualityJudgment(
        overall_score=round(overall, 1),
        pass_threshold=pass_threshold,
        passed=overall >= pass_threshold,
        dimensions=dimensions,
        summary=f"{len([d for d in dimensions if d.passed])}/{len(dimensions)} 维度通过",
    )
