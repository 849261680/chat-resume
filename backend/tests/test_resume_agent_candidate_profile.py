"""用于覆盖简历 Agent 候选人背景档案上下文。"""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.candidate_profile import (  # noqa: E402
    load_candidate_profile_context,
)
from app.agents.resume.prompt_context import build_resume_prompt_context  # noqa: E402
from app.prompts import load_prompt  # noqa: E402
from app.tools.resume.memory_tool import update_memory  # noqa: E402


def test_candidate_profile_context_reports_missing_fields_without_memory():
    """用于验证没有长期记忆时会提示 Agent 追问关键背景。"""
    profile = load_candidate_profile_context(
        user_id=None,
        resume_id=None,
    )

    assert profile.has_entries is False
    assert "候选人背景档案尚未建立" in profile.markdown
    assert "缺失关键信息" in profile.markdown


def test_candidate_profile_context_reads_user_and_resume_memory():
    """用于验证候选人背景档案会合并用户级和简历级记忆。"""
    with TemporaryDirectory() as memory_dir:
        update_memory(
            {},
            operation="append",
            scope="user",
            kind="target_strategy",
            content="目标岗位：AI Agent 工程师",
            user_id=7,
            memory_dir=memory_dir,
        )
        update_memory(
            {},
            operation="append",
            scope="resume",
            kind="fact_constraint",
            content="Chat Resume 项目由本人负责 ReAct Agent 运行时和工具确认链路。",
            user_id=7,
            resume_id=42,
            memory_dir=memory_dir,
        )

        profile = load_candidate_profile_context(
            user_id=7,
            resume_id=42,
            memory_dir=memory_dir,
        )

    assert profile.has_entries is True
    assert "AI Agent 工程师" in profile.markdown
    assert "ReAct Agent 运行时" in profile.markdown
    assert "不得自行补全" in profile.markdown


def test_resume_system_prompt_includes_candidate_profile_rules():
    """用于验证真实系统提示词包含候选人背景档案和追问规则。"""
    context = build_resume_prompt_context(
        {
            "resume_content": {"projects": []},
            "candidate_profile": "候选人背景档案尚未建立。\n缺失关键信息：目标岗位。",
        }
    )
    prompt = load_prompt("resume_agent").render(**context)

    assert "## 候选人背景档案" in prompt
    assert "缺失关键信息：目标岗位" in prompt
    assert "先问最多 3 个关键问题" in prompt
    assert "update_memory" in prompt
    assert "question 必须是直接问用户的疑问句" in prompt
    assert "不要把 question 写成" in prompt
