"""用于覆盖 Resume 工具调用生命周期的深接口。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.agents.resume.tool_execution import ResumeToolExecutionStage  # noqa: E402
from app.agents.resume.tool_lifecycle import ResumeToolLifecycleRequest  # noqa: E402


@pytest.mark.asyncio
async def test_tool_lifecycle_request_runs_confirmed_tool_call() -> None:
    """用于验证工具生命周期可以通过单一 request 接口执行。"""
    agent = ResumeAgent()
    stage = ResumeToolExecutionStage()
    resume: dict[str, Any] = {
        "projects": [
            {
                "id": "proj_1",
                "name": "Chat Resume",
                "highlights": [{"id": "hl_1", "text": "实现简历编辑"}],
            }
        ]
    }
    confirmation_queue: asyncio.Queue[bool] = asyncio.Queue()
    confirmation_queue.put_nowait(True)
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    stream_state: dict[str, Any] = {
        "visible_tool_call_ids": set(),
        "confirmed_diff_items": [],
        "confirmation_wait_ms": 0.0,
        "chunk_index": 0,
        "response_parts": [],
    }
    executed_tools: list[dict[str, Any]] = []

    result = await stage.execute_lifecycle(
        ResumeToolLifecycleRequest(
            agent=agent.definition,
            run_id="run_lifecycle",
            call_id="call_1",
            tool_name="update_bullet",
            tool_input={
                "section": "projects",
                "item_id": "proj_1",
                "bullet_id": "hl_1",
                "text": "实现流式 Agent 简历编辑，减少用户手动修改时间 40%",
                "reason": "补充量化结果",
            },
            context={
                "resume_content": resume,
                "allowed_sections": {"projects"},
                "user_message": "减少手动修改时间 40%",
            },
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=None,
            executed_tools=executed_tools,
            stream_state=stream_state,
        )
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    assert "减少用户手动修改时间 40%" in str(result.details)
    assert resume["projects"][0]["highlights"][0]["text"] == (
        "实现流式 Agent 简历编辑，减少用户手动修改时间 40%"
    )
    assert any(event.get("tool_pending") for event in events)
    assert any(event.get("tool_confirmed") for event in events)
