"""用于覆盖 eval harness 的结果恢复逻辑。"""

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
HARNESS_PATH = ROOT_DIR / "eval" / "harness.py"


def load_eval_harness() -> ModuleType:
    """用于按文件路径加载 eval harness。"""
    spec = importlib.util.spec_from_file_location("eval_harness", HARNESS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_agent_target_recovers_resume_after_from_tool_result_context():
    """用于验证最终回复缺 context 时仍能读取工具结果里的最终简历。"""
    harness = load_eval_harness()
    resume_after = {
        "projects": [
            {
                "id": "p1",
                "highlights": [{"id": "b1", "text": "重构接口链路，修复状态丢失问题"}],
            }
        ]
    }

    class FakeRuntime:
        """用于模拟只在 tool_result 事件里带 context 的 runtime。"""

        async def run(self, **kwargs: Any) -> dict[str, Any]:
            """用于返回缺少最终 context 的 runtime 结果。"""
            kwargs["event_callback"]({
                "event_type": "tool_result",
                "context": {"resume_content": resume_after},
            })
            return {"content": "已完成", "tool_calls": [], "context": None}

    fake_agent = SimpleNamespace(runtime=FakeRuntime(), definition=object())

    result = asyncio.run(
        harness.run_agent_target(
            fake_agent,
            {"case_id": "case-x", "resume": {"projects": []}, "user_message": "优化"},
        )
    )

    assert result["resume_after"] == resume_after
