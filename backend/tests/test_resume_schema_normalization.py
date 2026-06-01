"""用于覆盖 test_resume_schema_normalization.py 对应的回归测试。"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.resume import (  # noqa: E402
    ResumeContent,
    dump_resume_content_for_frontend,
)


class ResumeSchemaNormalizationTests(unittest.TestCase):
    def test_work_experience_description_is_normalized_to_summary_and_highlights(self):
        """用于验证workexperiencedescriptionisnormalizedtosummaryandhighlights。"""
        content = ResumeContent.model_validate(
            {
                "work_experience": [
                    {
                        "company": "某科技公司",
                        "position": "后端工程师",
                        "duration": "2022-01 - 2024-01",
                        "description": "负责核心后台开发\n优化异步任务调度\n推动接口性能提升",
                    }
                ]
            }
        ).model_dump(mode="json")

        work = content["work_experience"][0]
        self.assertEqual(
            [item["text"] for item in work["highlights"]],
            ["负责核心后台开发", "优化异步任务调度", "推动接口性能提升"],
        )
        self.assertEqual(work["description"], "")

    def test_project_achievements_are_merged_into_highlights(self):
        """用于验证projectachievementsaremergedintohighlights。"""
        content = ResumeContent.model_validate(
            {
                "projects": [
                    {
                        "name": "简历优化系统",
                        "role": "后端开发",
                        "duration": "2024",
                        "description": "面向求职场景的简历优化产品",
                        "achievements": ["支持 AI 改写", "支持 PDF 导出"],
                    }
                ]
            }
        ).model_dump(mode="json")

        project = content["projects"][0]
        self.assertEqual(project["overview"], "面向求职场景的简历优化产品")
        self.assertEqual(
            [item["text"] for item in project["highlights"]],
            ["支持 AI 改写", "支持 PDF 导出"],
        )
        self.assertEqual(project["description"], "")
        self.assertEqual(project["summary"], "")
        self.assertEqual(project["achievements"], [])

    def test_existing_technologies_fields_remain_backward_compatible(self):
        """用于验证旧数据中的 technologies 字段仍可被 schema 读取。"""
        content = ResumeContent.model_validate(
            {
                "work_experience": [
                    {
                        "company": "世优",
                        "position": "Agent 开发",
                        "technologies": ["Python"],
                    }
                ],
                "projects": [
                    {
                        "name": "Chat Resume",
                        "technologies": ["SSE", "MCP"],
                    }
                ],
            }
        ).model_dump(mode="json")

        self.assertEqual(content["work_experience"][0]["technologies"], ["Python"])
        self.assertEqual(content["projects"][0]["technologies"], ["SSE", "MCP"])

    def test_education_description_is_normalized_to_summary_and_highlights(self):
        """用于验证educationdescriptionisnormalizedtosummaryandhighlights。"""
        content = ResumeContent.model_validate(
            {
                "education": [
                    {
                        "school": "北京大学",
                        "major": "计算机科学与技术",
                        "degree": "本科",
                        "duration": "2018-2022",
                        "description": "主修计算机基础课程\n获得国家奖学金",
                    }
                ]
            }
        ).model_dump(mode="json")

        education = content["education"][0]
        self.assertEqual(
            [item["text"] for item in education["highlights"]],
            ["主修计算机基础课程", "获得国家奖学金"],
        )
        self.assertEqual(education["description"], "")

    def test_string_education_is_normalized_into_single_item(self):
        """用于验证stringeducationisnormalizedintosingleitem。"""
        content = ResumeContent.model_validate(
            {
                "education": "北京大学 计算机科学与技术",
            }
        ).model_dump(mode="json")

        education = content["education"][0]
        self.assertEqual(education["school"], "北京大学 计算机科学与技术")
        self.assertEqual(
            [item["text"] for item in education["highlights"]],
            ["北京大学 计算机科学与技术"],
        )
        self.assertEqual(education["description"], "")

    def test_string_work_experience_is_normalized_into_single_item(self):
        """用于验证stringworkexperienceisnormalizedintosingleitem。"""
        content = ResumeContent.model_validate(
            {
                "work_experience": "负责核心后台开发\n优化异步任务调度",
            }
        ).model_dump(mode="json")

        work = content["work_experience"][0]
        self.assertEqual(work["company"], "")
        self.assertEqual(work["position"], "")
        self.assertEqual(
            [item["text"] for item in work["highlights"]],
            ["负责核心后台开发", "优化异步任务调度"],
        )
        self.assertEqual(work["description"], "")

    def test_dump_resume_content_for_frontend_keeps_editable_summary(self):
        """用于验证前端可编辑的个人简介会保留在保存响应中。"""
        content = dump_resume_content_for_frontend(
            {
                "meta": {"language": "zh-CN"},
                "parsing_quality": 0.92,
                "parsing_method": "ai",
                "job_application": {"target_title": "AI Agent 开发工程师"},
                "personal_info": {"name": "彭世雄", "email": "test@example.com"},
                "summary": {"text": "AI Agent 开发工程师，擅长多 Agent 系统与 RAG 应用。"},
                "skills": [],
                "languages": [{"name": "英语", "level": "CET-6"}],
                "custom_sections": [{"title": "其他", "content": "隐藏字段"}],
                "projects": [
                    {
                        "name": "Chat Resume",
                        "role": "开发者",
                        "duration": "2025",
                        "description": "AI 求职辅导平台",
                    }
                ],
            }
        )

        self.assertEqual(
            content,
            {
                "parsing_quality": 0.92,
                "parsing_method": "ai",
                "job_application": {"target_title": "AI Agent 开发工程师"},
                "personal_info": {"name": "彭世雄", "email": "test@example.com"},
                "summary": {"text": "AI Agent 开发工程师，擅长多 Agent 系统与 RAG 应用。"},
                "projects": [
                    {
                        "id": content["projects"][0]["id"],
                        "name": "Chat Resume",
                        "overview": "AI 求职辅导平台",
                        "role": "开发者",
                        "duration": "2025",
                    }
                ],
            },
        )

    def test_personal_info_photo_url_is_preserved_for_frontend(self):
        """用于验证个人照片地址会保留给前端编辑器和预览。"""
        content = dump_resume_content_for_frontend(
            {
                "personal_info": {
                    "name": "彭世雄",
                    "photo_url": "data:image/png;base64,avatar",
                }
            }
        )

        self.assertEqual(
            content["personal_info"],
            {
                "name": "彭世雄",
                "photo_url": "data:image/png;base64,avatar",
            },
        )


if __name__ == "__main__":
    unittest.main()
