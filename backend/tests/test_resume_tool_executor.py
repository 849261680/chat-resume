"""用于覆盖 test_resume_tool_executor.py 对应的回归测试。"""

import sys
import unittest
from pathlib import Path
from typing import Any, cast

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.executor import ResumeToolExecutor  # noqa: E402


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

    def test_show_section_can_show_hidden_section(self):
        """用于验证show_section打开关闭的板块开关，不改动内容。"""
        skills_data = [{"id": "skill_1", "category": "AI", "items": ["Agent"]}]
        resume: dict[str, Any] = {
            "projects": [],
            "skills": skills_data,
            "_visible_modules": ["projects"],
        }
        executor = ResumeToolExecutor()

        result = cast(dict[str, Any], executor.execute(
            tool_name="show_section",
            tool_input={
                "section": "skills",
                "reason": "恢复技能板块",
            },
            context={"resume_content": resume, "allowed_sections": {"projects"}},
        ))

        self.assertTrue(result["result"]["success"])
        self.assertEqual(result["result"]["updated_section"], "skills")
        self.assertIn("skills", resume["_visible_modules"])
        self.assertEqual(resume["skills"], skills_data)
