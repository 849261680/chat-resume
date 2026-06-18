"""用于定义后端到前端打印页的简历载荷契约。"""

from __future__ import annotations

import base64
import json
from typing import Any

RESUME_PRINT_PAYLOAD_FIELDS = ("content", "template", "layout_config")


def build_resume_print_payload(
    *,
    resume_content: dict[str, Any],
    template: str,
    layout_config: dict[str, Any] | None = None,
) -> str:
    """用于编码前端打印页需要的稳定载荷。"""
    payload = materialize_resume_print_payload(
        resume_content=resume_content,
        template=template,
        layout_config=layout_config,
    )
    return base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("utf-8")


def decode_resume_print_payload(encoded_payload: str) -> dict[str, Any]:
    """用于测试和调试时解码打印页载荷。"""
    raw = base64.urlsafe_b64decode(encoded_payload.encode("utf-8")).decode("utf-8")
    decoded = json.loads(raw)
    return materialize_resume_print_payload(
        resume_content=decoded.get("content"),
        template=decoded.get("template"),
        layout_config=decoded.get("layout_config"),
    )


def materialize_resume_print_payload(
    *,
    resume_content: Any,
    template: Any,
    layout_config: Any = None,
) -> dict[str, Any]:
    """用于按契约字段顺序生成打印页载荷字典。"""
    content = resume_content if isinstance(resume_content, dict) else {}
    normalized_template = str(template or "default").strip() or "default"
    normalized_layout = layout_config if isinstance(layout_config, dict) else None
    return {
        "content": content,
        "template": normalized_template,
        "layout_config": normalized_layout,
    }


__all__ = [
    "RESUME_PRINT_PAYLOAD_FIELDS",
    "build_resume_print_payload",
    "decode_resume_print_payload",
    "materialize_resume_print_payload",
]
