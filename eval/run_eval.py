"""Agent 评测执行器。

用法：
    cd backend
    uv run python ../eval/run_eval.py [--cases TC001,TC002] [--output results.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from harness import (  # noqa: E402
    EVAL_DIR,
    build_agent,
    has_required_agent_api_key,
    load_backend_env,
    required_agent_api_key_name,
    run_agent_target,
)
from openai_agents_standard import build_eval_run_summary  # noqa: E402


def load_cases(filter_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """用于读取本地 eval case，并按 id 可选过滤。"""
    cases_path = EVAL_DIR / "test_cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if filter_ids:
        cases = [case for case in cases if case["id"] in filter_ids]
    return cases


def load_json_case_file(filename: str | None) -> dict[str, Any] | None:
    """用于读取 eval/cases 下的 JSON 样本文件。"""
    if not filename:
        return None
    path = EVAL_DIR / "cases" / filename
    return json.loads(path.read_text(encoding="utf-8"))


def case_to_inputs(case: dict[str, Any]) -> dict[str, Any]:
    """用于把本地 case 转成共享 harness target 输入。"""
    return {
        "case_id": case["id"],
        "resume": load_json_case_file(str(case["resume_file"])),
        "jd": load_json_case_file(case.get("jd_file")),
        "user_message": case["user_message"],
    }


async def run_single_case(agent, case: dict[str, Any]) -> dict[str, Any]:
    """用于运行单个测试用例，返回本地报告格式。"""
    try:
        result = await run_agent_target(agent, case_to_inputs(case), case=case)
        runtime_events = result.get("runtime_events")
        fallback_triggered = (
            isinstance(runtime_events, list)
            and any(
                event.get("event_type") == "llm_response"
                and event.get("finish_reason") == "stream_fallback"
                for event in runtime_events
                if isinstance(event, dict)
            )
        )
        return {
            "id": case["id"],
            "desc": case["desc"],
            "status": "ok",
            "elapsed_s": result["elapsed_s"],
            "agent_reply": result["agent_reply"],
            "tool_calls": result["tool_calls"],
            "fallback_triggered": fallback_triggered,
            "resume_before": case_to_inputs(case)["resume"],
            "resume_after": result.get("resume_after", {}),
            "case": case,
            "openai_agents_eval": result.get("openai_agents_eval"),
        }
    except Exception as exc:
        return {
            "id": case["id"],
            "desc": case["desc"],
            "status": "error",
            "elapsed_s": 0,
            "error": str(exc),
            "agent_reply": "",
            "tool_calls": [],
            "fallback_triggered": False,
            "resume_before": {},
            "resume_after": {},
            "case": case,
        }


async def run_all(filter_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """用于按顺序运行一组本地 eval cases。"""
    cases = load_cases(filter_ids)
    agent = build_agent()
    results = []

    print(f"\n{'='*60}")
    print(f"共 {len(cases)} 个测试用例")
    print(f"{'='*60}\n")

    for index, case in enumerate(cases, 1):
        print(f"[{index}/{len(cases)}] {case['id']} - {case['desc']}")
        result = await run_single_case(agent, case)
        results.append(result)
        if result["status"] == "ok":
            tools_str = ", ".join(result["tool_calls"]) or "（无工具调用）"
            fallback_note = " | fallback" if result.get("fallback_triggered") else ""
            print(f"  ✓ {result['elapsed_s']}s | 工具: {tools_str}{fallback_note}")
            print(f"  回复: {result['agent_reply'][:100]}...")
        else:
            print(f"  ✗ 错误: {result['error']}")
        print()

    return results


def save_results(results: list[dict[str, Any]], output_path: str) -> None:
    """用于把本地 eval 结果写到 JSON 文件。"""
    output = {
        "run_at": datetime.now().isoformat(),
        "total": len(results),
        "ok": sum(1 for result in results if result["status"] == "ok"),
        "error": sum(1 for result in results if result["status"] == "error"),
        "openai_agents_eval": build_eval_run_summary(results),
        "results": results,
    }
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n结果已保存到: {output_path}")


def main() -> None:
    """用于解析 CLI 参数并运行本地 eval。"""
    parser = argparse.ArgumentParser(description="Agent 评测执行器")
    parser.add_argument("--cases", help="逗号分隔的用例ID，如 TC001,TC002（默认全部）")
    parser.add_argument("--output", default="eval_results.json", help="结果输出文件路径")
    args = parser.parse_args()

    load_backend_env()
    filter_ids = [item.strip() for item in args.cases.split(",")] if args.cases else None
    if not has_required_agent_api_key():
        print(f"错误: 未设置 {required_agent_api_key_name()} 环境变量")
        sys.exit(1)

    results = asyncio.run(run_all(filter_ids))
    save_results(results, args.output)
    ok = sum(1 for result in results if result["status"] == "ok")
    print(f"\n完成: {ok}/{len(results)} 成功")


if __name__ == "__main__":
    main()
