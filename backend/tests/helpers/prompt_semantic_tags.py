"""语义标签系统：用业务意图标签替代精确字符串断言。

Prompt 每次调整措辞不应导致测试断裂。标签系统定义每个
业务意图对应的关键词集合，只要渲染结果命中任一关键词即通过。
"""

from __future__ import annotations



# ── 语义标签定义 ──────────────────────────────────────────────
# 每个标签 = 业务意图 → 匹配关键词列表（任一命中即通过）
PROMPT_TAGS: dict[str, list[str]] = {
    # 角色定义
    "role_definition": [
        "简历优化智能体",
        "简历优化助手",
        "简历智能体",
    ],
    # 防编造约束
    "no_fabrication": [
        "不得编造",
        "不编造",
        "不得虚构",
        "禁止编造",
        "不得捏造",
    ],
    # 工具调用约束：必须用工具改简历
    "must_use_tools_for_mutations": [
        "需要调用工具时不询问用户",
        "请直接调用",
        "调用工具时不要询问",
    ],
    # 禁止过度优化
    "no_over_optimization": [
        "不要过度优化",
        "不要顺便调",
        "不要动其他条目",
    ],
    # 追问约束：追问原因时文字回复
    "follow_up_text_only": [
        "追问原因时直接文字回复",
        "追问原因时回复文字",
        "用户追问原因",
    ],
    # 不暴露 memory 工具名
    # (用 assertNotIn 检查，不需要标签)
    # Jinja 模板变量残留检查
    # (用 assertNotIn 检查，不需要标签)
    # 工具选择规则
    "tool_selection_rules": [
        "工具选择规则",
        "选择工具时",
        "工具选择优先级",
    ],
    # 简历质量标准
    "quality_standards": [
        "简历质量标准",
        "STAR 法则",
        "质量标准",
    ],
}

# ── Schema 描述标签 ──────────────────────────────────────────
# 用于工具 schema description 的语义检查
SCHEMA_TAGS: dict[str, list[str]] = {
    # update_bullet 的 section 约束
    "bullet_section_constraint": [
        "section 只能是 education",
        "section 限制为 education",
        "section 范围是 education",
    ],
    # update_bullet 的 id 来源约束
    "bullet_id_source": [
        "item_id 和 bullet_id 必须来自当前简历",
        "bullet_id 必须来自当前简历",
    ],
    # update_overview 的 section 约束
    "overview_section_constraint": [
        "section 必须是 projects",
        "section 只能是 projects",
    ],
    # update_item_fields 的 is_current 约束
    "is_current_protected": [
        "不允许修改 is_current",
        "is_current 是内部派生字段",
        "不得修改 is_current",
    ],
    # text 字段的实质差异约束
    "text_must_differ": [
        "有实质差异",
        "存在实质差异",
        "必须与原文有差异",
    ],
    # 不要传入原文
    "no_passthrough": [
        "不要传入原文",
        "不得传入原文",
        "不能传入原文",
    ],
    # reason 不能替代 text 修改
    "reason_not_substitute": [
        "reason 不能替代 text 修改",
        "reason 不是 text 的替代",
        "reason 不替代 text",
    ],
}


def has_tag(text: str, tag: str, *, registry: dict[str, list[str]] | None = None) -> bool:
    """检查文本是否匹配某个语义标签。"""
    source = registry or PROMPT_TAGS
    keywords = source.get(tag)
    if keywords is None:
        raise ValueError(f"Unknown tag: {tag!r}")
    return any(kw in text for kw in keywords)


def assert_tag(text: str, tag: str, *, registry: dict[str, list[str]] | None = None) -> None:
    """断言文本匹配某个语义标签，失败时打印可用关键词。"""
    source = registry or PROMPT_TAGS
    keywords = source.get(tag)
    if keywords is None:
        raise ValueError(f"Unknown tag: {tag!r}")
    if not any(kw in text for kw in keywords):
        raise AssertionError(
            f"Semantic tag {tag!r} not matched.\n"
            f"  Expected one of: {keywords}\n"
            f"  Text preview: {text[:200]}..."
        )


def assert_no_tag(text: str, tag: str, *, registry: dict[str, list[str]] | None = None) -> None:
    """断言文本不匹配某个语义标签。"""
    source = registry or PROMPT_TAGS
    keywords = source.get(tag)
    if keywords is None:
        raise ValueError(f"Unknown tag: {tag!r}")
    matched = [kw for kw in keywords if kw in text]
    if matched:
        raise AssertionError(
            f"Semantic tag {tag!r} should NOT be present, but found: {matched}"
        )


def all_tag_names(*, registry: dict[str, list[str]] | None = None) -> set[str]:
    """返回所有已注册的标签名。"""
    source = registry or PROMPT_TAGS
    return set(source.keys())
