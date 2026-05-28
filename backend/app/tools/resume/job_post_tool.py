"""用于提供 Resume Agent 读取 JD 库的只读工具。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

JobPostReader = Callable[[int, int], dict[str, Any] | None]
JobPostLister = Callable[..., list[dict[str, Any]]]


def list_job_posts(
    resume_content: dict[str, Any],
    *,
    user_id: int | None = None,
    query: str = "",
    limit: int = 20,
    list_job_posts_reader: JobPostLister | None = None,
) -> dict[str, Any]:
    """用于列出当前用户可供 Agent 读取的 JD 摘要。"""
    del resume_content
    if user_id is None or list_job_posts_reader is None:
        return _configuration_error()
    records = list_job_posts_reader(user_id, query=query, limit=limit)
    return {
        "success": True,
        "message": f"找到 {len(records)} 条 JD",
        "job_posts": records,
    }


def read_job_post(
    resume_content: dict[str, Any],
    *,
    job_post_id: int,
    user_id: int | None = None,
    read_job_post_reader: JobPostReader | None = None,
) -> dict[str, Any]:
    """用于按 id 读取当前用户的一条完整 JD。"""
    del resume_content
    if user_id is None or read_job_post_reader is None:
        return _configuration_error()
    record = read_job_post_reader(user_id, int(job_post_id))
    if record is None:
        return {
            "success": False,
            "message": "未找到该 JD，或当前用户无权读取。",
            "job_post": None,
        }
    return {
        "success": True,
        "message": "已读取 JD",
        "job_post": record,
    }


def _configuration_error() -> dict[str, Any]:
    """用于返回工具运行上下文缺少 JD 读取器的错误。"""
    return {
        "success": False,
        "message": "当前会话缺少 JD 读取权限上下文。",
    }


__all__ = ["list_job_posts", "read_job_post"]
