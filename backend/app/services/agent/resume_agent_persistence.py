"""用于集中处理 Resume Agent 简历内容持久化和可见模块同步规则。"""

from __future__ import annotations

from typing import Any, Protocol, cast

from app.tools.resume.sections import allowed_sections_from_visible_modules


class ResumePersistenceStore(Protocol):
    """用于声明持久化模块需要的简历写入能力。"""

    def update(self, resume_id: int, payload: dict[str, Any], /) -> Any:
        """用于更新指定简历的持久化字段。"""
        ...


class ResumeAgentPersistence:
    """用于封装 Resume Agent 内容保存和可见模块同步规则。"""

    def __init__(self, store: ResumePersistenceStore):
        """用于注入简历持久化依赖。"""
        self.store = store

    def load_resume_content(self, resume: Any) -> dict[str, Any]:
        """用于读取完整简历内容供 Agent 推理和工具使用。"""
        return cast(
            dict[str, Any],
            resume.content if isinstance(resume.content, dict) else {},
        )

    def allowed_sections(
        self,
        resume_content: dict[str, Any],
        visible_modules: list[str] | None = None,
    ) -> set[str]:
        """用于按可见模块或简历内容推导允许工具修改的顶层板块。"""
        if visible_modules:
            return allowed_sections_from_visible_modules(visible_modules)
        return {key for key in resume_content if not key.startswith("_")}

    def persist_resume_if_changed(
        self,
        *,
        resume_id: int,
        latest_resume_content: dict[str, Any] | None,
        original_resume: dict[str, Any],
    ) -> None:
        """用于只在内容确实变化时落库存储结构化简历。"""
        if latest_resume_content is None:
            return
        content = self.strip_visibility_meta(latest_resume_content)
        if content == self.strip_visibility_meta(original_resume):
            return
        self.store.update(resume_id, {"content": content})

    def sync_visibility_if_changed(
        self,
        *,
        resume: Any,
        resume_id: int,
        request_visible: list[str],
        latest_resume_content: dict[str, Any] | None,
    ) -> None:
        """用于把 Agent 改动的可见模块同步到 layout_config.visibleModules。"""
        if not isinstance(latest_resume_content, dict):
            return
        new_visible = latest_resume_content.get("_visible_modules")
        if not isinstance(new_visible, list) or new_visible == request_visible:
            return
        existing = resume.layout_config if isinstance(resume.layout_config, dict) else {}
        merged = {**existing, "visibleModules": list(new_visible)}
        self.store.update(resume_id, {"layout_config": merged})

    def strip_visibility_meta(self, content: dict[str, Any]) -> dict[str, Any]:
        """用于剥离仅作传输用途的 _visible_modules。"""
        return {key: value for key, value in content.items() if key != "_visible_modules"}


__all__ = ["ResumeAgentPersistence", "ResumePersistenceStore"]
