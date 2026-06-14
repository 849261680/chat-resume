"""用于覆盖 Braintrust 真实 Agent eval runner 的任务和评分函数。"""

import pytest

from evals.braintrust_real_dataset import build_braintrust_eval_data
from evals.run_braintrust import (
    _case_id_filtered_data,
    behavior_match_score,
    bullet_quality_score,
    forbidden_claims_score,
    resume_optimization_task,
    resume_final_score,
    rule_quality_score,
)


def test_build_eval_data_maps_real_cases_to_braintrust_rows():
    """用于验证真实 Agent case 会转换成 Braintrust Eval 数据行。"""
    rows = build_braintrust_eval_data([
        {
            "id": "excellent-x",
            "title": "已有事实足够时改写",
            "category": "rewrite_weak_bullet",
            "jd_text": "强调后端接口设计。",
            "user_message": "帮我改得专业一点。",
            "resume": {
                "projects": [
                    {
                        "id": "proj_trade",
                        "name": "校园二手交易平台",
                        "highlights": [{"id": "b1", "text": "写了商品接口"}],
                    }
                ]
            },
            "expected_behavior": {
                "decision": "execute",
                "expected_tool_calls": ["update_bullet"],
                "target": {
                    "section": "projects",
                    "item_id": "proj_trade",
                    "bullet_id": "b1",
                },
            },
            "quality_checks": ["preserve_existing_facts"],
            "expert_rewrite": {
                "section": "projects",
                "item_id": "proj_trade",
                "bullet_id": "b1",
                "text": "基于 Spring Boot 设计商品接口",
            },
            "forbidden_claims": ["Redis"],
            "acceptance": "不能新增 Redis。",
            "anthropic_eval": {"split": "regression"},
        }
    ])

    assert rows == [
        {
            "input": {
                "case_id": "excellent-x",
                "title": "已有事实足够时改写",
                "user_request": "帮我改得专业一点。",
                "resume": {
                    "projects": [
                        {
                            "id": "proj_trade",
                            "name": "校园二手交易平台",
                            "highlights": [{"id": "b1", "text": "写了商品接口"}],
                        }
                    ]
                },
                "jd": {
                    "title": "已有事实足够时改写",
                    "company": "",
                    "description": "强调后端接口设计。",
                },
                "target": {
                    "section": "projects",
                    "item_id": "proj_trade",
                    "bullet_id": "b1",
                },
                "original": "写了商品接口",
            },
            "expected": {
                "expected_decision": "execute",
                "expected_tool_calls": ["update_bullet"],
                "forbidden_claims": ["Redis"],
                "acceptance": "不能新增 Redis。",
                "expert_rewrite": {
                    "section": "projects",
                    "item_id": "proj_trade",
                    "bullet_id": "b1",
                    "text": "基于 Spring Boot 设计商品接口",
                },
            },
            "metadata": {
                "category": "rewrite_weak_bullet",
                "quality_checks": ["preserve_existing_facts"],
                "source": "eval/cases/excellent_resume_agent_cases.json",
                "anthropic_split": "regression",
            },
        }
    ]


@pytest.mark.asyncio
async def test_resume_optimization_task_calls_real_agent_runner(monkeypatch):
    """用于验证 task 通过真实 Agent harness 入口产生输出摘要。"""
    calls = {}

    async def fake_run_agent_target(agent, inputs):
        """用于替代真实模型调用并捕获 task 传入参数。"""
        calls["agent"] = agent
        calls["inputs"] = inputs
        return {
            "agent_reply": "已优化",
            "tool_calls": ["update_bullet"],
            "decision": "execute",
            "elapsed_s": 0.1,
            "resume_after": {
                "projects": [
                    {
                        "id": "proj_trade",
                        "highlights": [{"id": "b1", "text": "优化后的 bullet"}],
                    }
                ]
            },
        }

    monkeypatch.setattr("evals.run_braintrust.build_agent", lambda: object())
    monkeypatch.setattr("evals.run_braintrust.run_agent_target", fake_run_agent_target)

    output = await resume_optimization_task({
        "case_id": "excellent-x",
        "resume": {"projects": []},
        "user_request": "优化亮点",
        "jd": {"title": "后端工程师", "description": "接口设计"},
        "target": {
            "section": "projects",
            "item_id": "proj_trade",
            "bullet_id": "b1",
        },
    })

    assert calls["inputs"]["user_message"] == "优化亮点"
    assert calls["inputs"]["jd"] == {"title": "后端工程师", "description": "接口设计"}
    assert output["optimized_bullet"] == "优化后的 bullet"
    assert output["tool_calls"] == ["update_bullet"]


def test_scores_return_braintrust_score_dicts():
    """用于验证 scorer 返回 Braintrust 可消费的分数字典。"""
    input_row = {
        "case_id": "excellent-x",
        "original": "负责开发",
        "user_request": "优化亮点",
    }
    expected = {
        "expected_decision": "execute",
        "expected_tool_calls": ["update_bullet"],
        "forbidden_claims": ["Redis"],
    }
    output = {
        "optimized_bullet": "主导接口重构，响应时间从 2s 降至 200ms",
        "agent_reply": "已完成优化。",
        "tool_calls": ["update_bullet"],
    }

    scores = [
        rule_quality_score(input_row, output, expected),
        behavior_match_score(input_row, output, expected),
        forbidden_claims_score(input_row, output, expected),
        bullet_quality_score(input_row, output, expected),
    ]

    assert {score["name"] for score in scores} == {
        "Rule quality",
        "Behavior match",
        "Forbidden claims safety",
        "Bullet quality",
    }
    assert all(0.0 <= score["score"] <= 1.0 for score in scores)


def test_bullet_quality_skips_clarify_cases():
    """用于验证澄清类 case 不会被最终 bullet 质量分误伤。"""
    score = bullet_quality_score(
        {"user_request": "帮我量化"},
        {"agent_reply": "你有具体指标吗？", "decision": "clarify"},
        {"expected_decision": "clarify", "expected_tool_calls": []},
    )

    assert score["name"] == "Bullet quality"
    assert score["score"] is None
    assert score["metadata"]["not_applicable"] is True


def test_case_id_filter_selects_requested_rows(monkeypatch):
    """用于验证真实 eval 可以只运行指定 case。"""
    rows = [
        {"input": {"case_id": "excellent-001"}},
        {"input": {"case_id": "excellent-011"}},
    ]
    monkeypatch.setenv("BRAINTRUST_EVAL_CASE_IDS", "excellent-011")

    filtered = _case_id_filtered_data(rows)

    assert filtered == [{"input": {"case_id": "excellent-011"}}]


def test_project_scorer_wrappers_ignore_braintrust_trace_kwarg():
    """用于验证本地 eval wrapper 会忽略 Braintrust 额外 trace 参数。"""
    score = resume_final_score(
        {
            "original": "负责后端接口开发",
            "jd": {"description": "Python FastAPI 性能优化"},
        },
        {
            "optimized_bullet": "设计 Python FastAPI 性能优化方案，将 P99 响应从 2s 降至 200ms",
        },
        {"expected_decision": "execute"},
        trace=object(),
    )

    assert score["name"] == "Resume final score"
    assert 0.0 <= score["score"] <= 1.0
