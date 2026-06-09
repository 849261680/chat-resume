"""用于让 LLM 以招聘经理视角评价单条简历要点。"""

from __future__ import annotations
import json
import logging
from typing import Any

from app.prompts.loader import load_prompt
from app.services.llm.chat_service import ChatService

from .shared import (
    HIGHLIGHT_SECTIONS,
    SECTION_NAMES,
    find_item,
    summarize_dict,
)

logger = logging.getLogger(__name__)


async def evaluate_bullet(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    bullet_id: str,
) -> dict[str, Any]:
    """用于调用 LLM 对一条 bullet 做多维度评价，只读不改简历。"""
    # 定位 bullet
    if section not in HIGHLIGHT_SECTIONS:
        return {"success": False, "message": f"{section} 不支持要点评价"}

    items, idx = find_item(resume_content, section, item_id)
    if items is None or idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    highlights = items[idx].get("highlights") or []
    bullet_text = ""
    for highlight in highlights:
        if str(highlight.get("id")) == str(bullet_id):
            bullet_text = str(highlight.get("text") or "").strip()
            break

    if not bullet_text:
        return {"success": False, "message": f"未找到 id={bullet_id} 的要点"}

    # 构建上下文
    section_name = SECTION_NAMES.get(section, section)
    item_summary = summarize_dict(items[idx])

    # 读取 JD（如果有）
    from app.services.agent.resume_rule_score import extract_jd_text

    jd_text = extract_jd_text(resume_content)
    jd_context = jd_text[:500] if jd_text else "（未提供）"

    # 渲染 prompt
    spec = load_prompt("bullet_judge")
    system_prompt = spec.render(
        section_name=section_name,
        item_summary=item_summary,
        jd_context=jd_context,
        bullet_text=bullet_text,
    )

    # 调用 LLM
    async with ChatService() as chat:
        response = await chat.chat_completion(
            messages=[{"role": "user", "content": "请评价这条要点"}],
            temperature=spec.model_defaults.get("temperature", 0.3),
            max_tokens=spec.model_defaults.get("max_tokens", 800),
            stream=False,
            system_prompt=system_prompt,
        )

    content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
    evaluation = _parse_evaluation(content)

    return {
        "success": True,
        "message": f"已完成要点评价，综合得分 {evaluation.get('score', '?')} 分",
        "bullet_text": bullet_text,
        "location": {
            "section": section,
            "item_id": item_id,
            "bullet_id": bullet_id,
        },
        **evaluation,
    }


def _parse_evaluation(raw: str) -> dict[str, Any]:
    """用于从 LLM 返回文本中提取 JSON 评价结果。"""
    # 尝试提取 JSON 块
    text = raw.strip()
    # 去掉 markdown 代码块标记
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM 评价结果不是有效 JSON: %s", text[:200])
        return {
            "score": 0,
            "grade": "F",
            "checks": {},
            "summary": "LLM 评价结果解析失败",
            "suggestions": [],
        }

    return {
        "score": int(result.get("score", 0)),
        "grade": str(result.get("grade", "F")),
        "checks": result.get("checks", {}),
        "summary": str(result.get("summary", "")),
        "suggestions": result.get("suggestions", []),
    }


__all__ = ["evaluate_bullet"]
