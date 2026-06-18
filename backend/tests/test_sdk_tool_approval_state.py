"""用于验证 SDK 工具审批状态的独立接口。"""

from __future__ import annotations

from app.agents.resume.sdk_tool_lifecycle import SdkToolApprovalState


def test_sdk_tool_approval_state_hides_context_storage_keys():
    """SDK 审批状态应通过接口读写 preview、预处理输出和批准标记。"""
    context: dict[str, object] = {}
    state = SdkToolApprovalState(context)

    state.store_preview("call_1", {"diff_summary": "更新项目亮点"})
    state.store_preapproval_output("call_2", '{"success": false}')
    state.mark_approved("call_3")

    assert state.preview("call_1") == {"diff_summary": "更新项目亮点"}
    assert state.preview("missing") is None
    assert state.pop_preapproval_output("call_2") == '{"success": false}'
    assert state.pop_preapproval_output("call_2") is None
    assert state.has_approved("call_3") is True
    assert state.consume_approved("call_3") is True
    assert state.has_approved("call_3") is False
    assert state.consume_approved("call_3") is False
