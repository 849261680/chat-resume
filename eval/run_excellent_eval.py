"""用于运行优秀简历黄金样例的真实 Agent 效果评估。"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent / "backend"
ROOT_DIR = EVAL_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def load_backend_env() -> None:
    """用于在导入 app 配置前读取 backend/.env。"""
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


load_backend_env()

from app.agents.resume.excellent_cases import load_excellent_resume_cases  # noqa: E402
from app.agents.resume.excellent_trajectory import (  # noqa: E402
    evaluate_excellent_resume_trajectory,
)
from app.agents.resume.final_resume_quality import score_final_resume_quality  # noqa: E402
from eval.harness import (  # noqa: E402
    build_agent,
    has_required_agent_api_key,
    required_agent_api_key_name,
    run_agent_target,
)
from eval.openai_agents_standard import (  # noqa: E402
    build_eval_artifact,
    build_eval_run_summary,
    build_trace_config,
)

TargetRunner = Callable[[Any, dict[str, Any]], Awaitable[dict[str, Any]]]

ANTHROPIC_EVAL_METHODOLOGY = {
    "standard": "anthropic_agent_eval",
    "source": [
        "Define task-specific measurable success criteria",
        "Run real agent loops with tool calls and tool results",
        "Grade verifiable outcomes instead of preferred wording",
        "Collect trajectory, tool efficiency, error recovery, latency, split metrics, and repeated-trial reliability",
        "Keep held-out cases separate from prompt/tool tuning cases and surface eval suite saturation",
    ],
    "dimensions": [
        "task_fidelity",
        "final_resume_quality",
        "planning_visibility",
        "feedback_repair",
        "stopping_condition",
        "tool_efficiency",
        "tool_error_recovery",
    ],
}


def load_cases(filter_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """用于读取优秀简历黄金样例并按 ID 过滤。"""
    cases = load_excellent_resume_cases()
    if filter_ids is None:
        return cases
    wanted = set(filter_ids)
    return [case for case in cases if case.get("id") in wanted]


def case_to_inputs(case: dict[str, Any]) -> dict[str, Any]:
    """用于把优秀简历样例转成共享 Agent harness 输入。"""
    return {
        "case_id": case["id"],
        "resume": case["resume"],
        "jd": {
            "title": "优秀简历 Agent 黄金样例",
            "description": case.get("jd_text", ""),
        },
        "user_message": case["user_message"],
    }


def case_to_openai_standard_case(case: dict[str, Any]) -> dict[str, Any]:
    """用于把优秀简历样例转成 OpenAI eval dataset 期望字段。"""
    expected = case.get("expected_behavior")
    expected = expected if isinstance(expected, dict) else {}
    return {
        **case,
        "expected_decision": expected.get("decision"),
        "expected_tool_calls": expected.get("expected_tool_calls", []),
        "forbidden_content": case.get("forbidden_claims", []),
    }


def trajectory_from_agent_result(result: dict[str, Any]) -> dict[str, Any]:
    """用于把真实 Agent 结果转成轨迹评测输入。"""
    return {
        "final_text": result.get("agent_reply", ""),
        "tool_calls": _tool_call_dicts(result.get("tool_calls", [])),
        "runtime_events": result.get("runtime_events", []),
    }


async def run_single_case(
    *,
    agent: Any,
    case: dict[str, Any],
    target: TargetRunner = run_agent_target,
    trial_index: int = 1,
    trial_count: int = 1,
) -> dict[str, Any]:
    """用于执行单条黄金样例并附加轨迹评分。"""
    try:
        inputs = case_to_inputs(case)
        standard_case = case_to_openai_standard_case(case)
        agent_result = await _run_target(target, agent, inputs, standard_case)
    except Exception as exc:
        return _error_result(case, exc)
    trajectory = trajectory_from_agent_result(agent_result)
    trajectory_score = evaluate_excellent_resume_trajectory(case=case, trajectory=trajectory)
    final_quality = _score_final_quality(
        case=case,
        inputs=inputs,
        agent_result=agent_result,
    )
    passed = trajectory_score["passed"] and final_quality["passed"]
    openai_artifact = agent_result.get("openai_agents_eval")
    if not isinstance(openai_artifact, dict):
        trace_config = build_trace_config(str(inputs["case_id"]))
        openai_artifact = build_eval_artifact(
            case=standard_case,
            inputs=inputs,
            result=agent_result,
            trace_config=trace_config,
        )
    return {
        "id": case["id"],
        "trial_id": f"{case['id']}:{trial_index}",
        "trial_index": trial_index,
        "trial_count": trial_count,
        "title": case.get("title", ""),
        "status": "ok",
        "passed": passed,
        "elapsed_s": agent_result.get("elapsed_s", 0),
        "agent_reply": agent_result.get("agent_reply", ""),
        "tool_calls": agent_result.get("tool_calls", []),
        "trajectory_score": trajectory_score,
        "anthropic_eval": _case_anthropic_profile(case, trajectory_score),
        "final_resume_quality": final_quality,
        "openai_agents_eval": openai_artifact,
    }


async def run_all(
    *,
    cases: list[dict[str, Any]],
    dry_run: bool = False,
    target: TargetRunner = run_agent_target,
    trials: int = 1,
) -> list[dict[str, Any]]:
    """用于按样例和试验次数批量运行优秀简历黄金样例。"""
    agent = None if dry_run else build_agent()
    results = []
    trial_count = max(1, trials)
    for case in cases:
        runner = _dry_run_target if dry_run else target
        for trial_index in range(1, trial_count + 1):
            result = await run_single_case(
                agent=agent,
                case=case,
                target=runner,
                trial_index=trial_index,
                trial_count=trial_count,
            )
            results.append(result)
            _print_case_result(result)
    return results


def build_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    """用于汇总优秀简历 Agent 评估报告。"""
    total = len(results)
    ok = sum(1 for result in results if result.get("status") == "ok")
    error = sum(1 for result in results if result.get("status") == "error")
    passed = sum(1 for result in results if result.get("passed") is True)
    failed = total - passed
    return {
        "run_at": datetime.now().isoformat(),
        "methodology": ANTHROPIC_EVAL_METHODOLOGY,
        "summary": {
            "total": total,
            "unique_cases": _unique_case_count(results),
            "ok": ok,
            "error": error,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total, 3) if total else 0.0,
            "final_resume_quality": _final_quality_summary(results),
            "anthropic_agent_eval": _anthropic_eval_summary(results),
            "dataset_splits": _dataset_split_summary(results),
            "reliability": _reliability_summary(results),
            "eval_suite_health": _eval_suite_health(results),
        },
        "openai_agents_eval": build_eval_run_summary(results),
        "failures": _failure_rows(results),
        "results": results,
    }


def save_report(report: dict[str, Any], output_path: str) -> None:
    """用于把评估报告写入 JSON 文件。"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_case_ids(raw: str | None) -> list[str] | None:
    """用于解析逗号分隔的样例 ID。"""
    if raw is None:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> None:
    """用于解析 CLI 参数并运行优秀简历 Agent 评估。"""
    parser = argparse.ArgumentParser(description="优秀简历 Agent 效果评估")
    parser.add_argument("--cases", help="逗号分隔的样例 ID，例如 excellent-001")
    parser.add_argument("--output", default="excellent_eval_results.json")
    parser.add_argument("--dry-run", action="store_true", help="不调用真实模型")
    parser.add_argument("--trials", type=int, default=1, help="每个样例重复运行次数")
    args = parser.parse_args()

    load_backend_env()
    if not args.dry_run and not has_required_agent_api_key():
        print(f"错误: 未设置 {required_agent_api_key_name()} 环境变量")
        sys.exit(1)

    cases = load_cases(parse_case_ids(args.cases))
    results = asyncio.run(run_all(cases=cases, dry_run=args.dry_run, trials=args.trials))
    report = build_report(results)
    save_report(report, args.output)
    summary = report["summary"]
    print(
        f"\n完成: {summary['passed']}/{summary['total']} 通过，"
        f"通过率 {summary['pass_rate']:.1%}，报告: {args.output}"
    )


