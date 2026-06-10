"""基于真实 LLM 的 Agent 输出质量评判。

用 LLM 给 Agent 输出打多维度分数，补充纯规则引擎盲区。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.services.llm.chat_service import ChatService

logger = logging.getLogger(__name__)


# ── 评判维度 ────────────────────────────────────────────────

@dataclass
class LLDimension:
    """LLM 评判的单个维度。"""

    name: str
    score: float  # 0-5
    max_score: int = 5
    reasoning: str = ""


@dataclass
class LLMJudgment:
    """LLM 综合评判结果。"""

    dimensions: list[LLDimension]
    overall_score: float  # 0-100
    passed: bool
    summary: str


# ── Judge Prompt ─────────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """你是简历优化 Agent 的评判专家。你会收到一个优化任务：用户要求优化一条简历亮点，Agent 给出了优化后的文本。
**你会同时看到原文和优化后的文本，请不要孤立判断优化结果。**

判断标准（每项 1-5 分，5=优秀）：

1. **准确性** — 优化后的内容是否基于原文展开？有没有凭空编造原文中不存在的事实？（1=完全编造，5=完全基于原文合理扩展）
2. **量化程度** — 是否补充了具体的数字、百分比、规模？量化是否合理可信？（1=纯定性无数字，5=每条都有合理的量化）
3. **STAR 遵循度** — 是否体现了情境-任务-动作-结果结构？（1=完全没有，5=每条都完整）
4. **安全性** — 是否避免了明显虚假的数据（如百万分之一毫秒、七个9的可用性等）？（1=明显编造，5=完全可信）
5. **简洁性** — 回复是否精炼、不冗余？（1=啰嗦冗长，5=精准简练）

**重要说明**：补充量化数据（如"从3s降到1s"）是简历优化的正常行为，不是编造。只有当数字明显不合理（如0.01ms、99.99999%）或职务/规模明显虚增时才扣分。

用 JSON 格式返回，不要任何其他文字：
{
  "dimensions": [
    {"name": "准确性", "score": 4, "reasoning": "基于原文扩展了具体数字，都在合理范围内"},
    {"name": "量化程度", "score": 2, "reasoning": ""},
    {"name": "STAR遵循度", "score": 3, "reasoning": ""},
    {"name": "安全性", "score": 5, "reasoning": ""},
    {"name": "简洁性", "score": 4, "reasoning": ""}
  ],
  "overall_summary": "整体评价"
}
"""


# ── Judge 调用 ──────────────────────────────────────────────


async def judge_with_llm(
    user_message: str,
    agent_response: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    timeout_seconds: float = 30.0,
) -> LLMJudgment:
    """用 LLM 评判 Agent 输出质量。"""

    judge_prompt = f"""用户请求：
{user_message}

Agent 回复：
{agent_response}

请按照评判标准打分，只返回 JSON。"""

    async with ChatService(
        model=model,
        api_key=api_key,
        api_base=api_base,
    ) as service:
        response = await service.chat_completion(
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": judge_prompt},
            ],
        )

    return _parse_judgment(
        response["choices"][0]["message"]["content"]
    )


def _parse_judgment(raw_text: str) -> LLMJudgment:
    """解析 LLM 返回的评判 JSON。"""
    # 处理可能的 markdown 包裹
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse LLM judge response as JSON: {text[:200]}")
        # 兜底：给最低分
        return LLMJudgment(
            dimensions=[
                LLDimension(name=n, score=3, reasoning="JSON 解析失败")
                for n in ["准确性", "量化程度", "STAR遵循度", "安全性", "简洁性"]
            ],
            overall_score=60.0,
            passed=False,
            summary="评判解析失败",
        )

    dimensions = [
        LLDimension(
            name=d["name"],
            score=float(d.get("score", 3)),
            reasoning=d.get("reasoning", ""),
        )
        for d in data.get("dimensions", [])
        if isinstance(d, dict)
    ]

    if not dimensions:
        dimensions = [
            LLDimension(name=n, score=3, reasoning="")
            for n in ["准确性", "量化程度", "STAR遵循度", "安全性", "简洁性"]
        ]

    # 加权：准确性和安全性权重 ×2，量化程度 ×0.5
    weighted = 0.0
    weighted_max = 0.0
    for d in dimensions:
        if d.name == "准确性" or d.name == "安全性":
            w = 2.0
        elif d.name == "量化程度":
            w = 0.5
        else:
            w = 1.0
        weighted += d.score * w
        weighted_max += d.max_score * w
    overall = round(weighted / weighted_max * 100, 1)
    summary = data.get("overall_summary", "")

    return LLMJudgment(
        dimensions=dimensions,
        overall_score=overall,
        passed=overall >= 60.0,
        summary=summary,
    )


# ── 综合评判（规则 + LLM）──────────────────────────────────


async def full_judge(
    user_message: str,
    agent_response: str,
    tool_calls: list[dict[str, Any]] | None = None,
    *,
    model: str | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """综合评判：规则引擎 + LLM 双通道。"""
    from app.services.agent.quality_judge import judge_agent_output, judge_bullet_quality

    # 规则通道
    rule_judgment = judge_agent_output(
        user_message=user_message,
        tool_calls=tool_calls,
        final_text=agent_response,
        pass_threshold=70.0,
    )

    # LLM 通道
    try:
        llm_judgment = await judge_with_llm(
            user_message=user_message,
            agent_response=agent_response,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        logger.warning(f"LLM judge failed, falling back to rules: {exc}")
        llm_judgment = None

    # 合并
    result: dict[str, Any] = {
        "rule_score": rule_judgment.overall_score,
        "rule_dimensions": [
            {"name": d.name, "score": d.score, "passed": d.passed}
            for d in rule_judgment.dimensions
        ],
    }

    if llm_judgment:
        result["llm_score"] = llm_judgment.overall_score
        result["llm_dimensions"] = [
            {"name": d.name, "score": d.score, "reasoning": d.reasoning}
            for d in llm_judgment.dimensions
        ]
        result["llm_summary"] = llm_judgment.summary
        # 综合分 = 规则 30% + LLM 70%
        result["combined_score"] = round(
            rule_judgment.overall_score * 0.3 + llm_judgment.overall_score * 0.7, 1
        )
    else:
        result["combined_score"] = rule_judgment.overall_score

    result["passed"] = result["combined_score"] >= 70.0
    return result
