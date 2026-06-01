"""用于管理工具确认环节的会话队列。"""

import asyncio
from typing import Dict, Optional


class ConfirmationSessionManager:
    """用于在 session 维度保存待确认工具调用的队列。"""

    def __init__(self):
        """用于初始化内存中的确认队列表。"""
        self._queues: Dict[str, asyncio.Queue] = {}

    def create(self, session_id: str) -> asyncio.Queue:
        """用于为新的 agent session 创建确认队列。"""
        q: asyncio.Queue = asyncio.Queue(maxsize=1)
        self._queues[session_id] = q
        return q

    def get(self, session_id: str) -> Optional[asyncio.Queue]:
        """用于按 session_id 获取已有确认队列。"""
        return self._queues.get(session_id)

    async def put(self, session_id: str, confirmed: bool | dict) -> bool:
        """用于向指定会话投递一次确认结果。"""
        q = self._queues.get(session_id)
        if q is None:
            return False
        await q.put(confirmed)
        return True

    def remove(self, session_id: str) -> None:
        """用于在会话结束后清理确认队列。"""
        self._queues.pop(session_id, None)


confirmation_manager = ConfirmationSessionManager()

__all__ = ["ConfirmationSessionManager", "confirmation_manager"]
