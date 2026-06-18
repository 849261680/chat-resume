"""用于覆盖简历文档变更模块的公开接口。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.tools.resume.document import (  # noqa: E402
    update_resume_bullet,
    update_resume_item_fields,
)


def test_update_resume_bullet_mutates_nested_highlight_and_returns_diff() -> None:
    """用于验证文档模块统一处理 bullet 查找、修改和 diff。"""
    resume: dict[str, Any] = {
        "projects": [
            {
                "id": "proj_1",
                "name": "Chat Resume",
                "highlights": [{"id": "hl_1", "text": "负责前端页面"}],
            }
        ]
    }

    result = update_resume_bullet(
        resume_content=resume,
        section="projects",
        item_id="proj_1",
        bullet_id="hl_1",
        text="用流式 Agent 事件驱动简历编辑，减少用户手动修改时间 40%",
        reason="补充结果指标",
    )

    assert result["success"] is True
    assert result["updated_section"] == "projects"
    assert "补充结果指标" in result["diff_summary"]
    assert (
        resume["projects"][0]["highlights"][0]["text"]
        == "用流式 Agent 事件驱动简历编辑，减少用户手动修改时间 40%"
    )


def test_update_resume_item_fields_rejects_internal_fields() -> None:
    """用于验证文档模块统一保护内部派生字段。"""
    resume: dict[str, Any] = {
        "work_experience": [
            {
                "id": "work_1",
                "company": "示例公司",
                "is_current": False,
            }
        ]
    }

    result = update_resume_item_fields(
        resume_content=resume,
        section="work_experience",
        item_id="work_1",
        fields={"is_current": True},
    )

    assert result["success"] is False
    assert "is_current" in result["message"]
    assert resume["work_experience"][0]["is_current"] is False
