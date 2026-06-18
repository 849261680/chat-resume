"""用于封装 SDK 工具审批在 ReAct context 中的临时状态。"""

from __future__ import annotations

from typing import Any


class SdkToolApprovalState:
    """用于隐藏 SDK approval preview、预处理输出和批准标记的存储细节。"""

    def __init__(self, context: dict[str, Any]):
        """用于绑定一次 Resume Agent run 的共享 context。"""
        self.context = context

    def store_preview(self, call_id: str, preview: dict[str, Any]) -> None:
        """用于按 SDK 工具 call_id 暂存待审批预览。"""
        previews = self.context.setdefault("_sdk_approval_previews", {})
        if isinstance(previews, dict):
            previews[call_id] = preview

    def preview(self, call_id: str) -> dict[str, Any] | None:
        """用于读取 SDK interruption 对应的预览。"""
        previews = self.context.get("_sdk_approval_previews")
        if not isinstance(previews, dict):
            return None
        preview = previews.get(call_id)
        return preview if isinstance(preview, dict) else None

    def store_preapproval_output(self, call_id: str, output: str) -> None:
        """用于暂存审批前已处理的工具输出。"""
        outputs = self.context.setdefault("_sdk_preapproval_outputs", {})
        if isinstance(outputs, dict):
            outputs[call_id] = output

    def pop_preapproval_output(self, call_id: str) -> str | None:
        """用于让 SDK 后续 on_invoke 复用审批前工具输出。"""
        outputs = self.context.get("_sdk_preapproval_outputs")
        if not isinstance(outputs, dict):
            return None
        output = outputs.pop(call_id, None)
        return output if isinstance(output, str) else None

    def mark_approved(self, call_id: str) -> None:
        """用于记录 SDK 已批准的工具调用。"""
        approved = self.context.setdefault("_sdk_approved_call_ids", set())
        if isinstance(approved, set):
            approved.add(call_id)

    def has_approved(self, call_id: str) -> bool:
        """用于判断 SDK 工具调用是否已获批。"""
        approved = self.context.get("_sdk_approved_call_ids")
        return isinstance(approved, set) and call_id in approved

    def consume_approved(self, call_id: str) -> bool:
        """用于消费 SDK 已批准工具调用标记。"""
        approved = self.context.get("_sdk_approved_call_ids")
        if not isinstance(approved, set) or call_id not in approved:
            return False
        approved.remove(call_id)
        return True


__all__ = ["SdkToolApprovalState"]
