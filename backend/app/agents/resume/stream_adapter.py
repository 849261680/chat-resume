"""用于承接 Resume Agent 的模型流适配策略。"""

from __future__ import annotations

import inspect
from typing import Any

from pi_agent_core import AgentContext
from pi_agent_core.types import StreamFn


class ResumeReActStreamAdapter:
    """用于把底层模型流接入 Resume ReAct runtime。"""

    def __init__(self, stream_fn: StreamFn):
        """保存底层 stream 函数，并透传测试所需属性。"""
        self._stream_fn = stream_fn

    def __getattr__(self, name: str) -> Any:
        """透传底层 stream 函数的统计属性。"""
        return getattr(self._stream_fn, name)

    async def __call__(
        self,
        model: Any,
        context: AgentContext,
        options: Any,
    ) -> Any:
        """调用底层模型流并保留完整工具调用结果。"""
        response = self._stream_fn(model, context, options)
        if inspect.isawaitable(response):
            response = await response
        return response
