"""用于兼容 Resume 工具调用开始后的执行流入口。"""

from __future__ import annotations

from typing import Any

from app.agents.resume.tool_lifecycle import (
    ResumeToolLifecycleRequest,
    ResumeToolLifecycleStart,
)
from app.agents.resume.tool_transaction import ResumeToolTransaction


class ResumeToolExecutionFlow:
    """用于把旧执行流入口委托给工具 transaction。"""

    def __init__(self, operations: Any):
        """用于绑定底层工具操作实现。"""
        self.operations = operations

    async def run_sdk_approved(
        self,
        request: ResumeToolLifecycleRequest,
        lifecycle_start: ResumeToolLifecycleStart,
    ) -> str:
        """用于执行 SDK 已确认的工具调用。"""
        return await ResumeToolTransaction(
            operations=self.operations,
            request=request,
            lifecycle_start=lifecycle_start,
        ).run_sdk_approved()

    async def run_requested(
        self,
        request: ResumeToolLifecycleRequest,
        lifecycle_start: ResumeToolLifecycleStart,
    ) -> str:
        """用于执行普通 requested 工具调用的预览、确认和执行分支。"""
        return await ResumeToolTransaction(
            operations=self.operations,
            request=request,
            lifecycle_start=lifecycle_start,
        ).run_requested()


__all__ = ["ResumeToolExecutionFlow"]
