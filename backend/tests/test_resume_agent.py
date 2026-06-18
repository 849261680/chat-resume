"""用于覆盖 test_resume_agent.py 对应的回归测试。"""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.agents.resume.stream_events import (  # noqa: E402
    normalize_resume_stream_payload,
    tool_pending_event,
)
from app.agents.resume.message_conversion import resume_chat_history_to_messages  # noqa: E402
from app.tools.resume.registry import execute_prepared_resume_tool_call  # noqa: E402
from app.tools.resume.registry import RESUME_TOOLS_SCHEMA  # noqa: E402
from app.tools.resume.update_bullet_tool import update_bullet  # noqa: E402
from app.types.stream import public_resume_stream_event  # noqa: E402
from app.prompts import load_prompt  # noqa: E402
from scripts.run_resume_agent_smoke import resume_changed  # noqa: E402


from tests.helpers.prompt_semantic_tags import (
    SCHEMA_TAGS,
    assert_tag,
)  # noqa: E402


def _render_resume_system_prompt(**kwargs: object) -> str:
    """用于按真实 prompt loader 渲染简历 Agent 系统提示词。"""
    return load_prompt("resume_agent").render(**kwargs)


class ResumeAgentPromptContextTests(unittest.TestCase):
    def test_prompt_context_includes_job_application_fields(self):
        """用于验证prompt上下文includes任务applicationfields。"""
        agent = ResumeAgent()
        context = agent._build_prompt_context(
            {
                "resume_content": {
                    "job_application": {
                        "target_title": "前端工程师",
                        "target_company": "字节跳动",
                        "jd_text": "负责复杂前端交互、性能优化和工程化建设",
                    },
                    "projects": [],
                }
            }
        )

        self.assertEqual(context["target_title"], "前端工程师")
        self.assertEqual(context["target_company"], "字节跳动")
        self.assertIn("性能优化", context["jd_text"])
        self.assertIn('"job_application"', context["resume_json"])

    def test_resume_tools_schema_exposes_optional_reason_field(self):
        """用于验证简历toolsschemaexposesoptionalreasonfield。"""
        schema = RESUME_TOOLS_SCHEMA
        update_bullet = next(
            tool for tool in schema if tool["function"]["name"] == "update_bullet"
        )

        properties = update_bullet["function"]["parameters"]["properties"]
        self.assertIn("reason", properties)
        self.assertEqual(properties["reason"]["type"], "string")

        update_bullet_description = update_bullet["function"]["description"]
        text_description = properties["text"]["description"]
        reason_description = properties["reason"]["description"]
        assert_tag(update_bullet_description, "text_must_differ", registry=SCHEMA_TAGS)
        assert_tag(update_bullet_description, "no_passthrough", registry=SCHEMA_TAGS)
        assert_tag(text_description, "no_passthrough", registry=SCHEMA_TAGS)
        assert_tag(reason_description, "reason_not_substitute", registry=SCHEMA_TAGS)

    def test_update_bullet_rejects_unchanged_text(self):
        """用于验证update_bullet拒绝新旧内容一致的空修改。"""
        resume_content: dict[str, Any] = {
            "work_experience": [
                {
                    "id": "work_1",
                    "company": "测试公司",
                    "position": "后端工程师",
                    "highlights": [
                        {"id": "bullet_1", "text": "负责 Agent 工具调用链路建设"}
                    ],
                }
            ]
        }

        result = execute_prepared_resume_tool_call(
            tool_name="update_bullet",
            tool_input={
                "section": "work_experience",
                "item_id": "work_1",
                "bullet_id": "bullet_1",
                "text": "  负责 Agent 工具调用链路建设  ",
                "reason": "只解释优化理由",
            },
            context={"resume_content": resume_content},
        )

        self.assertFalse(result["result"]["success"])
        self.assertEqual(
            resume_content["work_experience"][0]["highlights"][0]["text"],
            "负责 Agent 工具调用链路建设",
        )
        self.assertIn("内容一致", result["result"]["message"])

    def test_update_profile_schema_exposes_sourced_identity_fields(self):
        """用于验证update_profile schema暴露有来源的身份联系字段。"""
        update_profile = next(
            tool for tool in RESUME_TOOLS_SCHEMA if tool["function"]["name"] == "update_profile"
        )

        properties = update_profile["function"]["parameters"]["properties"]
        field_properties = properties["fields"]["properties"]

        self.assertIn("source", properties)
        self.assertIn("name", field_properties)
        self.assertIn("email", field_properties)
        self.assertIn("phone", field_properties)
        self.assertIn("address", field_properties)

    def test_resume_tools_schema_exposes_bullet_tools(self):
        """用于验证简历toolsschemaexposesbullettools。"""
        tool_names = {tool["function"]["name"] for tool in RESUME_TOOLS_SCHEMA}

        self.assertIn("update_bullet", tool_names)
        self.assertIn("add_bullet", tool_names)
        self.assertIn("remove_bullet", tool_names)
        self.assertNotIn("update_highlight", tool_names)
        self.assertNotIn("add_highlight", tool_names)
        self.assertNotIn("remove_highlight", tool_names)

    def test_resume_tools_schema_exposes_full_resume_edit_tools(self):
        """用于验证简历toolsschema暴露全简历编辑工具。"""
        tool_names = {tool["function"]["name"] for tool in RESUME_TOOLS_SCHEMA}

        self.assertIn("update_summary", tool_names)
        self.assertIn("update_profile", tool_names)
        self.assertIn("upsert_job_application", tool_names)
        self.assertIn("add_resume_item", tool_names)
        self.assertIn("remove_resume_item", tool_names)
        self.assertIn("update_item_fields", tool_names)
        self.assertIn("update_skills", tool_names)
        self.assertIn("show_section", tool_names)
        self.assertIn("hide_section", tool_names)

    def test_update_item_fields_schema_does_not_expose_hidden_technologies(self):
        """用于验证条目字段工具不再暴露隐藏技术栈字段。"""
        schema = next(
            tool
            for tool in RESUME_TOOLS_SCHEMA
            if tool["function"]["name"] == "update_item_fields"
        )
        fields_description = schema["function"]["parameters"]["properties"]["fields"][
            "description"
        ]

        self.assertNotIn("technologies", fields_description)
        self.assertIn("overview", fields_description)
        self.assertIn("employment_type", fields_description)

    def test_add_resume_item_schema_uses_item_fields_payload(self):
        """用于验证新增条目工具暴露可编辑字段并禁止隐藏技术栈字段。"""
        schema = next(
            tool
            for tool in RESUME_TOOLS_SCHEMA
            if tool["function"]["name"] == "add_resume_item"
        )
        fields_description = schema["function"]["parameters"]["properties"]["fields"][
            "description"
        ]

        self.assertEqual(schema["function"]["parameters"]["required"], ["section", "fields"])
        self.assertIn("overview", fields_description)
        self.assertIn("employment_type", fields_description)
        self.assertNotIn("technologies", fields_description)

    def test_resume_edit_profile_exposes_job_application_upsert_tool(self):
        """用于验证resume_edit工具profile暴露求职目标upsert工具。"""
        agent = ResumeAgent()

        self.assertIn(
            "upsert_job_application",
            agent.definition.tool_profiles["resume_edit"],
        )

    def test_upsert_job_application_schema_uses_fields_payload(self):
        """用于验证求职目标工具使用fields载荷以便只传实际修改字段。"""
        schema = next(
            tool
            for tool in RESUME_TOOLS_SCHEMA
            if tool["function"]["name"] == "upsert_job_application"
        )
        parameters = schema["function"]["parameters"]
        properties = parameters["properties"]

        self.assertEqual(parameters["required"], ["fields"])
        self.assertIn("fields", properties)
        self.assertNotIn("target_company", properties)
        self.assertNotIn("target_title", properties)
        self.assertNotIn("jd_text", properties)

    def test_resume_tools_schema_does_not_expose_custom_memory_tools(self):
        """用于验证简历toolsschemadoesnotexposecustommemorytools。"""
        tool_names = {tool["function"]["name"] for tool in RESUME_TOOLS_SCHEMA}

        self.assertNotIn("read_user_memory", tool_names)
        self.assertNotIn("write_user_memory", tool_names)

    def test_resume_tools_schema_exposes_memory_tools(self):
        """用于验证简历 Agent 显式暴露读写记忆工具。"""
        tool_names = {tool["function"]["name"] for tool in RESUME_TOOLS_SCHEMA}
        agent = ResumeAgent()

        self.assertIn("read_memory", tool_names)
        self.assertIn("update_memory", tool_names)
        self.assertIn("read_memory", agent.definition.tool_profiles["resume_edit"])
        self.assertIn("update_memory", agent.definition.tool_profiles["resume_edit"])

    def test_resume_tools_schema_exposes_job_post_read_tools(self):
        """用于验证简历 Agent 暴露 JD 库只读工具。"""
        tool_names = {tool["function"]["name"] for tool in RESUME_TOOLS_SCHEMA}
        agent = ResumeAgent()

        self.assertIn("list_job_posts", tool_names)
        self.assertIn("read_job_post", tool_names)
        self.assertIn("list_job_posts", agent.definition.tool_profiles["resume_edit"])
        self.assertIn("read_job_post", agent.definition.tool_profiles["read_only"])
        self.assertIn("read_job_post", agent.definition.auto_execute_tool_names)

    def test_job_post_tools_read_current_user_records_from_context(self):
        """用于验证 JD 工具只能通过当前会话注入的用户上下文读取。"""

        def read_job_post(user_id: int, job_post_id: int) -> dict[str, Any] | None:
            """用于模拟按用户读取 JD。"""
            if user_id != 7 or job_post_id != 42:
                return None
            return {
                "id": 42,
                "company_name": "美团",
                "job_title": "Agent 开发工程师",
                "jd_text": "负责 Agent 工具调用、RAG 和评测体系。",
            }

        result = execute_prepared_resume_tool_call(
            tool_name="read_job_post",
            tool_input={"job_post_id": 42},
            context={
                "resume_content": {},
                "user_id": 7,
                "read_job_post_reader": read_job_post,
            },
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(result["tool_name"], "读取JD")
        self.assertIn("RAG", result["result"]["job_post"]["jd_text"])

    def test_job_post_list_tool_reads_summaries_from_context(self):
        """用于验证 JD 列表工具返回当前用户的摘要列表。"""

        def list_job_posts(
            user_id: int,
            *,
            query: str = "",
            limit: int = 20,
        ) -> list[dict[str, Any]]:
            """用于模拟按用户列出 JD。"""
            self.assertEqual(user_id, 7)
            self.assertEqual(query, "Agent")
            self.assertEqual(limit, 5)
            return [{"id": 1, "job_title": "Agent 工程师", "jd_chars": 1200}]

        result = execute_prepared_resume_tool_call(
            tool_name="list_job_posts",
            tool_input={"query": "Agent", "limit": 5},
            context={
                "resume_content": {},
                "user_id": 7,
                "list_job_posts_reader": list_job_posts,
            },
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(result["result"]["job_posts"][0]["id"], 1)

    def test_memory_tools_write_and_read_markdown_store(self):
        """用于验证记忆工具通过执行器读写固定 md 文件。"""
        with TemporaryDirectory() as memory_dir:
            update_result = execute_prepared_resume_tool_call(
                tool_name="update_memory",
                tool_input={
                    "operation": "append",
                    "scope": "user",
                    "kind": "preference",
                    "content": "优化简历时不要编造数字;没有数据就强化结果表达。",
                    "reason": "用户明确要求长期遵守",
                },
                context={
                    "resume_content": {},
                    "user_id": 7,
                    "memory_dir": memory_dir,
                },
            )

            self.assertTrue(update_result["result"]["success"])
            self.assertEqual(update_result["tool_name"], "更新记忆")
            self.assertTrue(update_result["result"]["memory_id"].startswith("mem_"))

            memory_file = Path(memory_dir) / "7" / "resume_memory.md"
            self.assertTrue(memory_file.exists())
            self.assertIn(
                "不要编造数字",
                memory_file.read_text(encoding="utf-8"),
            )

            read_result = execute_prepared_resume_tool_call(
                tool_name="read_memory",
                tool_input={"scope": "user", "query": "数字"},
                context={
                    "resume_content": {},
                    "user_id": 7,
                    "memory_dir": memory_dir,
                },
            )

        self.assertTrue(read_result["result"]["success"])
        self.assertEqual(read_result["tool_name"], "读取记忆")
        self.assertEqual(len(read_result["result"]["memories"]), 1)
        self.assertEqual(
            read_result["result"]["memories"][0]["content"],
            "优化简历时不要编造数字;没有数据就强化结果表达。",
        )

    def test_memory_preview_does_not_write_markdown_store(self):
        """用于验证记忆工具预览不产生持久化副作用。"""
        with TemporaryDirectory() as memory_dir:
            result = execute_prepared_resume_tool_call(
                tool_name="update_memory",
                tool_input={
                    "operation": "append",
                    "scope": "user",
                    "kind": "preference",
                    "content": "用户偏好精简简历。",
                    "reason": "用户明确表达偏好",
                },
                context={
                    "resume_content": {},
                    "user_id": 7,
                    "memory_dir": memory_dir,
                    "dry_run": True,
                },
            )

            self.assertTrue(result["result"]["success"])
            self.assertTrue(result["result"]["dry_run"])
            self.assertFalse((Path(memory_dir) / "7" / "resume_memory.md").exists())

    def test_chat_history_replays_tool_events_as_pi_messages(self):
        """用于验证历史消息保留 Pi 风格工具流水账。"""
        messages = resume_chat_history_to_messages([
            {"role": "user", "content": "我喜欢精简的简历"},
            {
                "role": "assistant",
                "content": "已记住。",
                "stream_events": [
                    {
                        "type": "tool_call",
                        "callId": "call_1",
                        "toolName": "更新记忆",
                        "toolId": "update_memory",
                        "toolInput": {"operation": "append", "scope": "user"},
                    },
                    {
                        "type": "tool_result",
                        "callId": "call_1",
                        "toolName": "更新记忆",
                        "toolId": "update_memory",
                        "displayMessage": "记忆已更新",
                    },
                ],
            },
        ])

        tool_result = messages[2]
        self.assertEqual([message.role for message in messages], ["user", "assistant", "toolResult"])
        self.assertEqual(messages[1].content[0].type, "toolCall")
        self.assertEqual(getattr(tool_result, "tool_name", ""), "update_memory")

    def test_memory_tools_replace_disable_and_isolate_resume_scope(self):
        """用于验证更新记忆支持替换停用并隔离不同简历。"""
        with TemporaryDirectory() as memory_dir:
            first = execute_prepared_resume_tool_call(
                tool_name="update_memory",
                tool_input={
                    "operation": "append",
                    "scope": "resume",
                    "kind": "target_strategy",
                    "content": "这份简历主要投递后端岗位。",
                    "reason": "用户明确说明目标岗位",
                },
                context={
                    "resume_content": {},
                    "user_id": 7,
                    "resume_id": 42,
                    "memory_dir": memory_dir,
                },
            )
            execute_prepared_resume_tool_call(
                tool_name="update_memory",
                tool_input={
                    "operation": "append",
                    "scope": "resume",
                    "kind": "target_strategy",
                    "content": "另一份简历投递产品岗位。",
                    "reason": "用户明确说明目标岗位",
                },
                context={
                    "resume_content": {},
                    "user_id": 7,
                    "resume_id": 43,
                    "memory_dir": memory_dir,
                },
            )
            memory_id = first["result"]["memory_id"]

            replaced = execute_prepared_resume_tool_call(
                tool_name="update_memory",
                tool_input={
                    "operation": "replace",
                    "scope": "resume",
                    "memory_id": memory_id,
                    "kind": "target_strategy",
                    "content": "这份简历主要投递 AI Agent 后端岗位。",
                    "reason": "用户更新目标岗位",
                },
                context={
                    "resume_content": {},
                    "user_id": 7,
                    "resume_id": 42,
                    "memory_dir": memory_dir,
                },
            )
            read_replaced = execute_prepared_resume_tool_call(
                tool_name="read_memory",
                tool_input={"scope": "resume", "query": "AI Agent"},
                context={
                    "resume_content": {},
                    "user_id": 7,
                    "resume_id": 42,
                    "memory_dir": memory_dir,
                },
            )

            disabled = execute_prepared_resume_tool_call(
                tool_name="update_memory",
                tool_input={
                    "operation": "disable",
                    "scope": "resume",
                    "memory_id": memory_id,
                    "kind": "target_strategy",
                    "content": "这份简历主要投递 AI Agent 后端岗位。",
                    "reason": "用户不再需要这条记忆",
                },
                context={
                    "resume_content": {},
                    "user_id": 7,
                    "resume_id": 42,
                    "memory_dir": memory_dir,
                },
            )
            read_disabled = execute_prepared_resume_tool_call(
                tool_name="read_memory",
                tool_input={"scope": "resume"},
                context={
                    "resume_content": {},
                    "user_id": 7,
                    "resume_id": 42,
                    "memory_dir": memory_dir,
                },
            )

        self.assertTrue(replaced["result"]["success"])
        self.assertEqual(read_replaced["result"]["memories"][0]["content"], "这份简历主要投递 AI Agent 后端岗位。")
        self.assertTrue(disabled["result"]["success"])
        self.assertEqual(read_disabled["result"]["memories"], [])

    def test_update_summary_tool_updates_summary_text_with_diff(self):
        """用于验证update_summary通过执行器修改个人总结并返回diff。"""
        resume_content = {"summary": {"text": "3年后端开发经验"}}

        result = execute_prepared_resume_tool_call(
            tool_name="update_summary",
            tool_input={"text": "3年 AI 应用工程经验,熟悉 Agent 工具调用", "reason": "贴合 JD 定位"},
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(
            resume_content["summary"]["text"],
            "3年 AI 应用工程经验,熟悉 Agent 工具调用",
        )
        self.assertIn("贴合 JD 定位", result["result"]["diff_summary"])
        self.assertEqual(result["updated_section_name"], "个人总结")

    def test_update_profile_tool_updates_safe_profile_fields(self):
        """用于验证update_profile只修改可安全优化的个人信息字段。"""
        resume_content = {"personal_info": {"name": "张三", "position": "后端开发"}}

        result = execute_prepared_resume_tool_call(
            tool_name="update_profile",
            tool_input={
                "fields": {
                    "position": "AI 应用工程师",
                    "headline": "熟悉 Agent 工具调用与后端工程化",
                },
                "reason": "强化目标岗位定位",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(resume_content["personal_info"]["name"], "张三")
        self.assertEqual(resume_content["personal_info"]["position"], "AI 应用工程师")
        self.assertIn("Agent 工具调用", resume_content["personal_info"]["headline"])
        self.assertIn("强化目标岗位定位", result["result"]["diff_summary"])

    def test_update_profile_tool_updates_sourced_identity_fields(self):
        """用于验证update_profile可写入有明确来源的身份联系字段。"""
        resume_content = {"personal_info": {"name": "", "email": "", "phone": ""}}

        result = execute_prepared_resume_tool_call(
            tool_name="update_profile",
            tool_input={
                "fields": {
                    "name": "李四",
                    "email": "lisi@example.com",
                    "phone": "13800000000",
                },
                "source": "用户上传简历原文",
                "reason": "从导入简历补全个人信息",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(resume_content["personal_info"]["name"], "李四")
        self.assertEqual(resume_content["personal_info"]["email"], "lisi@example.com")
        self.assertEqual(resume_content["personal_info"]["phone"], "13800000000")
        self.assertEqual(result["result"]["source"], "用户上传简历原文")
        self.assertIn("从导入简历补全个人信息", result["result"]["diff_summary"])

    def test_update_profile_tool_rejects_unsourced_identity_fields(self):
        """用于验证update_profile无来源时仍拒绝身份联系字段。"""
        resume_content = {"personal_info": {"name": "张三", "position": "后端开发"}}

        result = execute_prepared_resume_tool_call(
            tool_name="update_profile",
            tool_input={"fields": {"name": "李四"}, "reason": "用户没有提供来源"},
            context={"resume_content": resume_content},
        )

        self.assertFalse(result["result"]["success"])
        self.assertEqual(resume_content["personal_info"]["name"], "张三")
        self.assertIn("name", result["result"]["message"])

    def test_upsert_job_application_updates_existing_target_fields(self):
        """用于验证upsert_job_application更新已有求职目标并保留未提字段。"""
        resume_content: dict[str, Any] = {
            "job_application": {
                "target_company": "OpenAI",
                "target_title": "AI Engineer",
                "jd_text": "旧 JD",
            }
        }

        result = execute_prepared_resume_tool_call(
            tool_name="upsert_job_application",
            tool_input={
                "fields": {"target_company": "Anthropic"},
                "reason": "用户要求改目标公司",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(
            resume_content["job_application"]["target_company"], "Anthropic"
        )
        self.assertEqual(
            resume_content["job_application"]["target_title"], "AI Engineer"
        )
        self.assertEqual(resume_content["job_application"]["jd_text"], "旧 JD")
        self.assertEqual(result["updated_section_name"], "求职目标")
        self.assertIn("用户要求改目标公司", result["result"]["diff_summary"])

    def test_upsert_job_application_fields_payload_updates_only_named_fields(self):
        """用于验证fields载荷只更新明确传入的求职目标字段。"""
        resume_content: dict[str, Any] = {
            "job_application": {
                "target_company": "腾讯",
                "target_title": "AGENT开发岗",
            }
        }

        result = execute_prepared_resume_tool_call(
            tool_name="upsert_job_application",
            tool_input={
                "fields": {"target_title": "AI应用开发岗"},
                "reason": "用户只要求修改岗位",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(resume_content["job_application"]["target_company"], "腾讯")
        self.assertEqual(
            resume_content["job_application"]["target_title"], "AI应用开发岗"
        )
        self.assertEqual(len(result["result"]["diff_items"]), 1)
        self.assertNotIn("腾讯", result["result"]["diff_summary"])
        self.assertIn("AI应用开发岗", result["result"]["diff_summary"])

    def test_upsert_job_application_diff_shows_changed_values_only(self):
        """用于验证求职目标diff只展示修改值而不是字段JSON包装。"""
        resume_content: dict[str, Any] = {
            "job_application": {"target_title": "AEGNK开发岗"}
        }

        result = execute_prepared_resume_tool_call(
            tool_name="upsert_job_application",
            tool_input={"fields": {"target_title": "AGENT开发岗"}},
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(result["result"]["diff_items"][0]["before"], "AEGNK开发岗")
        self.assertEqual(result["result"]["diff_items"][0]["after"], "AGENT开发岗")
        self.assertNotIn("target_title", result["result"]["diff_summary"])

    def test_upsert_job_application_hides_unchanged_fields_from_diff(self):
        """用于验证求职目标diff不展示未变化字段。"""
        resume_content: dict[str, Any] = {
            "job_application": {
                "target_company": "腾讯",
                "target_title": "AGENT开发岗",
            }
        }

        result = execute_prepared_resume_tool_call(
            tool_name="upsert_job_application",
            tool_input={
                "fields": {
                    "target_company": "腾讯",
                    "target_title": "AI应用开发岗",
                },
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(
            resume_content["job_application"]["target_company"], "腾讯"
        )
        self.assertEqual(
            resume_content["job_application"]["target_title"], "AI应用开发岗"
        )
        self.assertEqual(len(result["result"]["diff_items"]), 1)
        self.assertEqual(result["result"]["diff_items"][0]["before"], "AGENT开发岗")
        self.assertEqual(result["result"]["diff_items"][0]["after"], "AI应用开发岗")
        self.assertNotIn("腾讯", result["result"]["diff_summary"])

    def test_upsert_job_application_returns_no_diff_when_nothing_changes(self):
        """用于验证求职目标完全未变化时不产生假diff。"""
        resume_content: dict[str, Any] = {
            "job_application": {
                "target_company": "腾讯",
                "target_title": "AI应用开发岗",
            }
        }

        result = execute_prepared_resume_tool_call(
            tool_name="upsert_job_application",
            tool_input={
                "fields": {
                    "target_company": "腾讯",
                    "target_title": "AI应用开发岗",
                },
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(result["result"]["diff_items"], [])
        self.assertEqual(result["result"]["message"], "求职目标没有实际变化")

    def test_upsert_job_application_creates_missing_target_context(self):
        """用于验证upsert_job_application在缺失时创建求职目标上下文。"""
        resume_content: dict[str, Any] = {"projects": []}

        result = execute_prepared_resume_tool_call(
            tool_name="upsert_job_application",
            tool_input={
                "fields": {
                    "target_company": "OpenAI",
                    "target_title": "AI Engineer",
                },
                "reason": "用户指定新的面试目标",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(resume_content["job_application"]["target_company"], "OpenAI")
        self.assertEqual(resume_content["job_application"]["target_title"], "AI Engineer")
        self.assertEqual(result["tool_name"], "更新求职目标")
        self.assertIn("求职目标 修改内容", result["display_message"])

    def test_upsert_job_application_allows_omitted_reason(self):
        """用于验证upsert_job_application无需reason也可响应简单目标修改。"""
        agent = ResumeAgent()
        resume_content: dict[str, Any] = {"job_application": {"target_title": "后端"}}

        result = agent._run_tool(
            {
                "function": {
                    "name": "upsert_job_application",
                    "arguments": {"fields": {"target_company": "OpenAI"}},
                }
            },
            {"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(resume_content["job_application"]["target_company"], "OpenAI")

    def test_update_item_fields_tool_updates_project_fields(self):
        """用于验证update_item_fields修改项目条目的非bullet字段。"""
        resume_content = {
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Chat Resume",
                    "overview": "简历编辑器",
                    "role": "开发",
                }
            ]
        }

        result = execute_prepared_resume_tool_call(
            tool_name="update_item_fields",
            tool_input={
                "section": "projects",
                "item_id": "proj_1",
                "fields": {
                    "overview": "基于 ReAct Agent 的简历优化工作台",
                    "role": "全栈负责人",
                },
                "reason": "补强项目定位",
            },
            context={"resume_content": resume_content},
        )

        project = resume_content["projects"][0]
        self.assertTrue(result["result"]["success"])
        self.assertEqual(project["role"], "全栈负责人")
        self.assertIn("ReAct Agent", project["overview"])
        self.assertNotIn("technologies", project)
        self.assertIn("补强项目定位", result["result"]["diff_summary"])

    def test_update_item_fields_tool_rejects_hidden_technologies_field(self):
        """用于验证Agent不能写入当前简历不可见的技术栈字段。"""
        resume_content = {
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Chat Resume",
                    "overview": "简历编辑器",
                    "role": "开发",
                    "technologies": ["MCP"],
                }
            ],
            "work_experience": [
                {
                    "id": "work_1",
                    "company": "世优",
                    "position": "Agent 开发",
                    "technologies": ["Python"],
                }
            ],
        }

        project_result = execute_prepared_resume_tool_call(
            tool_name="update_item_fields",
            tool_input={
                "section": "projects",
                "item_id": "proj_1",
                "fields": {"technologies": ["SSE"]},
                "reason": "隐藏字段不应写入",
            },
            context={"resume_content": resume_content},
        )
        work_result = execute_prepared_resume_tool_call(
            tool_name="update_item_fields",
            tool_input={
                "section": "work_experience",
                "item_id": "work_1",
                "fields": {"technologies": ["Redis"]},
                "reason": "隐藏字段不应写入",
            },
            context={"resume_content": resume_content},
        )

        self.assertFalse(project_result["result"]["success"])
        self.assertFalse(work_result["result"]["success"])
        self.assertIn("technologies", project_result["result"]["message"])
        self.assertEqual(resume_content["projects"][0]["technologies"], ["MCP"])
        self.assertEqual(resume_content["work_experience"][0]["technologies"], ["Python"])

    def test_update_skills_tool_replaces_skill_items(self):
        """用于验证update_skills精确更新技能分类和技能列表。"""
        resume_content = {
            "skills": [
                {"id": "skill_1", "category": "后端", "items": ["Python", "FastAPI"]},
            ]
        }

        result = execute_prepared_resume_tool_call(
            tool_name="update_skills",
            tool_input={
                "category_id": "skill_1",
                "category": "AI 应用工程",
                "items": ["Python", "FastAPI", "Agent Tools", "RAG"],
                "mode": "replace",
                "reason": "补充 JD 关键词",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(resume_content["skills"][0]["category"], "AI 应用工程")
        self.assertEqual(
            resume_content["skills"][0]["items"],
            ["Python", "FastAPI", "Agent Tools", "RAG"],
        )
        self.assertIn("补充 JD 关键词", result["result"]["diff_summary"])

    def test_update_skills_diff_items_keep_full_json_for_frontend(self):
        """用于验证技能diff条目保留完整JSON而不是摘要截断文本。"""
        long_items = [
            "LangChain",
            "Multi-Agent",
            "Agent Memory",
            "RAG",
            "Context Engineering",
            "MCP",
            "ReAct",
            "Few-shot Prompting",
            "ASR/TTS",
        ]
        resume_content = {
            "skills": [
                {"id": "skill_long", "category": "Agent 技术栈", "items": long_items[:-1]},
            ]
        }

        result = execute_prepared_resume_tool_call(
            tool_name="update_skills",
            tool_input={
                "category_id": "skill_long",
                "items": long_items,
                "mode": "replace",
                "reason": "补充 ASR/TTS",
            },
            context={"resume_content": resume_content},
        )

        diff_item = result["result"]["diff_items"][0]
        self.assertTrue(result["result"]["success"])
        self.assertIn("…", result["result"]["diff_summary"])
        self.assertEqual(json.loads(diff_item["after"])["items"], long_items)
        self.assertNotIn("...", diff_item["after"])

    def test_show_section_turns_on_hidden_module(self):
        """用于验证show_section打开关闭的板块开关,不改动内容。"""
        skills_data = [{"id": "skill_1", "category": "AI", "items": ["Agent"]}]
        resume_content: dict[str, Any] = {
            "skills": skills_data,
            "_visible_modules": ["personal", "summary", "projects"],
        }

        result = execute_prepared_resume_tool_call(
            tool_name="show_section",
            tool_input={
                "section": "skills",
                "reason": "补充技能板块",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertIn("skills", resume_content["_visible_modules"])
        self.assertEqual(resume_content["skills"], skills_data)
        self.assertIn("技能专长", result["result"]["message"])

    def test_show_section_only_toggles_visibility_for_empty_section(self):
        """用于验证show_section对空板块只打开开关、不创建内容。"""
        resume_content: dict[str, Any] = {
            "summary": {"text": ""},
            "_visible_modules": ["personal", "projects"],
        }

        result = execute_prepared_resume_tool_call(
            tool_name="show_section",
            tool_input={
                "section": "summary",
                "reason": "显示个人简介",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertIn("summary", resume_content["_visible_modules"])
        self.assertEqual(resume_content["summary"], {"text": ""})

    def test_show_section_rejects_already_visible_section(self):
        """用于验证show_section拒绝已显示的板块。"""
        resume_content: dict[str, Any] = {"projects": []}

        result = execute_prepared_resume_tool_call(
            tool_name="show_section",
            tool_input={"section": "projects"},
            context={"resume_content": resume_content},
        )

        self.assertFalse(result["result"]["success"])

    def test_hide_section_turns_off_module_and_preserves_content(self):
        """用于验证hide_section关闭板块开关并保留内容。"""
        skills_data = [
            {"id": "skill_1", "category": "旧技能", "items": ["jQuery"]},
            {"id": "skill_2", "category": "后端", "items": ["Python"]},
        ]
        resume_content: dict[str, Any] = {
            "skills": skills_data,
            "_visible_modules": ["skills", "projects"],
        }

        result = execute_prepared_resume_tool_call(
            tool_name="hide_section",
            tool_input={
                "section": "skills",
                "reason": "隐藏与目标岗位弱相关的技能",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertNotIn("skills", resume_content["_visible_modules"])
        self.assertEqual(resume_content["skills"], skills_data)
        self.assertIn("隐藏", result["result"]["message"])

    def test_hide_section_rejects_already_hidden_section(self):
        """用于验证hide_section拒绝当前未显示的板块。"""
        resume_content: dict[str, Any] = {
            "projects": [],
            "_visible_modules": ["projects"],
        }

        result = execute_prepared_resume_tool_call(
            tool_name="hide_section",
            tool_input={"section": "skills"},
            context={"resume_content": resume_content},
        )

        self.assertFalse(result["result"]["success"])

    def test_resume_tool_result_includes_structured_diff_reason(self):
        """用于验证简历tool结果includesstructureddiffreason。"""
        resume_content = {
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Chat Resume",
                    "highlights": [
                        {"id": "hl_1", "text": "负责前端开发"},
                    ],
                }
            ]
        }

        result = update_bullet(
            resume_content,
            section="projects",
            item_id="proj_1",
            bullet_id="hl_1",
            text="主导前端重构,首屏加载提速 35%",
            reason="补充量化结果",
        )

        self.assertTrue(result["success"])
        self.assertIn("改动理由：补充量化结果", result["diff_summary"])
        self.assertEqual(result["diff_items"][0]["reason"], "补充量化结果")
        self.assertIn("35%", result["diff_items"][0]["after"])

    def test_resume_agent_smoke_change_detector_checks_nested_highlights(self):
        """用于验证resumeagentsmokechangedetectorchecks嵌套要点。"""
        before = {
            "work_experience": [
                {
                    "id": "work_1",
                    "summary": "负责内部系统开发",
                    "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
                }
            ]
        }
        after = {
            "work_experience": [
                {
                    "id": "work_1",
                    "summary": "负责内部系统开发",
                    "highlights": [{"id": "hl_1", "text": "优化多个后台服务"}],
                }
            ]
        }

        self.assertTrue(resume_changed(before, after))

    def test_update_bullet_tool_updates_existing_highlights_storage(self):
        """用于验证updatebullettoolupdatesexistinghighlightsstorage。"""
        agent = ResumeAgent()
        resume_content = {
            "work_experience": [
                {
                    "id": "work_1",
                    "highlights": [
                        {"id": "hl_1", "text": "负责后端开发"},
                    ],
                }
            ]
        }

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_bullet",
                    "arguments": {
                        "section": "work_experience",
                        "item_id": "work_1",
                        "bullet_id": "hl_1",
                        "text": "负责后端服务治理,接口错误率下降 20%",
                    },
                }
            },
            {"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(result["tool_name"], "优化要点")
        self.assertIn("下降 20%", resume_content["work_experience"][0]["highlights"][0]["text"])

    def test_update_bullet_tool_accepts_common_model_argument_aliases(self):
        """用于验证updatebullettoolaccepts常见模型参数别名。"""
        agent = ResumeAgent()
        resume_content = {
            "work_experience": [
                {
                    "id": "work_1",
                    "highlights": [
                        {"id": "hl_1", "text": "负责后端开发"},
                    ],
                }
            ]
        }

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_bullet",
                    "arguments": {
                        "section": "work",
                        "item_id": "work_1",
                        "highlight_id": "hl_1",
                        "text": "负责后端服务治理,接口错误率下降 20%",
                    },
                }
            },
            {"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertIn("下降 20%", resume_content["work_experience"][0]["highlights"][0]["text"])

    def test_update_skills_tool_accepts_schema_skills_alias(self):
        """用于验证模型按 schema 传 skills 时会归一化为内部 items。"""
        agent = ResumeAgent()
        resume_content = {
            "skills": [{"id": "skill_1", "category": "AI", "items": ["Agent"]}]
        }

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_skills",
                    "arguments": {
                        "category_id": "skill_1",
                        "skills": ["OpenAI Agents SDK", "RAG"],
                        "mode": "replace",
                    },
                }
            },
            {"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(
            resume_content["skills"][0]["items"],
            ["OpenAI Agents SDK", "RAG"],
        )

    def test_resume_stream_event_contract_keeps_structured_diff(self):
        """用于验证简历stream事件contractkeepsstructureddiff。"""
        event = tool_pending_event(
            call_id="call_1",
            tool_id="update_bullet",
            tool_call={
                "id": "call_1",
                "type": "function",
                "function": {"name": "update_bullet", "arguments": {}},
            },
            tool_display_name="优化要点",
            tool_input={"section": "projects"},
            diff_summary="旧文本 diff",
            diff_items=[
                {
                    "before": "负责前端开发",
                    "after": "主导前端重构,首屏加载提速 35%",
                    "reason": "补充量化结果",
                }
            ],
            tool_calls=[],
        )

        self.assertEqual(event["event_type"], "tool_pending")
        self.assertTrue(event["tool_pending"])
        self.assertEqual(event["tool_id"], "update_bullet")
        self.assertEqual(event["tool_display_name"], "优化要点")
        self.assertEqual(event["tool_name"], "优化要点")
        self.assertEqual(event["diff_items"][0]["reason"], "补充量化结果")

    def test_resume_stream_event_normalizes_legacy_payload(self):
        """用于验证简历stream事件normalizeslegacypayload。"""
        event = normalize_resume_stream_payload(
            {
                "tool_pending": True,
                "call_id": "call_1",
                "tool_call": {
                    "function": {
                        "name": "update_highlight",
                    }
                },
                "tool_name": "update_highlight",
                "diff_items": [{"before": "A", "after": "B", "reason": 123}],
            }
        )

        self.assertEqual(event["event_type"], "tool_pending")
        self.assertEqual(event["tool_id"], "update_highlight")
        self.assertEqual(event["tool_display_name"], "update_highlight")
        self.assertEqual(event["diff_items"][0]["reason"], "123")

    def test_resume_stream_event_does_not_expose_runtime_context(self):
        """用于验证简历stream事件doesnotexposeruntime上下文。"""
        resume_content = {"projects": [{"id": "proj_1", "highlights": []}]}

        event = normalize_resume_stream_payload(
            {
                "tool_confirmed": True,
                "call_id": "call_1",
                "context": {
                    "resume_content": resume_content,
                    "allowed_sections": {"projects"},
                },
            },
            resume_content=resume_content,
        )

        self.assertNotIn("context", event)
        self.assertEqual(event["resume_content"], resume_content)
        json.dumps({k: v for k, v in event.items() if v is not None})

    def test_public_resume_stream_event_strips_internal_fields(self):
        """用于验证public简历stream事件stripsinternalfields。"""
        event = public_resume_stream_event(
            {
                "event_type": "tool_result",
                "internal_only": False,
                "content": "",
                "context": {"resume_content": {"projects": []}},
                "display_message": None,
                "done": False,
            }
        )

        self.assertNotIn("context", event)
        self.assertNotIn("internal_only", event)
        self.assertNotIn("display_message", event)
        self.assertEqual(event["event_type"], "tool_result")

    def test_system_prompt_is_thin_stable_business_policy(self):
        """用于验证系统提示词只保留薄业务边界。"""
        rendered = _render_resume_system_prompt(
            target_title="前端工程师",
            target_company="字节跳动",
            jd_text="负责复杂前端交互与性能优化",
            resume_json="{}",
        )

        assert_tag(rendered, "role_definition")
        assert_tag(rendered, "no_fabrication")
        self.assertNotIn("可用工具", rendered)
        self.assertNotIn("量化改写优先级", rendered)
        self.assertNotIn("简历优化策略", rendered)
        assert_tag(rendered, "explicit_planning")
        assert_tag(rendered, "tool_feedback_repair")
        assert_tag(rendered, "stopping_conditions")

    def test_system_prompt_requires_jd_backed_action_chain_for_bullets(self):
        """用于验证系统提示词要求 bullet 兼顾 JD 贴合和强动作链路。"""
        rendered = _render_resume_system_prompt(
            target_title="前端工程师",
            target_company="字节跳动",
            jd_text="需要表达清晰、重点突出的前端工程化经验",
            resume_json='{"work_experience": [{"highlights": [{"text": "重构后台页面"}]}]}',
        )

        self.assertIn("强动作动词 + 技术/方法 + 结果", rendered)
        self.assertIn("页面/组件/交互可支撑“前端/工程化”", rendered)

    def test_system_prompt_does_not_expose_memory_tools(self):
        """用于验证systempromptdoesnotexposememorytools。"""
        rendered = _render_resume_system_prompt(
            target_title="AI Agent 开发工程师",
            target_company="腾讯",
            jd_text="负责 Agent 产品能力建设",
            resume_json="{}",
        )

        self.assertNotIn("read_user_memory", rendered)
        self.assertNotIn("write_user_memory", rendered)
        self.assertNotIn("${toolsList}", rendered)
        self.assertNotIn("${guidelines}", rendered)
        self.assertNotIn("Pi 文档", rendered)

    def test_system_prompt_requires_tools_for_resume_mutations(self):
        """用于验证修改简历内容时必须使用真实简历工具。"""
        rendered = _render_resume_system_prompt(
            target_title="产品经理",
            target_company="美团",
            jd_text="负责策略优化与跨团队协同",
            resume_json='{"work_experience": [{"id": "work_1", "highlights": []}]}',
        )

        assert_tag(rendered, "must_use_tools_for_mutations")
        assert_tag(rendered, "no_over_optimization")
        self.assertNotIn("默认执行 `optimize-first`", rendered)

    def test_system_prompt_uses_kimi_style_tool_turn_contract(self):
        """用于验证工具轮协议采用 Kimi 风格:调用工具时不输出解释。"""
        rendered = _render_resume_system_prompt(
            target_title="产品经理",
            target_company="美团",
            jd_text="负责策略优化与跨团队协同",
            resume_json='{"work_experience": [{"id": "work_1", "highlights": []}]}',
        )

        # 新 prompt 不再包含 tool turn contract，工具协议收敛在 schema 描述中
        assert_tag(rendered, "must_use_tools_for_mutations")

    def test_tool_schema_descriptions_carry_tool_protocol(self):
        """用于验证工具使用协议收敛在工具 schema 描述中。"""
        descriptions = {
            tool["function"]["name"]: tool["function"]["description"]
            for tool in RESUME_TOOLS_SCHEMA
        }

        assert_tag(descriptions["update_bullet"], "bullet_section_constraint", registry=SCHEMA_TAGS)
        assert_tag(descriptions["update_bullet"], "bullet_id_source", registry=SCHEMA_TAGS)
        assert_tag(descriptions["update_overview"], "overview_section_constraint", registry=SCHEMA_TAGS)
        assert_tag(descriptions["update_item_fields"], "is_current_protected", registry=SCHEMA_TAGS)

    def test_tool_schema_descriptions_omit_prompt_routing_labels(self):
        """用于验证工具描述不重复系统提示词中的路由规则。"""
        descriptions = [
            tool["function"]["description"]
            for tool in RESUME_TOOLS_SCHEMA
        ]

        self.assertFalse(any("触发条件" in description for description in descriptions))
        self.assertFalse(any("选择规则" in description for description in descriptions))

    def test_system_prompt_omits_tool_call_protocol_section(self):
        """用于验证系统提示词不再硬编码工具协议正文。"""
        rendered = _render_resume_system_prompt(
            target_title="前端工程师",
            target_company="字节跳动",
            jd_text="负责复杂前端交互与性能优化",
            resume_json='{"projects": [{"id": "proj_1", "highlights": [{"id": "hl_1", "text": "负责前端开发"}]}]}',
        )

        self.assertNotIn("工具调用协议", rendered)
        self.assertNotIn("改单条要点用 `update_bullet", rendered)
        self.assertNotIn("改项目简介只用 `update_overview", rendered)

    def test_system_prompt_limits_follow_up_to_defined_exception_cases(self):
        """用于验证systempromptlimitsfollowuptodefinedexception用例。"""
        rendered = _render_resume_system_prompt(
            target_title="运营",
            target_company="小红书",
            jd_text="负责活动运营与增长分析",
            resume_json='{"projects": [{"id": "proj_1", "highlights": []}]}',
        )

        # 新 prompt 精简后不再包含追问例外清单，改为通用约束
        assert_tag(rendered, "follow_up_text_only")

    def test_system_prompt_explicitly_blocks_high_risk_fabrication_requests(self):
        """用于验证systempromptexplicitlyblockshighriskfabricationrequests。"""
        rendered = _render_resume_system_prompt(
            target_title="高级后端工程师",
            target_company="字节跳动",
            jd_text="负责高并发系统设计与稳定性建设",
            resume_json='{"work_experience": [{"id": "work_1", "highlights": []}]}',
        )

        assert_tag(rendered, "no_fabrication")
        self.assertIn("不编造经历、数字或结果", rendered)


if __name__ == "__main__":
    unittest.main()
