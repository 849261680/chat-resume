"""用于覆盖 test_resume_tool_executor.py 对应的回归测试。"""

import asyncio
import inspect
import sys
import unittest
from pathlib import Path
from typing import Any, Awaitable, cast

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.executor import ResumeToolExecutor  # noqa: E402


class FakeJobMatchAnalyzer:
    """用于模拟岗位匹配语义分析器。"""

    async def analyze(self, *, jd_text: str, resume_text: str):
        """用于返回可预测的岗位匹配结果。"""
        return {
            "matched_keywords": ["Agent"],
            "missing_keywords": ["Redis"],
            "fact_gaps": ["需要补充 Redis 相关真实经历"],
        }


class ResumeToolExecutorTests(unittest.TestCase):
    def test_execute_wraps_success_result(self):
        """用于验证executewrapssuccess结果。"""
        resume = {
            "projects": [{"id": "proj_1", "name": "Chat Resume", "overview": "旧简介"}]
        }
        executor = ResumeToolExecutor()

        result = cast(dict[str, Any], executor.execute(
            tool_name="update_overview",
            tool_input={
                "section": "projects",
                "item_id": "proj_1",
                "overview": "新简介",
            },
            context={"resume_content": resume, "allowed_sections": {"projects"}},
        ))

        self.assertTrue(result["result"]["success"])
        self.assertEqual(result["tool_name"], "优化简介")
        self.assertEqual(resume["projects"][0]["overview"], "新简介")


    def test_execute_rejects_internal_is_current_field(self):
        """用于验证条目字段工具不允许模型直接修改内部派生字段。"""
        resume = {
            "work_experience": [
                {
                    "id": "work_1",
                    "company": "示例公司",
                    "duration": "2025.08-至今",
                    "is_current": False,
                }
            ]
        }
        executor = ResumeToolExecutor()

        result = cast(dict[str, Any], executor.execute(
            tool_name="update_item_fields",
            tool_input={
                "section": "work_experience",
                "item_id": "work_1",
                "fields": {"is_current": True},
            },
            context={"resume_content": resume, "allowed_sections": {"work_experience"}},
        ))

        self.assertFalse(result["result"]["success"])
        self.assertIn("is_current", result["result"]["message"])
        self.assertFalse(resume["work_experience"][0]["is_current"])

    def test_execute_wraps_async_job_match_summary_result(self):
        """用于验证异步只读工具仍返回统一工具结果结构。"""
        resume = {
            "job_application": {"jd_text": "要求 Agent 和 Redis 经验。"},
            "projects": [{"name": "Chat Resume", "overview": "Agent 简历工具"}],
        }
        executor = ResumeToolExecutor()

        pending = executor.execute(
            tool_name="generate_job_match_summary",
            tool_input={},
            context={
                "resume_content": resume,
                "confirmed_diff_items": [],
                "semantic_analyzer": FakeJobMatchAnalyzer(),
            },
        )

        self.assertTrue(inspect.isawaitable(pending))
        result = asyncio.run(_await_tool_result(cast(Awaitable[dict[str, Any]], pending)))
        self.assertEqual(result["tool_name"], "岗位匹配摘要")
        self.assertTrue(result["result"]["success"])
        self.assertIn("job_match_summary", result["result"])

    def test_execute_returns_structured_hidden_section_error(self):
        """用于验证executereturnsstructuredhiddensection错误。"""
        executor = ResumeToolExecutor()

        result = cast(dict[str, Any], executor.execute(
            tool_name="add_bullet",
            tool_input={
                "section": "projects",
                "item_id": "proj_1",
                "text": "新增成果",
            },
            context={
                "resume_content": {"projects": []},
                "allowed_sections": {"skills"},
            },
        ))

        self.assertFalse(result["result"]["success"])
        self.assertEqual(result["result"]["error"]["type"], "hidden_section")
        self.assertFalse(result["result"]["error"]["recoverable"])

    def test_add_resume_item_can_create_missing_skills_section(self):
        """用于验证新增技能条目不依赖简历里已有 skills 数组。"""
        resume = {"projects": []}
        executor = ResumeToolExecutor()

        result = cast(dict[str, Any], executor.execute(
            tool_name="add_resume_item",
            tool_input={
                "section": "skills",
                "item": {"category": "AI 工具", "items": ["Codex", "Cursor"]},
                "source": "用户要求补充 AI 编程工具经验",
                "reason": "补充 JD 加分项",
            },
            context={"resume_content": resume, "allowed_sections": {"projects"}},
        ))

        self.assertTrue(result["result"]["success"])
        self.assertEqual(result["result"]["updated_section"], "skills")
        self.assertEqual(resume["skills"][0]["category"], "AI 工具")
        self.assertEqual(resume["skills"][0]["items"], ["Codex", "Cursor"])


async def _await_tool_result(
    pending: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    """用于在同步 unittest 中等待异步工具结果。"""
    return await pending
