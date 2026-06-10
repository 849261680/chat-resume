"""LLM-as-Judge 质量评估框架的单元测试。"""

from __future__ import annotations

import pytest

from app.services.agent.quality_judge import (
    judge_agent_output,
    judge_bullet_quality,
    judge_output_safety,
    judge_tool_call_relevance,
)


class TestToolCallRelevance:
    def test_add_intent_matches_add_bullet(self):
        dim = judge_tool_call_relevance(
            "帮我新增一条亮点",
            "add_bullet",
            {},
        )
        assert dim.passed

    def test_add_intent_mismatched_with_update_bullet(self):
        dim = judge_tool_call_relevance(
            "帮我新增一条亮点",
            "update_bullet",
            {},
        )
        assert not dim.passed
        assert len(dim.findings) >= 1

    def test_modify_intent_matches_update_bullet(self):
        dim = judge_tool_call_relevance(
            "帮我优化这条亮点",
            "update_bullet",
            {},
        )
        assert dim.passed

    def test_delete_intent_matches_remove_bullet(self):
        dim = judge_tool_call_relevance(
            "删掉这条亮点",
            "remove_bullet",
            {},
        )
        assert dim.passed

    def test_non_bullet_tool_not_flagged(self):
        dim = judge_tool_call_relevance(
            "帮我优化这条亮点",
            "update_summary",
            {},
        )
        assert dim.passed


class TestOutputSafety:
    def test_safe_text_passes(self):
        dim = judge_output_safety("已完成简历优化，将首屏加载提速从 3s 优化到 1.2s。")
        assert dim.passed

    def test_uncertain_expression_flagged(self):
        dim = judge_output_safety("根据我的理解，应该是前端性能瓶颈导致了加载慢。")
        assert not dim.passed
        assert any("应该是" in f for f in dim.findings)

    def test_fabrication_salary_flagged(self):
        dim = judge_output_safety("目前市场年薪大约 30 万左右。")
        assert not dim.passed


class TestBulletQuality:
    def test_quantified_star_bullet_scores_high(self):
        dim = judge_bullet_quality(
            "主导前端架构重构，将首屏加载时间从 3s 优化到 1.2s，提速 60%"
        )
        assert dim.score >= 70

    def test_non_quantified_bullet_scores_lower(self):
        dim = judge_bullet_quality("负责前端开发")
        assert dim.score < 70
        assert any("缺少量化" in f for f in dim.findings)

    def test_no_action_verb_bullet(self):
        dim = judge_bullet_quality("前端性能提升了 30%")
        assert not dim.passed


class TestAgentOutputJudgment:
    def test_empty_output_passes(self):
        result = judge_agent_output(
            user_message="简历怎么写？",
            tool_calls=None,
            final_text="建议清晰说明个人优势。",
        )
        assert result.passed

    def test_tool_mismatch_lowers_score(self):
        result = judge_agent_output(
            user_message="帮我新增一条亮点",
            tool_calls=[{
                "name": "update_bullet",
                "arguments": {"section": "work_experience", "item_id": "w1", "bullet_id": "h1", "text": "abc"},
            }],
            final_text="已完成。",
        )
        assert result.overall_score < 90

    def test_safe_output_with_correct_tool_scores_high(self):
        result = judge_agent_output(
            user_message="优化工作经历的亮点",
            tool_calls=[{
                "name": "update_bullet",
                "arguments": {
                    "section": "work_experience",
                    "item_id": "w1",
                    "bullet_id": "h1",
                    "text": "主导架构重构，P99 延迟从 800ms 降至 120ms",
                },
            }],
            final_text="已完成优化。",
        )
        assert result.overall_score >= 70
