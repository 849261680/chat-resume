"""用于提供简历 Agent 记忆工具的受限实现。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any

from app.infra.config import settings


@dataclass(frozen=True)
class MemoryEntry:
    """用于表达一条从 Markdown 解析出的记忆。"""

    memory_id: str
    kind: str
    scope: str
    enabled: bool
    content: str
    reason: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """用于把记忆转换成工具返回的稳定字典。"""
        return {
            "memory_id": self.memory_id,
            "kind": self.kind,
            "scope": self.scope,
            "enabled": self.enabled,
            "content": self.content,
            "reason": self.reason,
            "updated_at": self.updated_at,
        }


class MemoryMarkdownStore:
    """用于把用户记忆限制在固定 Markdown 文件中读写。"""

    def __init__(self, *, memory_dir: str | None, user_id: int | None):
        """用于初始化当前用户的记忆文件路径。"""
        self.user_id = user_id
        self.base_dir = Path(memory_dir or settings.USER_MEMORY_DIR)

    def read(
        self,
        *,
        scope: str,
        query: str = "",
        resume_id: int | None = None,
    ) -> list[MemoryEntry]:
        """用于读取启用且匹配 scope/query 的记忆。"""
        effective_scope = _effective_scope(scope, resume_id)
        entries = [entry for entry in self._read_all() if entry.enabled]
        scoped = [entry for entry in entries if entry.scope == effective_scope]
        if not query.strip():
            return scoped[:10]
        return [entry for entry in scoped if query.strip() in entry.content][:10]

    def append(
        self,
        *,
        scope: str,
        kind: str,
        content: str,
        resume_id: int | None = None,
        reason: str = "",
    ) -> MemoryEntry:
        """用于追加一条新的长期记忆。"""
        entry = MemoryEntry(
            memory_id=f"mem_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}",
            kind=kind,
            scope=_effective_scope(scope, resume_id),
            enabled=True,
            content=content.strip(),
            reason=reason.strip(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        entries = [*self._read_all(), entry]
        self._write_all(entries)
        return entry

    def replace(
        self,
        *,
        memory_id: str,
        scope: str,
        kind: str,
        content: str,
        resume_id: int | None = None,
        reason: str = "",
    ) -> MemoryEntry | None:
        """用于替换指定 scope 内的一条已有记忆。"""
        entries = self._read_all()
        effective_scope = _effective_scope(scope, resume_id)
        updated = _replace_entry(
            entries,
            memory_id=memory_id,
            scope=effective_scope,
            kind=kind,
            content=content,
            reason=reason,
        )
        if updated is not None:
            self._write_all(entries)
        return updated

    def disable(
        self,
        *,
        memory_id: str,
        scope: str,
        resume_id: int | None = None,
        reason: str = "",
    ) -> MemoryEntry | None:
        """用于停用指定 scope 内的一条已有记忆。"""
        entries = self._read_all()
        effective_scope = _effective_scope(scope, resume_id)
        disabled = _disable_entry(
            entries,
            memory_id=memory_id,
            scope=effective_scope,
            reason=reason,
        )
        if disabled is not None:
            self._write_all(entries)
        return disabled

    def _memory_file(self) -> Path:
        """用于返回当前用户固定的 Markdown 记忆文件。"""
        if self.user_id is None:
            raise ValueError("user_id is required for memory tools")
        return self.base_dir / str(self.user_id) / "resume_memory.md"

    def _read_all(self) -> list[MemoryEntry]:
        """用于读取并解析全部 Markdown 记忆。"""
        path = self._memory_file()
        if not path.exists():
            return []
        return _parse_memory_markdown(path.read_text(encoding="utf-8"))

    def _write_all(self, entries: list[MemoryEntry]) -> None:
        """用于原子写入完整 Markdown 记忆文件。"""
        path = self._memory_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(_render_memory_markdown(entries), encoding="utf-8")
        tmp_path.replace(path)


def update_memory(
    resume_content: dict[str, Any],
    operation: str,
    scope: str,
    kind: str = "preference",
    content: str = "",
    memory_id: str = "",
    reason: str = "",
    user_id: int | None = None,
    resume_id: int | None = None,
    memory_dir: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """用于更新当前用户或简历的长期记忆。"""
    if operation in {"append", "replace"} and not content.strip():
        return {"success": False, "message": "记忆内容不能为空"}
    if operation in {"replace", "disable"} and not memory_id.strip():
        return {"success": False, "message": "memory_id 不能为空"}
    if dry_run:
        return _memory_dry_run_result(
            operation=operation,
            scope=scope,
            kind=kind,
            content=content,
            memory_id=memory_id,
            reason=reason,
        )
    store = MemoryMarkdownStore(memory_dir=memory_dir, user_id=user_id)
    entry = _apply_memory_operation(
        store,
        operation=operation,
        scope=scope,
        kind=kind,
        content=content,
        memory_id=memory_id,
        resume_id=resume_id,
        reason=reason,
    )
    if entry is None:
        return {"success": False, "message": "未找到要更新的记忆"}
    return {
        "success": True,
        "terminate": True,
        "operation": operation,
        "scope": scope,
        "memory_id": entry.memory_id,
        "kind": entry.kind,
        "content": entry.content,
        "reason": entry.reason,
        "message": "记忆已更新",
    }


def _memory_dry_run_result(
    *,
    operation: str,
    scope: str,
    kind: str,
    content: str,
    memory_id: str,
    reason: str,
) -> dict[str, Any]:
    """用于预览记忆更新，不产生持久化副作用。"""
    return {
        "success": True,
        "dry_run": True,
        "operation": operation,
        "scope": scope,
        "memory_id": memory_id,
        "kind": kind,
        "content": content.strip(),
        "reason": reason.strip(),
        "message": "记忆将被更新",
    }


def read_memory(
    resume_content: dict[str, Any],
    scope: str,
    query: str = "",
    user_id: int | None = None,
    resume_id: int | None = None,
    memory_dir: str | None = None,
) -> dict[str, Any]:
    """用于读取当前用户或简历的长期记忆。"""
    store = MemoryMarkdownStore(memory_dir=memory_dir, user_id=user_id)
    memories = [
        entry.to_dict()
        for entry in store.read(scope=scope, query=query, resume_id=resume_id)
    ]
    return {
        "success": True,
        "scope": scope,
        "query": query,
        "memories": memories,
        "message": f"读取到 {len(memories)} 条记忆",
    }


def _apply_memory_operation(
    store: MemoryMarkdownStore,
    *,
    operation: str,
    scope: str,
    kind: str,
    content: str,
    memory_id: str,
    resume_id: int | None,
    reason: str,
) -> MemoryEntry | None:
    """用于把 update_memory 操作分发到具体存储动作。"""
    if operation == "append":
        return store.append(
            scope=scope,
            kind=kind,
            content=content,
            resume_id=resume_id,
            reason=reason,
        )
    if operation == "replace":
        return store.replace(
            memory_id=memory_id,
            scope=scope,
            kind=kind,
            content=content,
            resume_id=resume_id,
            reason=reason,
        )
    if operation == "disable":
        return store.disable(
            memory_id=memory_id,
            scope=scope,
            resume_id=resume_id,
            reason=reason,
        )
    return None


def _effective_scope(scope: str, resume_id: int | None) -> str:
    """用于把公开 scope 转成 Markdown 内部隔离 scope。"""
    if scope != "resume":
        return "user"
    if resume_id is None:
        raise ValueError("resume_id is required for resume memory scope")
    return f"resume:{resume_id}"


def _replace_entry(
    entries: list[MemoryEntry],
    *,
    memory_id: str,
    scope: str,
    kind: str,
    content: str,
    reason: str,
) -> MemoryEntry | None:
    """用于在列表中原位替换一条记忆。"""
    for index, entry in enumerate(entries):
        if entry.memory_id != memory_id or entry.scope != scope:
            continue
        replacement = MemoryEntry(
            memory_id=entry.memory_id,
            kind=kind,
            scope=entry.scope,
            enabled=True,
            content=content.strip(),
            reason=reason.strip(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        entries[index] = replacement
        return replacement
    return None


def _disable_entry(
    entries: list[MemoryEntry],
    *,
    memory_id: str,
    scope: str,
    reason: str,
) -> MemoryEntry | None:
    """用于在列表中原位停用一条记忆。"""
    for index, entry in enumerate(entries):
        if entry.memory_id != memory_id or entry.scope != scope:
            continue
        disabled = MemoryEntry(
            memory_id=entry.memory_id,
            kind=entry.kind,
            scope=entry.scope,
            enabled=False,
            content=entry.content,
            reason=reason.strip() or entry.reason,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        entries[index] = disabled
        return disabled
    return None


def _parse_memory_markdown(markdown: str) -> list[MemoryEntry]:
    """用于把受限 Markdown 格式解析成记忆条目。"""
    entries: list[MemoryEntry] = []
    for block in markdown.split("\n## "):
        if not block.startswith("mem_"):
            continue
        entry = _parse_memory_block(block)
        if entry is not None:
            entries.append(entry)
    return entries


def _parse_memory_block(block: str) -> MemoryEntry | None:
    """用于解析单个 Markdown 记忆块。"""
    lines = block.strip().splitlines()
    if not lines:
        return None
    memory_id = lines[0].strip().lstrip("#").strip()
    metadata: dict[str, str] = {}
    content_lines: list[str] = []
    in_content = False
    for line in lines[1:]:
        if not in_content and not line.strip():
            in_content = True
            continue
        if in_content:
            content_lines.append(line)
            continue
        key, _, value = line.partition(":")
        metadata[key.strip()] = value.strip()
    return MemoryEntry(
        memory_id=memory_id,
        kind=metadata.get("kind", "preference"),
        scope=metadata.get("scope", "user"),
        enabled=metadata.get("enabled", "true") == "true",
        content="\n".join(content_lines).strip(),
        reason=metadata.get("reason", ""),
        updated_at=metadata.get("updated_at", ""),
    )


def _render_memory_markdown(entries: list[MemoryEntry]) -> str:
    """用于把记忆条目渲染成稳定 Markdown。"""
    blocks = ["# Resume Agent Memory", ""]
    for entry in entries:
        blocks.extend(
            [
                f"## {entry.memory_id}",
                f"kind: {entry.kind}",
                f"scope: {entry.scope}",
                f"enabled: {'true' if entry.enabled else 'false'}",
                f"reason: {entry.reason}",
                f"updated_at: {entry.updated_at}",
                "",
                entry.content,
                "",
            ]
        )
    return "\n".join(blocks)


__all__ = ["MemoryMarkdownStore", "read_memory", "update_memory"]