async def _dry_run_target(agent: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """用于生成不调用模型的可评测轨迹。"""
    case = next(
        item for item in load_excellent_resume_cases()
        if item["id"] == inputs["case_id"]
    )
    expected = case["expected_behavior"]
    tools = expected["expected_tool_calls"]
    is_execute = expected.get("decision") == "execute"
    reply = "已基于已有事实完成优化。" if is_execute else "请补充更多真实事实后我再改写。"
    events = []
    if is_execute:
        events = [
            {"event_type": "text_delta", "content": "我会先基于现有事实保守改写。"},
            {"event_type": "tool_call_started", "tool_name": tools[0] if tools else ""},
        ]
    return {
        "case_id": inputs["case_id"],
        "agent_reply": reply,
        "tool_calls": tools,
        "elapsed_s": 0,
        "runtime_events": events,
        "skip_final_resume_quality": True,
    }


def _score_final_quality(
    *,
    case: dict[str, Any],
    inputs: dict[str, Any],
    agent_result: dict[str, Any],
) -> dict[str, Any]:
    """用于在执行类样例中评估最终简历成品质量。"""
    expected = case.get("expected_behavior")
    expected = expected if isinstance(expected, dict) else {}
    profile = case.get("anthropic_eval")
    profile = profile if isinstance(profile, dict) else {}
    applicable = (
        expected.get("decision") == "execute"
        and not agent_result.get("skip_final_resume_quality")
        and profile.get("final_quality_applicable", True) is not False
    )
    resume_after = agent_result.get("resume_after")
    if not isinstance(resume_after, dict) or not resume_after:
        resume_after = inputs["resume"]
    jd = inputs.get("jd")
    jd_text = jd.get("description", "") if isinstance(jd, dict) else ""
    return score_final_resume_quality(
        resume_before=inputs["resume"],
        resume_after=resume_after,
        jd_text=jd_text,
        user_message=str(inputs.get("user_message", "")),
        applicable=applicable,
    )


async def _run_target(
    target: TargetRunner,
    agent: Any,
    inputs: dict[str, Any],
    standard_case: dict[str, Any],
) -> dict[str, Any]:
    """用于兼容默认真实 runner 和测试注入 runner。"""
    if target is run_agent_target:
        return await run_agent_target(agent, inputs, case=standard_case)
    return await target(agent, inputs)


def _tool_call_dicts(tool_calls: Any) -> list[dict[str, Any]]:
    """用于把工具名列表标准化成轨迹工具结构。"""
    if not isinstance(tool_calls, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in tool_calls:
        if isinstance(item, dict):
            normalized.append(item)
            continue
        if str(item):
            normalized.append({"name": str(item)})
    return normalized


def _error_result(case: dict[str, Any], exc: Exception) -> dict[str, Any]:
    """用于构造单条样例运行失败结果。"""
    return {
        "id": case["id"],
        "title": case.get("title", ""),
        "status": "error",
        "passed": False,
        "error": str(exc),
        "trajectory_score": {"failure_codes": ["execution_error"]},
        "anthropic_eval": {"split": _case_split(case), "passed": False, "metrics": {}},
        "final_resume_quality": {"applicable": False, "failure_codes": []},
    }


def _failure_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用于提取失败样例和失败代码。"""
    rows = []
    for result in results:
        if result.get("passed") is True:
            continue
        score = result.get("trajectory_score", {})
        quality = result.get("final_resume_quality", {})
        rows.append({
            "id": result.get("id"),
            "failure_codes": _combined_failure_codes(score, quality),
            "final_resume_quality": quality,
            "anthropic_eval": result.get("anthropic_eval", {}),
        })
    return rows


def _combined_failure_codes(
    trajectory_score: dict[str, Any],
    final_quality: dict[str, Any],
) -> list[str]:
    """用于合并轨迹评分和最终质量评分失败码。"""
    trajectory_codes = trajectory_score.get("failure_codes", [])
    quality_codes = final_quality.get("failure_codes", [])
    codes = [str(code) for code in trajectory_codes if str(code)]
    codes.extend(f"final_quality:{code}" for code in quality_codes if str(code))
    return codes


def _final_quality_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """用于汇总最终简历质量评分。"""
    scores = [
        quality["score"]
        for quality in (result.get("final_resume_quality") for result in results)
        if isinstance(quality, dict)
        and quality.get("applicable") is not False
        and isinstance(quality.get("score"), (int, float))
    ]
    passed = sum(
        1
        for result in results
        if isinstance(result.get("final_resume_quality"), dict)
        and result["final_resume_quality"].get("applicable") is not False
        and result["final_resume_quality"].get("passed") is True
    )
    return {
        "total": len(scores),
        "passed": passed,
        "failed": len(scores) - passed,
        "average_score": round(sum(scores) / len(scores), 1) if scores else None,
    }


def _case_anthropic_profile(
    case: dict[str, Any],
    trajectory_score: dict[str, Any],
) -> dict[str, Any]:
    """用于把单条样例的 Anthropic 轨迹评测结果放入报告。"""
    profile = case.get("anthropic_eval")
    profile = profile if isinstance(profile, dict) else {}
    return {
        "split": _case_split(case),
        "expected_planning": bool(profile.get("expected_planning", _expects_execution(case))),
        "max_tool_calls": profile.get("max_tool_calls"),
        "passed": trajectory_score.get("anthropic_passed") is True,
        "metrics": trajectory_score.get("anthropic_metrics", {}),
        "tool_metrics": trajectory_score.get("tool_metrics", {}),
    }


def _case_split(case: dict[str, Any]) -> str:
    """用于读取样例所属评测分层。"""
    profile = case.get("anthropic_eval")
    if isinstance(profile, dict) and profile.get("split"):
        return str(profile["split"])
    return "train"


def _expects_execution(case: dict[str, Any]) -> bool:
    """用于判断样例是否期望执行简历修改。"""
    expected = case.get("expected_behavior")
    return isinstance(expected, dict) and expected.get("decision") == "execute"


def _anthropic_eval_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """用于汇总 Anthropic 风格轨迹评测维度。"""
    dimensions = _dimension_summary(results)
    total = sum(1 for result in results if isinstance(result.get("anthropic_eval"), dict))
    passed = sum(
        1
        for result in results
        if isinstance(result.get("anthropic_eval"), dict)
        and result["anthropic_eval"].get("passed") is True
    )
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "dimensions": dimensions,
        "tool_metrics": _tool_metric_summary(results),
    }


def _dimension_summary(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """用于按 Anthropic 维度统计适用样例和通过率。"""
    rows: dict[str, dict[str, int]] = {}
    for result in results:
        anthropic = result.get("anthropic_eval")
        if not isinstance(anthropic, dict):
            continue
        metrics = anthropic.get("metrics")
        if not isinstance(metrics, dict):
            continue
        for name, metric in metrics.items():
            if not isinstance(metric, dict) or metric.get("applicable") is False:
                continue
            row = rows.setdefault(str(name), {"total": 0, "passed": 0})
            row["total"] += 1
            if metric.get("passed") is True:
                row["passed"] += 1
    return {
        name: {
            "total": row["total"],
            "passed": row["passed"],
            "failed": row["total"] - row["passed"],
            "pass_rate": round(row["passed"] / row["total"], 3) if row["total"] else 0.0,
        }
        for name, row in rows.items()
    }


def _tool_metric_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """用于汇总工具调用效率和错误指标。"""
    metrics = [
        result.get("anthropic_eval", {}).get("tool_metrics", {})
        for result in results
        if isinstance(result.get("anthropic_eval"), dict)
    ]
    total_tool_calls = sum(int(metric.get("total_tool_calls", 0)) for metric in metrics)
    total_errors = sum(int(metric.get("tool_errors", 0)) for metric in metrics)
    total_duplicates = sum(int(metric.get("duplicate_tool_calls", 0)) for metric in metrics)
    return {
        "total_tool_calls": total_tool_calls,
        "average_tool_calls": round(total_tool_calls / len(metrics), 2) if metrics else 0.0,
        "tool_errors": total_errors,
        "duplicate_tool_calls": total_duplicates,
    }



def _unique_case_count(results: list[dict[str, Any]]) -> int:
    """用于统计去重后的任务数量。"""
    return len({str(result.get("id")) for result in results if result.get("id")})


def _reliability_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """用于按任务汇总重复试验后的 pass@k 和 pass^k 稳定性。"""
    rows = _results_by_case(results)
    case_rows = {}
    all_passed = 0
    any_passed = 0
    for case_id, attempts in rows.items():
        passed = sum(1 for result in attempts if result.get("passed") is True)
        total = len(attempts)
        if passed == total:
            all_passed += 1
        if passed:
            any_passed += 1
        case_rows[case_id] = {
            "trials": total,
            "passed": passed,
            "pass_rate": round(passed / total, 3) if total else 0.0,
            "pass@k": 1.0 if passed else 0.0,
            "pass^k": 1.0 if total and passed == total else 0.0,
        }
    total_cases = len(rows)
    return {
        "unique_cases": total_cases,
        "trials_per_case": _observed_trials_per_case(rows),
        "pass@k": round(any_passed / total_cases, 3) if total_cases else 0.0,
        "pass^k": round(all_passed / total_cases, 3) if total_cases else 0.0,
        "cases": case_rows,
    }


def _eval_suite_health(results: list[dict[str, Any]]) -> dict[str, Any]:
    """用于暴露评测套件是否满足 Anthropic 建议的最小覆盖。"""
    unique_cases = _unique_case_count(results)
    trials_per_case = _reliability_summary(results)["trials_per_case"]
    return {
        "recommended_min_cases": 20,
        "unique_cases": unique_cases,
        "has_minimum_task_count": unique_cases >= 20,
        "has_repeated_trials": trials_per_case >= 2,
        "status": "healthy" if unique_cases >= 20 and trials_per_case >= 2 else "needs_expansion",
    }


def _results_by_case(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """用于按 case id 分组试验结果。"""
    rows: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        case_id = str(result.get("id") or "")
        if not case_id:
            continue
        rows.setdefault(case_id, []).append(result)
    return rows


def _observed_trials_per_case(rows: dict[str, list[dict[str, Any]]]) -> int:
    """用于读取当前报告中每个任务的最小试验次数。"""
    if not rows:
        return 0
    return min(len(attempts) for attempts in rows.values())

def _dataset_split_summary(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """用于按 train/holdout/regression 分层汇总结果。"""
    rows: dict[str, dict[str, int]] = {}
    for result in results:
        split = "train"
        anthropic = result.get("anthropic_eval")
        if isinstance(anthropic, dict):
            split = str(anthropic.get("split") or "train")
        row = rows.setdefault(split, {"total": 0, "passed": 0})
        row["total"] += 1
        if result.get("passed") is True:
            row["passed"] += 1
    return {
        split: {
            "total": row["total"],
            "passed": row["passed"],
            "failed": row["total"] - row["passed"],
            "pass_rate": round(row["passed"] / row["total"], 3) if row["total"] else 0.0,
        }
        for split, row in rows.items()
    }

def _print_case_result(result: dict[str, Any]) -> None:
    """用于打印单条样例运行摘要。"""
    mark = "PASS" if result.get("passed") else "FAIL"
    tools = ", ".join(str(item) for item in result.get("tool_calls", []))
    print(f"{mark} {result.get('id')} tools=[{tools}]")


if __name__ == "__main__":
    main()
