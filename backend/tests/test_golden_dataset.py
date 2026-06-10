"""Golden Dataset 回归测试 — 验证 Agent 在已知样本上的优化效果。

每个用例 = 简历 + JD + 优化后的期望评分区间。
不调用真实 LLM，而是用确定性工具链验证评分回归不劣化。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.agent.resume_rule_score import score_resume_rules  # noqa: E402


# ── Golden Dataset ──────────────────────────────────────────

# 每项: (name, resume, expected_min_score, expected_max_score, rules)
# 评分区间确保回归：如果 refactor 导致评分跌破 expected_min_score 即为回归
GOLDEN_CASES: list[tuple[str, dict[str, Any], float, float, list[str]]] = [
    (
        "空白简历",
        {
            "work_experience": [],
            "projects": [],
            "education": [],
        },
        0.0,
        15.0,
        [],
    ),
    (
        "单条亮点含量化结果",
        {
            "work_experience": [
                {
                    "id": "w1",
                    "company": "某科技",
                    "highlights": [
                        {"id": "h1", "text": "重构核心服务，P99 延迟从 800ms 降到 120ms"},
                    ],
                }
            ],
            "projects": [],
            "education": [],
        },
        50.0,
        85.0,
        ["completeness", "quantification", "expression"],
    ),
    (
        "完整的 STAR 量化简历",
        {
            "personal_info": {"name": "张三"},
            "summary": {"text": "5 年后端工程师"},
            "education": [
                {"id": "e1", "school": "北京大学", "highlights": [{"id": "eh1", "text": "GPA 3.8"}]},
            ],
            "work_experience": [
                {
                    "id": "w1",
                    "company": "某科技",
                    "title": "后端工程师",
                    "highlights": [
                        {"id": "h1", "text": "重构核心服务，P99 延迟从 800ms 降到 120ms"},
                        {"id": "h2", "text": "搭建监控体系，覆盖 30+ 关键链路，故障定位缩短 60%"},
                    ],
                }
            ],
            "projects": [
                {
                    "id": "p1",
                    "name": "增长平台",
                    "highlights": [
                        {"id": "ph1", "text": "设计实时分析管线，支撑日均 1000 万事件"},
                    ],
                }
            ],
            "skills": [{"id": "s1", "category": "后端", "items": ["Python", "FastAPI"]}],
        },
        70.0,
        98.0,
        ["completeness", "quantification", "expression"],
    ),
    (
        "无量化数据的中等简历",
        {
            "work_experience": [
                {
                    "id": "w1",
                    "company": "某科技",
                    "highlights": [
                        {"id": "h1", "text": "负责前端开发"},
                        {"id": "h2", "text": "参与项目迭代"},
                    ],
                }
            ],
            "projects": [{"id": "p1", "name": "后台系统", "highlights": []}],
            "education": [],
        },
        5.0,
        40.0,
        ["completeness", "quantification", "expression"],
    ),
    (
        "所有教育亮点都缺失的简历",
        {
            "work_experience": [
                {
                    "id": "w1",
                    "company": "某公司",
                    "highlights": [
                        {"id": "h1", "text": "重构服务，延迟降低"},
                    ],
                }
            ],
            "projects": [],
            "education": [{"id": "e1", "school": "某大学", "highlights": []}],
        },
        10.0,
        50.0,
        ["completeness", "quantification", "expression"],
    ),
    (
        "单条教育亮点无量化",
        {
            "work_experience": [],
            "projects": [],
            "education": [
                {"id": "e1", "school": "某某大学", "highlights": [{"id": "eh1", "text": "主修计算机科学"}]},
            ],
        },
        0.0,
        20.0,
        ["completeness"],
    ),
    (
        "只有项目经历无工作经历",
        {
            "work_experience": [],
            "projects": [
                {
                    "id": "p1",
                    "name": "开源项目",
                    "highlights": [
                        {"id": "ph1", "text": "开发了一个开源 CLI 工具，GitHub 500+ star"},
                    ],
                }
            ],
            "education": [],
        },
        40.0,
        80.0,
        ["completeness", "quantification"],
    ),
    (
        "技能板块缺失但其他板块完整",
        {
            "personal_info": {"name": "李四", "email": "li@foo.com"},
            "summary": {"text": "3 年全栈工程师，擅长快速迭代"},
            "work_experience": [
                {
                    "id": "w1",
                    "company": "某创业公司",
                    "highlights": [
                        {"id": "h1", "text": "搭建 CI/CD 流水线，部署时间从 2h 缩短到 15min"},
                        {"id": "h2", "text": "重构支付模块，交易成功率从 95% 提升到 99.7%"},
                    ],
                }
            ],
            "projects": [
                {
                    "id": "p1",
                    "name": "内部工具链",
                    "highlights": [
                        {"id": "ph1", "text": "开发自动化测试框架，覆盖 200+ 用例"},
                    ],
                }
            ],
            "education": [
                {"id": "e1", "school": "某工科院校", "highlights": [{"id": "eh1", "text": "GPA 3.6，获校级奖学金"}]},
            ],
        },
        80.0,
        98.0,
        ["completeness", "quantification", "expression"],
    ),
    (
        "多条亮点但无一条含动作动词",
        {
            "work_experience": [
                {
                    "id": "w1",
                    "company": "某公司",
                    "highlights": [
                        {"id": "h1", "text": "前端性能优化到 1 秒以内"},
                        {"id": "h2", "text": "用户增长到 100 万"},
                    ],
                }
            ],
            "projects": [],
            "education": [],
        },
        50.0,
        80.0,
        ["quantification", "expression"],
    ),
    (
        "多板块但全英文表达",
        {
            "personal_info": {"name": "Alice", "email": "a@b.com"},
            "summary": {"text": "Senior engineer with 5 years of experience."},
            "work_experience": [
                {
                    "id": "w1",
                    "company": "Tech Corp",
                    "highlights": [
                        {"id": "h1", "text": "Reduced API latency from 500ms to 50ms"},
                        {"id": "h2", "text": "Migrated monolith to microservices, scaling to 10M DAU"},
                    ],
                }
            ],
            "projects": [
                {"id": "p1", "name": "OSS Tool", "highlights": [{"id": "ph1", "text": "Built CLI tool gaining 1k GitHub stars"}]},
            ],
            "education": [
                {"id": "e1", "school": "Stanford", "highlights": [{"id": "eh1", "text": "M.S. Computer Science, GPA 3.9"}]},
            ],
            "skills": [{"id": "s1", "category": "Backend", "items": ["Go", "Kubernetes", "AWS"]}],
        },
        85.0,
        105.0,
        ["completeness", "quantification", "expression"],
    ),
]


# ── P2: Golden Dataset 评分回归 ───────────────────────────


@pytest.mark.parametrize(
    "name,resume,min_score,max_score,expected_rules",
    GOLDEN_CASES,
    ids=[case[0] for case in GOLDEN_CASES],
)
def test_golden_resume_score_within_expected_range(
    name: str,
    resume: dict[str, Any],
    min_score: float,
    max_score: float,
    expected_rules: list[str],
):
    """Golden 样本评分应在预期区间内，且诊断应包含预期规则。"""
    result = score_resume_rules(resume)

    overall = result["score"]
    assert min_score <= overall <= max_score, (
        f"{name}: score {overall} not in [{min_score}, {max_score}]"
    )

    # 检查维度是否全部存在
    dimensions = result.get("dimensions", [])
    dim_names = {d["key"] for d in dimensions}
    for rule in expected_rules:
        assert rule in dim_names, (
            f"{name}: expected dimension {rule!r} not found in {dim_names}"
        )

    # 整体分数应与维度汇总一致
    total_weight = sum(d.get("max", 0) for d in dimensions)
    total_score = sum(d.get("score", 0) for d in dimensions)
    assert abs(total_score - overall) < 1.0, (
        f"{name}: score mismatch: dims={total_score}, overall={overall}"
    )
    assert total_weight > 0, f"{name}: total weight must be positive"

    # 单维度得分应在合理范围内
    for dim in dimensions:
        assert 0 <= dim["score"] <= dim["max"] + 0.1, (
            f"{name}: dim {dim['key']} score {dim['score']} exceeds max {dim['max']}"
        )
