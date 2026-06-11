"""用于覆盖优秀简历真实 Agent 评估 runner。"""

import asyncio
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
EVAL_DIR = ROOT_DIR / "eval"
RUNNER = EVAL_DIR / "run_excellent_eval.py"
sys.path.insert(0, str(ROOT_DIR))


def _load_runner() -> ModuleType:
    """用于按文件路径加载 eval runner 脚本。"""
    spec = importlib.util.spec_from_file_location("run_excellent_eval", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load run_excellent_eval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER_MODULE = _load_runner()
build_report: Any = RUNNER_MODULE.build_report
case_to_inputs: Any = RUNNER_MODULE.case_to_inputs
run_single_case: Any = RUNNER_MODULE.run_single_case
run_all: Any = RUNNER_MODULE.run_all
trajectory_from_agent_result: Any = RUNNER_MODULE.trajectory_from_agent_result


def test_case_to_inputs_uses_excellent_case_resume_and_jd():
    """用于验证黄金样例能转成真实 Agent 输入。"""
    case = {
        "id": "excellent-x",
        "jd_text": "要求后端接口设计能力",
        "user_message": "帮我优化",
        "resume": {"projects": [{"id": "p1", "highlights": []}]},
    }

    inputs = case_to_inputs(case)

    assert inputs == {
        "case_id": "excellent-x",
        "resume": case["resume"],
        "jd": {"title": "优秀简历 Agent 黄金样例", "description": "要求后端接口设计能力"},
        "user_message": "帮我优化",
    }


def test_trajectory_from_agent_result_preserves_tool_calls_and_reply():
    """用于验证真实 Agent 结果能转成轨迹评测输入。"""
    trajectory = trajectory_from_agent_result(
        {
            "agent_reply": "请补充真实指标。",
            "tool_calls": ["update_bullet"],
            "runtime_events": [{"event_type": "x"}],
        }
    )

    assert trajectory == {
        "final_text": "请补充真实指标。",
        "tool_calls": [{"name": "update_bullet"}],
        "runtime_events": [{"event_type": "x"}],
    }


def test_run_single_case_scores_fake_agent_result():
    """用于验证单条样例会执行注入 runner 并返回轨迹评分。"""
    case = {
        "id": "excellent-001",
        "title": "执行样例",
        "jd_text": "后端岗位",
        "user_message": "帮我优化",
        "resume": {"projects": []},
        "expected_behavior": {
            "decision": "execute",
            "expected_tool_calls": ["update_bullet"],
        },
        "forbidden_claims": ["Kafka"],
    }

    async def fake_target(agent, inputs):
        """用于模拟真实 Agent 的成功结果。"""
        assert inputs["case_id"] == "excellent-001"
        return {
            "case_id": inputs["case_id"],
            "agent_reply": "已基于已有事实优化。",
            "tool_calls": ["update_bullet"],
            "elapsed_s": 0.01,
            "runtime_events": [
                {"event_type": "text_delta", "content": "我会先保守改写项目亮点。"},
                {"event_type": "tool_call_started", "tool_name": "update_bullet"},
            ],
            "skip_final_resume_quality": True,
        }

    result = asyncio.run(run_single_case(agent=object(), case=case, target=fake_target))

    assert result["status"] == "ok"
    assert result["trajectory_score"]["passed"] is True
    assert result["anthropic_eval"]["passed"] is True
    assert result["passed"] is True


def test_build_report_summarizes_pass_rate_and_failures():
    """用于验证报告汇总通过率和失败原因。"""
    report = build_report(
        [
            {
                "id": "excellent-001",
                "status": "ok",
                "passed": True,
                "trajectory_score": {"failure_codes": []},
            },
            {
                "id": "excellent-002",
                "status": "ok",
                "passed": False,
                "trajectory_score": {"failure_codes": ["unexpected_decision"]},
            },
        ]
    )

    assert report["methodology"]["standard"] == "anthropic_agent_eval"
    assert report["summary"]["total"] == 2
    assert report["summary"]["unique_cases"] == 2
    assert report["summary"]["passed"] == 1
    assert report["summary"]["pass_rate"] == 0.5
    assert report["summary"]["final_resume_quality"] == {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "average_score": None,
    }
    assert report["summary"]["anthropic_agent_eval"]["total"] == 0
    assert report["summary"]["dataset_splits"]["train"]["total"] == 2
    assert report["summary"]["reliability"]["pass@k"] == 0.5
    assert report["summary"]["eval_suite_health"]["status"] == "needs_expansion"
    assert report["openai_agents_eval"]["dataset_item_count"] == 2
    assert report["failures"] == [
        {
            "id": "excellent-002",
            "failure_codes": ["unexpected_decision"],
            "final_resume_quality": {},
            "anthropic_eval": {},
        }
    ]



def test_build_report_summarizes_repeated_trial_reliability():
    """用于验证重复试验报告 pass@k 和 pass^k 稳定性。"""
    report = build_report(
        [
            {"id": "case-a", "status": "ok", "passed": True, "trajectory_score": {}},
            {"id": "case-a", "status": "ok", "passed": False, "trajectory_score": {}},
            {"id": "case-b", "status": "ok", "passed": True, "trajectory_score": {}},
            {"id": "case-b", "status": "ok", "passed": True, "trajectory_score": {}},
        ]
    )

    reliability = report["summary"]["reliability"]
    assert reliability["trials_per_case"] == 2
    assert reliability["pass@k"] == 1.0
    assert reliability["pass^k"] == 0.5
    assert reliability["cases"]["case-a"]["pass@k"] == 1.0
    assert reliability["cases"]["case-a"]["pass^k"] == 0.0

def test_build_report_summarizes_anthropic_dimensions():
    """用于验证报告汇总 Anthropic 轨迹维度和工具指标。"""
    report = build_report(
        [
            {
                "id": "excellent-011",
                "status": "ok",
                "passed": True,
                "trajectory_score": {"failure_codes": []},
                "anthropic_eval": {
                    "split": "holdout",
                    "passed": False,
                    "metrics": {
                        "planning_visibility": {
                            "applicable": True,
                            "passed": False,
                        },
                        "feedback_repair": {
                            "applicable": False,
                            "passed": True,
                        },
                    },
                    "tool_metrics": {
                        "total_tool_calls": 2,
                        "tool_errors": 1,
                        "duplicate_tool_calls": 0,
                    },
                },
            }
        ]
    )

    summary = report["summary"]["anthropic_agent_eval"]
    assert summary["total"] == 1
    assert summary["failed"] == 1
    assert summary["dimensions"]["planning_visibility"]["pass_rate"] == 0.0
    assert summary["tool_metrics"]["tool_errors"] == 1
    assert report["summary"]["dataset_splits"]["holdout"]["total"] == 1


def test_cli_dry_run_writes_report_without_openrouter_key(tmp_path, monkeypatch):
    """用于验证 CLI dry-run 不需要真实模型密钥。"""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    output_path = tmp_path / "excellent_eval.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--cases",
            "excellent-002",
            "--dry-run",
            "--trials",
            "3",
            "--output",
            str(output_path),
        ],
        cwd=ROOT_DIR / "backend",
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["summary"]["total"] == 3
    assert report["summary"]["unique_cases"] == 1
    assert report["summary"]["reliability"]["trials_per_case"] == 3
    assert report["summary"]["reliability"]["pass^k"] == 1.0
    assert report["results"][0]["id"] == "excellent-002"
