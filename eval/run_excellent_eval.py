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
) -> dict[str, Any]:
    """用于执行单条黄金样例并附加轨迹评分。"""
    try:
        inputs = case_to_inputs(case)
        standard_case = case_to_openai_standard_case(case)
        agent_result = await _run_target(target, agent, inputs, standard_case)
    except Exception as exc:
        return _error_result(case, exc)
    trajectory = trajectory_from_agent_result(agent_result)
    score = evaluate_excellent_resume_trajectory(case=case, trajectory=trajectory)
    final_quality = _score_final_quality(
        case=case,
        inputs=inputs,
        agent_result=agent_result,
    )
    passed = score["passed"] and final_quality["passed"]
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
        "title": case.get("title", ""),
        "status": "ok",
        "passed": passed,
        "elapsed_s": agent_result.get("elapsed_s", 0),
        "agent_reply": agent_result.get("agent_reply", ""),
        "tool_calls": agent_result.get("tool_calls", []),
        "trajectory_score": score,
        "final_resume_quality": final_quality,
        "openai_agents_eval": openai_artifact,
    }


async def run_all(
    *,
    cases: list[dict[str, Any]],
    dry_run: bool = False,
    target: TargetRunner = run_agent_target,
) -> list[dict[str, Any]]:
    """用于批量运行优秀简历黄金样例。"""
    agent = None if dry_run else build_agent()
    results = []
    for case in cases:
        runner = _dry_run_target if dry_run else target
        result = await run_single_case(agent=agent, case=case, target=runner)
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
        "summary": {
            "total": total,
            "ok": ok,
            "error": error,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total, 3) if total else 0.0,
            "final_resume_quality": _final_quality_summary(results),
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
    args = parser.parse_args()

    load_backend_env()
    if not args.dry_run and not has_required_agent_api_key():
        print(f"错误: 未设置 {required_agent_api_key_name()} 环境变量")
        sys.exit(1)

    cases = load_cases(parse_case_ids(args.cases))
    results = asyncio.run(run_all(cases=cases, dry_run=args.dry_run))
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
    reply = "已基于已有事实完成优化。" if tools else "请补充更多真实事实后我再改写。"
    return {
        "case_id": inputs["case_id"],
        "agent_reply": reply,
        "tool_calls": tools,
        "elapsed_s": 0,
        "runtime_events": [],
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
    applicable = (
        expected.get("decision") == "execute"
        and not agent_result.get("skip_final_resume_quality")
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


def _tool_call_dicts(tool_calls: Any) -> list[dict[str, str]]:
    """用于把工具名列表标准化成轨迹工具结构。"""
    if not isinstance(tool_calls, list):
        return []
    return [{"name": str(name)} for name in tool_calls if str(name)]


def _error_result(case: dict[str, Any], exc: Exception) -> dict[str, Any]:
    """用于构造单条样例运行失败结果。"""
    return {
        "id": case["id"],
        "title": case.get("title", ""),
        "status": "error",
        "passed": False,
        "error": str(exc),
        "trajectory_score": {"failure_codes": ["execution_error"]},
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


def _print_case_result(result: dict[str, Any]) -> None:
    """用于打印单条样例运行摘要。"""
    mark = "PASS" if result.get("passed") else "FAIL"
    tools = ", ".join(str(item) for item in result.get("tool_calls", []))
    print(f"{mark} {result.get('id')} tools=[{tools}]")


if __name__ == "__main__":
    main()
