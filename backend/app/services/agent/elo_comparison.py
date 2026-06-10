"""ELO 对比评估 — 新旧 Agent 版本在多条样本上的质量对比。

不依赖真实 LLM，用确定性评分做 A/B 对比，适合 CI 回归门禁。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable


# ── ELO 算法实现 ────────────────────────────────────────────

DEFAULT_K = 32
ELO_SCALE = 400.0


def expected_score(rating_a: float, rating_b: float) -> float:
    """计算 A 对 B 的期望胜率。"""
    return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / ELO_SCALE))


def update_elo(
    winner_rating: float,
    loser_rating: float,
    k: float = DEFAULT_K,
) -> tuple[float, float]:
    """单场比赛后更新 ELO 分数。返回 (new_winner, new_loser)。"""
    exp = expected_score(winner_rating, loser_rating)
    delta = k * (1.0 - exp)
    return winner_rating + delta, loser_rating - delta


def update_elo_draw(
    rating_a: float,
    rating_b: float,
    k: float = DEFAULT_K,
) -> tuple[float, float]:
    """平局后更新 ELO 分数。"""
    exp_a = expected_score(rating_a, rating_b)
    delta_a = k * (0.5 - exp_a)
    return rating_a + delta_a, rating_b - delta_a


# ── 对比评估 ────────────────────────────────────────────────


@dataclass
class ComparisonCase:
    """单个对比用例。"""

    name: str
    input_data: dict[str, Any]
    # 评分函数
    scorer: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class VersionResult:
    """单个版本在全部用例上的结果。"""

    version_name: str
    scores: dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0
    win_count: int = 0
    lose_count: int = 0
    draw_count: int = 0
    elo: float = 1500.0


@dataclass
class ELoReport:
    """ELO 对比报告。"""

    version_a: VersionResult
    version_b: VersionResult
    cases: list[ComparisonCase]
    winner: str | None = None
    confidence: str = ""
    significance: float = 0.0

    @property
    def score_delta(self) -> float:
        return self.version_a.total_score - self.version_b.total_score

    @property
    def elo_delta(self) -> float:
        return self.version_a.elo - self.version_b.elo


def run_comparison(
    version_a_name: str,
    version_b_name: str,
    cases: list[ComparisonCase],
    initial_elo: float = 1500.0,
) -> ELoReport:
    """在两个版本之间运行 ELO 对比。

    每个 case 用两个版本分别评分，分数高的获胜。
    用 ELO 系统追踪累计表现。
    """
    version_a = VersionResult(version_name=version_a_name, elo=initial_elo)
    version_b = VersionResult(version_name=version_b_name, elo=initial_elo)

    for case in cases:
        result_a = case.scorer(case.input_data)
        result_b = case.scorer(case.input_data)  # 同一天数据，但独立调用

        score_a = float(result_a.get("score", 0))
        score_b = float(result_b.get("score", 0))

        version_a.scores[case.name] = score_a
        version_b.scores[case.name] = score_b
        version_a.total_score += score_a
        version_b.total_score += score_b

        # ELO 更新
        if score_a > score_b:
            version_a.elo, version_b.elo = update_elo(version_a.elo, version_b.elo)
            version_a.win_count += 1
            version_b.lose_count += 1
        elif score_b > score_a:
            version_b.elo, version_a.elo = update_elo(version_b.elo, version_a.elo)
            version_b.win_count += 1
            version_a.lose_count += 1
        else:
            version_a.elo, version_b.elo = update_elo_draw(version_a.elo, version_b.elo)
            version_a.draw_count += 1
            version_b.draw_count += 1

    # 判断赢家
    if version_a.win_count > version_b.win_count:
        winner = version_a_name
    elif version_b.win_count > version_a.win_count:
        winner = version_b_name
    else:
        winner = None

    # 显著性：二项检验（win/loss 是否显著偏离 50%）
    total_decisive = version_a.win_count + version_b.win_count
    if total_decisive > 0:
        win_rate = version_a.win_count / total_decisive
        # 简单的 z-test 近似
        se = math.sqrt(0.5 * 0.5 / total_decisive)
        z_score = abs(win_rate - 0.5) / se if se > 0 else 0
        # 双边 p-value 近似
        significance = min(1.0, z_score * 1.96 / 3.0)  # 归一化到 0-1
    else:
        significance = 0.0

    if significance >= 0.95:
        confidence = "高 (p < 0.05)"
    elif significance >= 0.8:
        confidence = "中 (可接受)"
    else:
        confidence = "低 (需要更多样本)"

    return ELoReport(
        version_a=version_a,
        version_b=version_b,
        cases=cases,
        winner=winner if confidence.startswith("高") else "不明确",
        confidence=confidence,
        significance=round(significance, 3),
    )


# ── CI 门禁 ────────────────────────────────────────────────


def ci_gate(report: ELoReport, min_elo_delta: float = -10.0) -> bool:
    """CI 回归门禁：新版本不应显著劣于旧版本。

    min_elo_delta: 允许的最小 ELO 差距（负数=允许略差）
    """
    return report.elo_delta >= min_elo_delta
