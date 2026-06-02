"""用于验证简历 Agent 流式服务把板块显隐同步到 layout_config 并剥离传输 meta。"""

from __future__ import annotations

from typing import Any

from app.services.agent.resume_agent_stream_service import ResumeAgentStreamService


class _FakeResumeService:
    """用于记录 update 调用而不触达数据库。"""

    def __init__(self) -> None:
        """用于初始化调用记录。"""
        self.updates: list[tuple[int, dict[str, Any]]] = []

    def update(self, resume_id: int, payload: dict[str, Any]) -> None:
        """用于记录一次更新调用。"""
        self.updates.append((resume_id, payload))


class _FakeResume:
    """用于提供带 layout_config 的简历桩。"""

    def __init__(self, layout_config: dict[str, Any] | None) -> None:
        """用于初始化 layout_config。"""
        self.layout_config = layout_config


def test_persist_strips_visibility_meta_and_skips_when_content_unchanged() -> None:
    """用于验证仅 _visible_modules 变化时不落库内容，且持久化内容不含该 meta。"""
    service = _FakeResumeService()
    original = {"summary": {"text": "hi"}}
    latest = {"summary": {"text": "hi"}, "_visible_modules": ["summary"]}

    ResumeAgentStreamService._persist_resume_if_changed(
        service,  # type: ignore[arg-type]
        resume_id=1,
        latest_resume_content=latest,
        original_resume=original,
    )

    assert service.updates == []


def test_persist_writes_clean_content_when_changed() -> None:
    """用于验证内容变化时落库的 content 已剥离 _visible_modules。"""
    service = _FakeResumeService()
    original = {"summary": {"text": "hi"}}
    latest = {"summary": {"text": "changed"}, "_visible_modules": ["summary"]}

    ResumeAgentStreamService._persist_resume_if_changed(
        service,  # type: ignore[arg-type]
        resume_id=7,
        latest_resume_content=latest,
        original_resume=original,
    )

    assert len(service.updates) == 1
    resume_id, payload = service.updates[0]
    assert resume_id == 7
    assert "_visible_modules" not in payload["content"]
    assert payload["content"] == {"summary": {"text": "changed"}}


def test_sync_visibility_merges_into_layout_config_when_changed() -> None:
    """用于验证可见模块变化时合并写入 layout_config，保留其它布局字段。"""
    service = _FakeResumeService()
    resume = _FakeResume({"spacingScale": 0.7, "visibleModules": ["personal", "summary"]})

    ResumeAgentStreamService._sync_visibility_if_changed(
        service,  # type: ignore[arg-type]
        resume=resume,
        resume_id=3,
        request_visible=["personal", "summary"],
        latest_resume_content={"_visible_modules": ["personal"]},
    )

    assert len(service.updates) == 1
    resume_id, payload = service.updates[0]
    assert resume_id == 3
    assert payload["layout_config"]["visibleModules"] == ["personal"]
    assert payload["layout_config"]["spacingScale"] == 0.7


def test_sync_visibility_noop_when_unchanged() -> None:
    """用于验证可见模块未变化时不触发 layout_config 写入。"""
    service = _FakeResumeService()
    resume = _FakeResume({"visibleModules": ["personal", "summary"]})

    ResumeAgentStreamService._sync_visibility_if_changed(
        service,  # type: ignore[arg-type]
        resume=resume,
        resume_id=3,
        request_visible=["personal", "summary"],
        latest_resume_content={"_visible_modules": ["personal", "summary"]},
    )

    assert service.updates == []
