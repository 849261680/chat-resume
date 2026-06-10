#!/usr/bin/env python
"""评测流水线：对数据集批量跑分，生成效果报告。

用法:
  uv run python scripts/run_eval.py           # 纯规则（快）
  uv run python scripts/run_eval.py --llm     # 规则 + LLM 双通道

输出:  终端彩色报告 + 详细 JSON
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.agent.eval_dataset import EVAL_CASES, EvalCase
from app.services.agent.quality_judge import judge_agent_output, judge_bullet_quality


@dataclass
class CaseResult:
    """单条评测结果。"""

    case_id: str
    category: str
    expected_good: bool
    rule_score: float = 0.0
    bullet_score: float = 0.0
    llm_score: float | None = None
    llm_dimensions: list[dict[str, Any]] = field(default_factory=list)
    llm_summary: str = ""
    combined_score: float = 0.0
    passed: bool = False
    correct: bool = False  # 评判结果是否与期望一致


@dataclass
class EvalReport:
    """评测报告。"""

    total: int = 0
    passed: int = 0
    correct: int = 0
    good_cases_passed: int = 0
    bad_cases_failed: int = 0
    precision: float = 0.0  # 好案例中判断正确的比例
    recall: float = 0.0  # 所有好判断中真正好的比例
    avg_good_score: float = 0.0
    avg_bad_score: float = 0.0
    results: list[CaseResult] = field(default_factory=list)


def run_rule_eval() -> EvalReport:
    """纯规则引擎评估。"""
    results: list[CaseResult] = []

    for case in EVAL_CASES:
        # 模拟一次优化
        rule_judgment = judge_agent_output(
            user_message=case.user_request,
            tool_calls=[{
                "name": "update_bullet",
                "arguments": {
                    "section": "work_experience",
                    "item_id": "w1",
                    "bullet_id": "h1",
                    "text": case.optimized,
                },
            }],
            final_text="已完成优化。",
            pass_threshold=70.0,
        )

        bullet_dim = judge_bullet_quality(case.optimized)
        rule_score = rule_judgment.overall_score
        bullet_score = bullet_dim.score
        combined = rule_score * 0.5 + bullet_score * 0.5
        passed = combined >= 60.0
        correct = passed == case.expected_good

        results.append(CaseResult(
            case_id=case.case_id,
            category=case.category,
            expected_good=case.expected_good,
            rule_score=rule_score,
            bullet_score=bullet_score,
            combined_score=combined,
            passed=passed,
            correct=correct,
        ))

    return _build_report(results)


async def run_full_eval() -> EvalReport:
    """规则 + LLM 双通道评估。"""
    from app.services.agent.llm_judge import judge_with_llm

    results: list[CaseResult] = []

    for case in EVAL_CASES:
        # 规则通道
        rule_judgment = judge_agent_output(
            user_message=case.user_request,
            tool_calls=[{
                "name": "update_bullet",
                "arguments": {
                    "section": "work_experience",
                    "item_id": "w1",
                    "bullet_id": "h1",
                    "text": case.optimized,
                },
            }],
            final_text="已完成优化。",
        )
        bullet_dim = judge_bullet_quality(case.optimized)
        rule_score = rule_judgment.overall_score * 0.5 + bullet_dim.score * 0.5

        # LLM 通道
        try:
            llm_judgment = await judge_with_llm(
                user_message=f"用户请求: {case.user_request}\n\n原文: {case.original}\n\n优化后: {case.optimized}",
                agent_response=f"已将亮点优化为: {case.optimized}",
                timeout_seconds=30.0,
            )
            llm_score = llm_judgment.overall_score
            llm_dims = [
                {"name": d.name, "score": d.score, "reasoning": d.reasoning}
                for d in llm_judgment.dimensions
            ]
            llm_summary = llm_judgment.summary
        except Exception as exc:
            print(f"  ⚠️  LLM 评判失败 ({case.case_id}): {exc}")
            llm_score = None
            llm_dims = []
            llm_summary = f"ERROR: {exc}"

        if llm_score is not None:
            combined = rule_score * 0.3 + llm_score * 0.7
        else:
            combined = rule_score

        passed = combined >= 60.0
        correct = passed == case.expected_good

        results.append(CaseResult(
            case_id=case.case_id,
            category=case.category,
            expected_good=case.expected_good,
            rule_score=rule_score,
            bullet_score=bullet_dim.score,
            llm_score=llm_score,
            llm_dimensions=llm_dims,
            llm_summary=llm_summary,
            combined_score=combined,
            passed=passed,
            correct=correct,
        ))

        # 进度提示
        marker = "✅" if correct else "❌"
        print(f"  {marker} {case.case_id}: rule={rule_score:.0f}"
              f"{f' llm={llm_score:.0f}' if llm_score else ''}"
              f" → combined={combined:.0f} | expect={'PASS' if case.expected_good else 'FAIL'}")

    return _build_report(results)


def _build_report(results: list[CaseResult]) -> EvalReport:
    """汇总统计。"""
    good_results = [r for r in results if r.expected_good]
    bad_results = [r for r in results if not r.expected_good]

    report = EvalReport()
    report.total = len(results)
    report.passed = sum(1 for r in results if r.passed)
    report.correct = sum(1 for r in results if r.correct)
    report.good_cases_passed = sum(1 for r in good_results if r.passed)
    report.bad_cases_failed = sum(1 for r in bad_results if not r.passed)
    report.precision = report.good_cases_passed / len(good_results) if good_results else 0
    report.recall = report.bad_cases_failed / len(bad_results) if bad_results else 0
    report.avg_good_score = sum(r.combined_score for r in good_results) / len(good_results) if good_results else 0
    report.avg_bad_score = sum(r.combined_score for r in bad_results) / len(bad_results) if bad_results else 0
    report.results = results
    return report


def print_report(report: EvalReport) -> None:
    """打印彩色终端报告。"""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  简历优化 Agent 效果评估报告{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    # 汇总
    print(f"{BOLD}📊 汇总{RESET}")
    print(f"  总样本: {report.total}")
    print(f"  正确率: {GREEN if report.correct >= 12 else YELLOW}"
          f"{report.correct}/{report.total}{RESET}"
          f" ({report.correct/report.total*100:.0f}%)")
    print(f"  好案例识别率 (precision): {report.good_cases_passed}/{len([r for r in report.results if r.expected_good])}"
          f" ({report.precision*100:.0f}%)")
    print(f"  坏案例拦截率 (recall):    {report.bad_cases_failed}/{len([r for r in report.results if not r.expected_good])}"
          f" ({report.recall*100:.0f}%)")
    print(f"  好案例平均分: {report.avg_good_score:.1f}")
    print(f"  坏案例平均分: {report.avg_bad_score:.1f}")
    print(f"  分差 (discrimination): {report.avg_good_score - report.avg_bad_score:.1f}")

    # 逐条
    print(f"\n{BOLD}📋 逐条结果{RESET}")
    for r in report.results:
        tag = "✅" if r.correct else "❌"
        color = GREEN if r.correct else RED
        llm_info = f" llm={r.llm_score:.0f}" if r.llm_score else ""
        expect = "PASS" if r.expected_good else "FAIL"
        actual = "PASS" if r.passed else "FAIL"
        print(f"  {color}{tag} {r.case_id:<10s}{RESET} "
              f"rule={r.rule_score:.0f}{llm_info}"
              f" combined={r.combined_score:.0f}"
              f" | expect={expect} actual={actual}")

    # LLM 详细维度
    llm_results = [r for r in report.results if r.llm_dimensions]
    if llm_results:
        print(f"\n{BOLD}🧠 LLM 详细评判 (各维度平均分){RESET}")
        all_dims: dict[str, list[float]] = {}
        for r in llm_results:
            for d in r.llm_dimensions:
                all_dims.setdefault(d["name"], []).append(d["score"])
        for name, scores in sorted(all_dims.items()):
            avg = sum(scores) / len(scores)
            bar = "█" * int(avg)
            print(f"  {name:<12s} {avg:.1f}/5  {bar}")

    # 建议
    print(f"\n{BOLD}💡 建议{RESET}")
    if report.precision >= 0.8 and report.recall >= 0.8:
        print(f"  {GREEN}✓ 评判系统能有效区分好优化和坏优化{RESET}")
    else:
        print(f"  {YELLOW}⚠ 评判系统在区分好坏方面需要改进{RESET}")
    if report.avg_good_score - report.avg_bad_score < 15:
        print(f"  {YELLOW}⚠ 好坏案例分差较小，建议调评判阈值或权重{RESET}")
    if report.correct < report.total * 0.8:
        print(f"  {YELLOW}⚠ 正确率低于 80%，需要检查误判案例{RESET}")
    print()


def save_report(report: EvalReport, path: str) -> None:
    """保存 JSON 详细报告。"""
    data = {
        "summary": {
            "total": report.total,
            "correct": report.correct,
            "accuracy": round(report.correct / report.total, 3) if report.total else 0,
            "precision": round(report.precision, 3),
            "recall": round(report.recall, 3),
            "avg_good_score": round(report.avg_good_score, 1),
            "avg_bad_score": round(report.avg_bad_score, 1),
            "discrimination": round(report.avg_good_score - report.avg_bad_score, 1),
        },
        "results": [
            {
                "case_id": r.case_id,
                "category": r.category,
                "expected_good": r.expected_good,
                "rule_score": round(r.rule_score, 1),
                "bullet_score": round(r.bullet_score, 1),
                "llm_score": round(r.llm_score, 1) if r.llm_score else None,
                "combined_score": round(r.combined_score, 1),
                "passed": r.passed,
                "correct": r.correct,
                "llm_summary": r.llm_summary if r.llm_summary else None,
            }
            for r in report.results
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"📄 详细报告已保存: {path}")


# ── CLI ─────────────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser(description="简历优化 Agent 效果评估")
    parser.add_argument("--llm", action="store_true", help="启用 LLM 双通道评估")
    parser.add_argument("--json", type=str, default="eval_report.json", help="JSON 报告路径")
    args = parser.parse_args()

    if args.llm:
        print("🚀 运行 LLM 双通道评估...\n")
        report = await run_full_eval()
    else:
        print("🚀 运行规则引擎评估 (用 --llm 启用 LLM 评判)...\n")
        report = run_rule_eval()

    print_report(report)
    save_report(report, args.json)


if __name__ == "__main__":
    asyncio.run(main())
