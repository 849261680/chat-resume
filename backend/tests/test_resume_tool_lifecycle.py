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
from app.agents.resume.tool_lifecycle import (  # noqa: E402
    ResumeToolLifecycleRequest,
    ResumeToolLifecycleRunner,
    ResumeToolLifecycleStart,
)
from app.agents.resume.tool_transaction import ResumeToolTransaction  # noqa: E402
from app.runtime.tool_confirmation import ToolConfirmationPolicy  # noqa: E402


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


@pytest.mark.asyncio
async def test_lifecycle_runner_delegates_requested_tool_flow_to_single_operation() -> None:
    """用于验证普通工具生命周期通过深接口交给执行侧处理。"""

    class RequestedOnlyOperations:
        """用于模拟只暴露深生命周期接口的工具执行侧。"""

        def __init__(self) -> None:
            """用于记录被委托的请求和开始状态。"""
            self.delegated: tuple[str, bool] | None = None

        @staticmethod
        def tool_call_payload(
            call_id: str,
            tool_name: str,
            tool_input: dict[str, Any],
        ) -> dict[str, Any]:
            """用于构造测试里的工具调用载荷。"""
            return {
                "id": call_id,
                "type": "function",
                "function": {"name": tool_name, "arguments": tool_input},
            }

        async def run_requested_tool_call(
            self,
            request: ResumeToolLifecycleRequest,
            lifecycle_start: Any,
        ) -> str:
            """用于验证生命周期 runner 只委托一次普通工具流。"""
            self.delegated = (request.call_id, lifecycle_start.needs_confirmation)
            return '{"success": true}'

    operations = RequestedOnlyOperations()
    agent = ResumeAgent()
    output = await ResumeToolLifecycleRunner(
        operations,
        ToolConfirmationPolicy(),
    ).run(
        ResumeToolLifecycleRequest(
            agent=agent.definition,
            run_id="run_deep_interface",
            call_id="call_deep_interface",
            tool_name="update_bullet",
            tool_input={"text": "提升系统稳定性"},
            context={},
            confirmation_queue=asyncio.Queue(),
            event_queue=None,
            event_callback=None,
            executed_tools=[],
            stream_state={},
        )
    )

    assert output == '{"success": true}'
    assert operations.delegated == ("call_deep_interface", True)


@pytest.mark.asyncio
async def test_tool_transaction_owns_requested_tool_ordering() -> None:
    """用于验证 requested 工具流由 transaction seam 收口。"""

    class TransactionOperations:
        """用于记录 transaction 触发的执行步骤。"""

        def __init__(self) -> None:
            """用于保存调用顺序。"""
            self.calls: list[str] = []

        def record_tool_requested(self, stream_state: dict[str, Any], call_id: str) -> None:
            """用于记录工具请求。"""
            self.calls.append(f"requested:{call_id}")
            stream_state["requested"] = call_id

        def trace_tool_requested(
            self,
            agent: Any,
            run_id: str,
            call_id: str,
            tool_name: str,
            tool_input: dict[str, Any],
            needs_confirmation: bool,
        ) -> None:
            """用于记录工具请求 trace。"""
            del agent, run_id, tool_name, tool_input
            self.calls.append(f"trace:{call_id}:{needs_confirmation}")

        @staticmethod
        def has_tool_argument_parse_error(tool_input: dict[str, Any]) -> bool:
            """用于模拟参数解析成功。"""
            del tool_input
            return False

        async def maybe_confirm_tool(self, **kwargs: Any) -> None:
            """用于模拟免确认工具不需要预览。"""
            self.calls.append(f"preview:{kwargs['call_id']}")
            return None

        async def maybe_block_auto_execute_tool(self, **kwargs: Any) -> None:
            """用于模拟自动执行质量闸口通过。"""
            self.calls.append(f"guard:{kwargs['call_id']}")
            return None

        async def publish_visible_tool_call_once(self, **kwargs: Any) -> None:
            """用于模拟发布可见工具调用。"""
            self.calls.append(f"visible:{kwargs['call_id']}")

        async def run_confirmed_tool(self, **kwargs: Any) -> str:
            """用于模拟最终工具执行。"""
            self.calls.append(f"execute:{kwargs['call_id']}")
            return '{"success": true}'

    operations = TransactionOperations()
    agent = ResumeAgent()
    request = ResumeToolLifecycleRequest(
        agent=agent.definition,
        run_id="run_transaction",
        call_id="call_transaction",
        tool_name="read_job_post",
        tool_input={"job_post_id": 1},
        context={},
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        executed_tools=[],
        stream_state={},
    )
    lifecycle_start = ResumeToolLifecycleStart(
        tool_started_at=1.0,
        tool_call={
            "id": "call_transaction",
            "type": "function",
            "function": {"name": "read_job_post", "arguments": {"job_post_id": 1}},
        },
        needs_confirmation=False,
        preapproval_output=None,
        sdk_approved=False,
    )

    output = await ResumeToolTransaction(
        operations=operations,
        request=request,
        lifecycle_start=lifecycle_start,
    ).run_requested()

    assert output == '{"success": true}'
    assert operations.calls == [
        "requested:call_transaction",
        "trace:call_transaction:False",
        "preview:call_transaction",
        "visible:call_transaction",
        "guard:call_transaction",
        "execute:call_transaction",
    ]


@pytest.mark.asyncio
async def test_tool_transaction_owns_sdk_approved_ordering() -> None:
    """用于验证 SDK 已确认工具流也由 transaction seam 收口。"""

    class SdkApprovedOperations:
        """用于记录 SDK approved transaction 的执行顺序。"""

        def __init__(self) -> None:
            """用于保存调用顺序。"""
            self.calls: list[str] = []

        def record_tool_requested(self, stream_state: dict[str, Any], call_id: str) -> None:
            """用于记录工具请求。"""
            self.calls.append(f"requested:{call_id}")
            stream_state["requested"] = call_id

        def trace_tool_requested(
            self,
            agent: Any,
            run_id: str,
            call_id: str,
            tool_name: str,
            tool_input: dict[str, Any],
            needs_confirmation: bool,
        ) -> None:
            """用于记录工具请求 trace。"""
            del agent, run_id, tool_name, tool_input
            self.calls.append(f"trace:{call_id}:{needs_confirmation}")

        async def run_confirmed_tool(self, **kwargs: Any) -> str:
            """用于模拟 SDK 已确认后的最终工具执行。"""
            self.calls.append(f"execute:{kwargs['call_id']}:{kwargs['needs_confirmation']}")
            return '{"success": true}'

    operations = SdkApprovedOperations()
    agent = ResumeAgent()
    request = ResumeToolLifecycleRequest(
        agent=agent.definition,
        run_id="run_sdk_transaction",
        call_id="call_sdk_transaction",
        tool_name="update_summary",
        tool_input={"text": "更强的个人总结"},
        context={},
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        executed_tools=[],
        stream_state={},
    )
    lifecycle_start = ResumeToolLifecycleStart(
        tool_started_at=1.0,
        tool_call={
            "id": "call_sdk_transaction",
            "type": "function",
            "function": {"name": "update_summary", "arguments": {"text": "更强的个人总结"}},
        },
        needs_confirmation=True,
        preapproval_output=None,
        sdk_approved=True,
    )

    output = await ResumeToolTransaction(
        operations=operations,
        request=request,
        lifecycle_start=lifecycle_start,
    ).run_sdk_approved()

    assert output == '{"success": true}'
    assert operations.calls == [
        "requested:call_sdk_transaction",
        "trace:call_sdk_transaction:True",
        "execute:call_sdk_transaction:True",
    ]
