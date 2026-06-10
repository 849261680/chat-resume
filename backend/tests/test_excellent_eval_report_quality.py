"""用于覆盖优秀样例评测报告中的最终简历质量摘要。"""

import importlib.util
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT_DIR / "eval" / "run_excellent_eval.py"


def load_build_report() -> Any:
    """用于从仓库根目录动态加载优秀样例报告构造函数。"""
    spec = importlib.util.spec_from_file_location("run_excellent_eval", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_report


def test_excellent_eval_report_summarizes_final_resume_quality():
    """用于验证优秀样例报告汇总最终简历质量评分。"""
    build_report = load_build_report()

    report = build_report(
        [
            {
                "id": "excellent-pass",
                "status": "ok",
                "passed": True,
                "trajectory_score": {"failure_codes": []},
                "final_resume_quality": {"score": 92, "passed": True},
            },
            {
                "id": "excellent-fail",
                "status": "ok",
                "passed": False,
                "trajectory_score": {"failure_codes": ["unexpected_decision"]},
                "final_resume_quality": {"score": 62, "passed": False},
            },
        ]
    )

    assert report["summary"]["final_resume_quality"]["average_score"] == 77.0
    assert report["summary"]["final_resume_quality"]["passed"] == 1
    assert report["summary"]["final_resume_quality"]["failed"] == 1
    assert report["failures"][0]["final_resume_quality"]["score"] == 62
