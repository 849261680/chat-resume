"""用于加载优秀简历 Agent 的黄金验收样例。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CASE_PATH = (
    Path(__file__).resolve().parents[4]
    / "eval"
    / "cases"
    / "excellent_resume_agent_cases.json"
)


def load_excellent_resume_cases(path: Path | None = None) -> list[dict[str, Any]]:
    """用于读取优秀简历 Agent 黄金样例列表。"""
    case_path = path or _CASE_PATH
    with case_path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("excellent resume cases root must be a list")
    return [case for case in data if isinstance(case, dict)]


__all__ = ["load_excellent_resume_cases"]
