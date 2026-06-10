"""ELO 对比框架单元测试。"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.agent.elo_comparison import (
    ComparisonCase,
    ci_gate,
    expected_score,
    run_comparison,
    update_elo,
    update_elo_draw,
)
from app.services.agent.resume_rule_score import score_resume_rules


class TestEloAlgorithm:
    def test_equal_ratings_equal_chance(self):
        assert expected_score(1500, 1500) == pytest.approx(0.5)

    def test_higher_rating_higher_expected(self):
        assert expected_score(1600, 1500) > 0.5

    def test_winner_gains_points(self):
        new_w, new_l = update_elo(1500, 1500)
        assert new_w > 1500
        assert new_l < 1500
        assert new_w + new_l == pytest.approx(3000)

    def test_draw_conserves_total(self):
        new_a, new_b = update_elo_draw(1500, 1500)
        assert new_a == pytest.approx(1500)
        assert new_b == pytest.approx(1500)
        assert new_a + new_b == pytest.approx(3000)


_SIMPLE_CASES = [
    ComparisonCase(
        name="empty",
        input_data={"work_experience": [], "projects": [], "education": []},
        scorer=score_resume_rules,
    ),
    ComparisonCase(
        name="basic",
        input_data={
            "work_experience": [
                {
                    "id": "w1",
                    "company": "某公司",
                    "highlights": [
                        {"id": "h1", "text": "重构服务，P99 延迟从 800ms 降到 120ms"},
                    ],
                }
            ],
            "projects": [],
            "education": [],
        },
        scorer=score_resume_rules,
    ),
]


class TestEloComparison:
    def test_run_comparison_produces_report(self):
        report = run_comparison("v1", "v2", _SIMPLE_CASES)
        assert report.version_a.version_name == "v1"
        assert report.version_b.version_name == "v2"
        assert len(report.version_a.scores) == len(_SIMPLE_CASES)
        assert len(report.version_b.scores) == len(_SIMPLE_CASES)

    def test_same_version_draws(self):
        """同一评分器对比自己应全平。"""
        report = run_comparison("v1", "v1", _SIMPLE_CASES)
        assert report.winner == "不明确"
        assert report.version_a.draw_count == len(_SIMPLE_CASES)

    def test_ci_gate_passes_for_same_version(self):
        report = run_comparison("v1", "v1", _SIMPLE_CASES)
        assert ci_gate(report) is True

    def test_elo_updates_accumulate_across_cases(self):
        """ELO 应在多轮对比中累积变化。"""
        many_cases = _SIMPLE_CASES * 5  # 10 cases
        report = run_comparison("v1", "v1", many_cases)
        # 同版本对比 ELO 应保持在初始值附近
        assert abs(report.version_a.elo - 1500) < 50
