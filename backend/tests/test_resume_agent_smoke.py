"""用于覆盖 test_resume_agent_smoke.py 对应的回归测试。"""

import asyncio
import sys
import unittest
from typing import Any
from pathlib import Path
from pi_agent_core import (
    AssistantMessage,
    StreamDoneEvent,
    StreamStartEvent,
    StreamTextDeltaEvent,
    StreamTextEndEvent,
    StreamTextStartEvent,
    StreamToolCallEndEvent,
    StreamToolCallStartEvent,
    TextContent,
    ToolCall,
    ToolResultMessage,
)
from pi_agent_core.types import AgentContext, Model, SimpleStreamOptions, StreamResult

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.agents.resume.runtime import ResumeAgentRuntime  # noqa: E402
from app.infra.config import settings  # noqa: E402
from app.services.llm.chat_service import ChatService  # noqa: E402


class FakeModelResponse:
    """用于描述测试模型返回的文本或工具调用。"""

    def __init__(
        self,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ):
        """用于处理init。"""
        self.content = content
        self.tool_calls = tool_calls or []


class FakePiAgentStream:
    """用于给 pi-agent-core runtime 提供确定性的模型事件。"""

    def __init__(self, messages: list[AssistantMessage]):
        """用于处理init。"""
        self.messages = list(messages)
        self.contexts: list[AgentContext] = []
        self.options: list[SimpleStreamOptions] = []
        self.calls = 0

    async def __call__(
        self,
        model: Model,
        context: AgentContext,
        options: SimpleStreamOptions,
    ) -> StreamResult:
        """返回 pi-agent-core 期望的 stream result。"""
        del model
        self.contexts.append(context)
        self.options.append(options)
        message = self.messages[self.calls]
        self.calls += 1
        events = self._events_for(message)

        async def events_iter():
            """按顺序返回预设模型事件。"""
            for event in events:
                yield event

        async def result():
            """返回当前预设 assistant message。"""
            return message

        return {"events": events_iter(), "result": result}

    @staticmethod
    def _events_for(message: AssistantMessage) -> list[Any]:
        """把一个完整 assistant message 转成流式事件。"""
        events: list[Any] = [StreamStartEvent(partial=message)]
        for index, block in enumerate(message.content):
            if isinstance(block, TextContent):
                events.extend(
                    [
                        StreamTextStartEvent(content_index=index, partial=message),
                        StreamTextDeltaEvent(
                            content_index=index,
                            delta=block.text,
                            partial=message,
                        ),
                        StreamTextEndEvent(
                            content_index=index,
                            content=block.text,
                            partial=message,
                        ),
                    ]
                )
            if isinstance(block, ToolCall):
                events.extend(
                    [
                        StreamToolCallStartEvent(
                            content_index=index,
                            partial=message,
                        ),
                        StreamToolCallEndEvent(
                            content_index=index,
                            tool_call=block,
                            partial=message,
                        ),
                    ]
                )
        events.append(StreamDoneEvent(reason=message.stop_reason, message=message))
        return events


class FakeEarlyToolStartStream(FakePiAgentStream):
    """用于模拟 first_tool_delta 时先出现的 toolcall_start 事件。"""

    def __init__(self, messages: list[AssistantMessage], early_tool_call: ToolCall):
        """保存消息和提前展示用的轻量工具调用。"""
        super().__init__(messages)
        self.early_tool_call = early_tool_call

    async def __call__(
        self,
        model: Model,
        context: AgentContext,
        options: SimpleStreamOptions,
    ) -> StreamResult:
        """第一轮在完整工具调用事件前插入一个轻量 toolcall_start。"""
        del model
        self.contexts.append(context)
        self.options.append(options)
        message = self.messages[self.calls]
        call_index = self.calls
        self.calls += 1
        events = self._events_for(message)
        if call_index == 0:
            preview = AssistantMessage(
                api=message.api,
                provider=message.provider,
                model=message.model,
                content=[self.early_tool_call],
            )
            events.insert(
                1,
                StreamToolCallStartEvent(content_index=0, partial=preview),
            )

        async def events_iter():
            """按顺序返回预设模型事件。"""
            for event in events:
                yield event

        async def result():
            """返回当前预设 assistant message。"""
            return message

        return {"events": events_iter(), "result": result}


class HangingPiAgentStream:
    """用于模拟永不自然结束的模型流，便于验证取消信号。"""

    def __init__(self):
        """保存 stream options 供断言。"""
        self.options: list[SimpleStreamOptions] = []
        self.started = asyncio.Event()
        self.released = asyncio.Event()

    async def __call__(
        self,
        model: Model,
        context: AgentContext,
        options: SimpleStreamOptions,
    ) -> StreamResult:
        """返回一个会一直等待的流式结果。"""
        del model, context
        self.options.append(options)
        self.started.set()

        async def events_iter():
            """保持流运行直到测试取消。"""
            await self.released.wait()
            for event in ():
                yield event

        async def result():
            """返回空文本结果。"""
            await self.released.wait()
            return fake_pi_text("")

        return {"events": events_iter(), "result": result}


def fake_pi_text(text: str) -> AssistantMessage:
    """构造 pi-agent-core 文本 assistant message。"""
    return AssistantMessage(content=[TextContent(text=text)], stop_reason="stop")


def fake_pi_tool_call(
    *,
    name: str,
    args: dict,
    call_id: str,
) -> AssistantMessage:
    """构造 pi-agent-core 工具调用 assistant message。"""
    return AssistantMessage(
        content=[ToolCall(id=call_id, name=name, arguments=args)],
        stop_reason="toolUse",
    )


def fake_pi_message(response: FakeModelResponse) -> AssistantMessage:
    """把测试响应转换为 pi-agent-core assistant message。"""
    if response.tool_calls:
        content: list[Any] = []
        if response.content:
            content.append(TextContent(text=response.content))
        for index, call in enumerate(response.tool_calls):
            raw_args = call.get("args")
            args = raw_args if isinstance(raw_args, dict) else {}
            content.append(
                ToolCall(
                    id=str(call.get("id") or f"call_{index}"),
                    name=str(call.get("name") or ""),
                    arguments=args,
                )
            )
        return AssistantMessage(
            content=content,
            stop_reason="toolUse",
        )
    return fake_pi_text(response.content)


def fake_tool_call(
    *,
    name: str,
    args: dict,
    call_id: str,
) -> dict:
    """用于构造toolcall。"""
    return {"name": name, "args": args, "id": call_id}


class ResumeAgentSmokeTests(unittest.IsolatedAsyncioTestCase):
    def _build_agent(self, responses):
        """用于构建Agent。"""
        agent = ResumeAgent()
        agent.runtime = ResumeAgentRuntime(
            stream_fn=FakePiAgentStream(
                [fake_pi_message(response) for response in responses]
            )
        )
        return agent

    def _sample_resume(self):
        """用于处理示例简历。"""
        return {
            "personal_info": {"name": "张三", "position": "后端开发"},
            "summary": {"text": "3年 Python 后端开发经验"},
            "work_experience": [
                {
                    "id": "work_1",
                    "company": "某科技公司",
                    "position": "Python 开发工程师",
                    "summary": "负责内部系统开发",
                    "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
                }
            ],
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Chat Resume",
                    "role": "开发者",
                    "duration": "2025",
                    "overview": "AI 求职辅导平台",
                    "highlights": [{"id": "proj_hl_1", "text": "支持流式简历优化"}],
                }
            ],
            "skills": [],
            "education": [],
            "languages": [],
        }

    def test_strip_redundant_fields_removes_empty_summary(self):
        """用于验证stripredundantfieldsremovesemptysummary。"""
        cleaned = ResumeAgent._strip_redundant_fields(
            {
                "personal_info": {"name": "张三"},
                "summary": {"text": "   "},
                "projects": [],
                "work_experience": [],
            }
        )

        self.assertNotIn("summary", cleaned)

    def test_strip_redundant_fields_keeps_summary_when_non_empty(self):
        """用于验证 Agent 简历上下文保留非空个人简介。"""
        cleaned = ResumeAgent._strip_redundant_fields(
            {
                "personal_info": {"name": "张三"},
                "summary": {"text": "有 3 年后端开发经验"},
                "projects": [],
                "work_experience": [],
            }
        )

        self.assertEqual(cleaned["summary"]["text"], "有 3 年后端开发经验")

    def test_run_tool_rejects_hidden_section(self):
        """用于验证runtoolrejectshiddensection。"""
        agent = ResumeAgent()
        result = agent._run_tool(
            {
                "function": {
                    "name": "add_bullet",
                    "arguments": {
                        "section": "skills",
                        "item_id": "skill_1",
                        "text": "不应被允许",
                    },
                }
            },
            {
                "resume_content": self._sample_resume(),
                "allowed_sections": {"personal_info", "work_experience"},
            },
        )

        self.assertIn("禁止修改", result["display_message"])
        self.assertEqual(result["updated_section_name"], "技能专长")

    def test_update_overview_tool_updates_project_overview(self):
        """用于验证updateoverviewtoolupdatesprojectoverview。"""
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_overview",
                    "arguments": {
                        "section": "projects",
                        "item_id": "proj_1",
                        "overview": "支持结构化简历编辑、Agent 改写和模拟面试。",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(
            resume["projects"][0]["overview"],
            "支持结构化简历编辑、Agent 改写和模拟面试。",
        )

    def test_update_overview_defaults_missing_section_to_projects(self):
        """用于验证updateoverviewdefaultsmissingsectiontoprojects。"""
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_overview",
                    "arguments": {
                        "item_id": "proj_1",
                        "overview": "默认补全 projects 后完成更新。",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(
            resume["projects"][0]["overview"],
            "默认补全 projects 后完成更新。",
        )

    def test_update_overview_missing_item_id_returns_recoverable_error(self):
        """用于验证updateoverviewmissingitemidreturnsrecoverable错误。"""
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_overview",
                    "arguments": {
                        "section": "projects",
                        "overview": "缺少 item_id 时不应抛出 TypeError。",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertFalse(result["result"]["success"])
        self.assertEqual(
            result["result"]["error"]["type"],
            "missing_required_argument",
        )
        self.assertTrue(result["result"]["error"]["recoverable"])
        self.assertIn("item_id", result["display_message"])

    def test_invalid_tool_arguments_json_returns_recoverable_error(self):
        """用于验证invalidtoolargumentsjsonreturnsrecoverable错误。"""
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_bullet",
                    "arguments": '{"section":"projects",',
                }
            },
            {"resume_content": resume},
        )

        self.assertFalse(result["result"]["success"])
        self.assertEqual(
            result["result"]["error"]["type"],
            "invalid_arguments_json",
        )
        self.assertTrue(result["result"]["error"]["recoverable"])

    def test_update_bullet_tool_updates_single_highlight(self):
        """用于验证updatebullettoolupdatessinglehighlight。"""
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_bullet",
                    "arguments": {
                        "section": "work_experience",
                        "item_id": "work_1",
                        "bullet_id": "hl_1",
                        "text": "维护多个后台服务并推动关键接口性能优化",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(
            resume["work_experience"][0]["highlights"][0]["text"],
            "维护多个后台服务并推动关键接口性能优化",
        )

    def test_add_bullet_tool_appends_highlight(self):
        """用于验证addbullettoolappendshighlight。"""
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "add_bullet",
                    "arguments": {
                        "section": "projects",
                        "item_id": "proj_1",
                        "text": "支持工具调用后的人机确认流程",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(len(resume["projects"][0]["highlights"]), 2)
        self.assertEqual(
            resume["projects"][0]["highlights"][-1]["text"],
            "支持工具调用后的人机确认流程",
        )

    def test_remove_bullet_tool_deletes_highlight(self):
        """用于验证removebullettooldeleteshighlight。"""
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "remove_bullet",
                    "arguments": {
                        "section": "projects",
                        "item_id": "proj_1",
                        "bullet_id": "proj_hl_1",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(resume["projects"][0]["highlights"], [])

    async def test_optimize_returns_plain_text_without_mutation(self):
        """用于验证optimizereturnsplaintextwithoutmutation。"""
        agent = self._build_agent(
            [FakeModelResponse(content="我建议优先强化项目结果和量化指标。")]
        )
        resume = self._sample_resume()

        result = await agent.optimize("帮我看看这份简历怎么优化", resume)

        self.assertEqual(result["content"], "我建议优先强化项目结果和量化指标。")
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(resume["summary"]["text"], "3年 Python 后端开发经验")

    async def test_optimize_retries_no_tool_mutation_claim(self):
        """用于验证无工具完成声明会被拦截并重试真实工具调用。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content=(
                        "继续添加 Prompt Chain 要点：已完成工作经历拆分，"
                        "新增 4 条独立 bullet。"
                    )
                ),
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="add_bullet",
                            call_id="call_guard_retry",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "text": "优化 Prompt Chain 生成链路，支撑 Agent 输出一致性",
                                "reason": "纠正无工具声明",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="已通过工具新增 1 条工作经历要点。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("继续拆分工作经历 bullet，事实是 Prompt Chain 生成链路支撑 Agent 输出一致性", resume)

        self.assertNotIn("新增 4 条独立 bullet", result["content"])
        self.assertIn("已通过工具新增 1 条工作经历要点。", result["content"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(agent.runtime.stream_fn.calls, 3)
        self.assertEqual(len(resume["work_experience"][0]["highlights"]), 2)
        self.assertEqual(
            resume["work_experience"][0]["highlights"][-1]["text"],
            "优化 Prompt Chain 生成链路，支撑 Agent 输出一致性",
        )


    async def test_optimize_retries_no_tool_bullet_optimization_narrative(self):
        """用于验证逐条优化叙述没有工具调用时会被拦截。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content=(
                        "好的，让我仔细审视工作经历的 4 条 bullet，逐条优化。"
                        "开始逐条优化：Bullet 1 — 精简，突出架构设计与业务闭环："
                        "完成。工作经历 bullet 优化总结：#1 精简表述，#2 保留技术亮点。"
                    )
                ),
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_bullet",
                            call_id="call_narrative_retry",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "bullet_id": "hl_1",
                                "text": "设计并落地 Multi-Agent 销售系统，覆盖线索获取、客户分析与 CRM 跟进闭环",
                                "reason": "纠正无工具完成叙述",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="已通过工具优化 1 条工作经历要点。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("2", resume)

        self.assertNotIn("工作经历 bullet 优化总结", result["content"])
        self.assertIn("已通过工具优化 1 条工作经历要点。", result["content"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(agent.runtime.stream_fn.calls, 3)
        self.assertIn("Multi-Agent 销售系统", resume["work_experience"][0]["highlights"][0]["text"])

    async def test_optimize_updates_resume_via_tool_call(self):
        """用于验证optimizeupdates简历viatoolcall。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_bullet",
                            call_id="call_1",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "bullet_id": "hl_1",
                                "text": "优化核心接口链路，推动响应时间下降 30%",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="我已经把工作经历改成结果导向表达，并补了量化成果。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("优化我的工作经历，核心接口响应时间下降 30% 是真实成果", resume)

        self.assertIn("量化成果", result["content"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertIn(
            "响应时间下降 30%",
            resume["work_experience"][0]["highlights"][0]["text"],
        )

    async def test_optimize_hides_tool_call_turn_preamble_text(self):
        """用于验证工具调用轮次的模型前置文本不会进入最终回复。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="我来继续添加一个技术要点：",
                    tool_calls=[
                        fake_tool_call(
                            name="add_bullet",
                            call_id="call_with_preamble",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "text": "构建结构化工具调用链路，支撑简历内容更新",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="已通过工具新增 1 条项目要点。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("继续优化项目，事实是结构化工具调用链路支撑简历内容更新", resume)

        self.assertNotIn("我来继续添加一个技术要点", result["content"])
        self.assertIn("已通过工具新增 1 条项目要点。", result["content"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(
            resume["projects"][0]["highlights"][-1]["text"],
            "构建结构化工具调用链路，支撑简历内容更新",
        )

    async def test_optimize_falls_back_after_repeated_no_tool_mutation_claim(self):
        """用于验证重复无工具完成声明会被替换为安全回复。"""
        agent = self._build_agent(
            [
                FakeModelResponse(content="已完成项目拆分，新增 3 条 bullet。"),
                FakeModelResponse(content="继续添加智能解析要点：已完成新增 2 条 bullet。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("继续优化项目内容", resume)

        self.assertNotIn("新增 3 条 bullet", result["content"])
        self.assertIn("还没有通过简历工具完成修改", result["content"])
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(agent.runtime.stream_fn.calls, 2)

    async def test_optimize_surfaces_unrealized_action_headline_without_tool(self):
        """用于验证工具结果后的无工具文本会直接展示并停止。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="我来精简 Chat Resume 项目中过长的 overview 和 bullet。",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_update_overview",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "overview": "AI 求职辅导平台，支持简历诊断与流式优化。",
                            },
                        )
                    ],
                ),
                FakeModelResponse(
                    content="我来看看当前 Chat Resume 的 bullet 长度，精简过长的部分。"
                    "继续精简另一条：继续精简最后一条：本轮没有新的修改。"
                ),
                FakeModelResponse(content="已精简项目简介，保留核心能力和技术关键词。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("把太长的部分精简一下", resume)

        self.assertIn("继续精简另一条", result["content"])
        self.assertIn("继续精简最后一条", result["content"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(
            resume["projects"][0]["overview"],
            "AI 求职辅导平台，支持简历诊断与流式优化。",
        )
        self.assertEqual(agent.runtime.stream_fn.calls, 2)

    async def test_optimize_runs_multiple_tools_from_one_model_turn(self):
        """用于验证 runtime 会按顺序执行同一轮的多个工具。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_first",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "overview": "新的项目简介",
                            },
                        ),
                        fake_tool_call(
                            name="add_bullet",
                            call_id="call_second",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "text": "同一轮多发出的工具调用会按顺序执行",
                            },
                        ),
                    ],
                ),
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="add_bullet",
                            call_id="call_after_feedback",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "text": "优化工具结果回读链路，支撑亮点持续新增",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="已先完成第一步修改。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("优化项目内容，事实是工具结果回读链路支撑亮点持续新增", resume)

        self.assertEqual(result["content"], "已先完成第一步修改。")
        self.assertEqual(len(result["tool_calls"]), 3)
        self.assertEqual(resume["projects"][0]["overview"], "新的项目简介")
        self.assertEqual(len(resume["projects"][0]["highlights"]), 3)
        self.assertEqual(
            resume["projects"][0]["highlights"][-2]["text"],
            "同一轮多发出的工具调用会按顺序执行",
        )
        self.assertEqual(
            resume["projects"][0]["highlights"][-1]["text"],
            "优化工具结果回读链路，支撑亮点持续新增",
        )
        self.assertEqual(agent.runtime.stream_fn.calls, 3)
        second_turn_messages = agent.runtime.stream_fn.contexts[1].messages
        self.assertTrue(
            any(
                isinstance(message, AssistantMessage)
                and any(
                    isinstance(block, ToolCall) and block.id == "call_first"
                    for block in message.content
                )
                for message in second_turn_messages
            )
        )
        self.assertTrue(
            any(
                isinstance(message, ToolResultMessage)
                and message.tool_call_id == "call_first"
                for message in second_turn_messages
            )
        )

    async def test_optimize_default_react_loop_has_no_six_turn_cap(self):
        """用于验证默认 ReAct 循环不会在 6 轮工具调用后停止。"""
        responses = [
            FakeModelResponse(
                content="",
                tool_calls=[
                    fake_tool_call(
                        name="update_overview",
                        call_id=f"call_overview_{index}",
                        args={
                            "section": "projects",
                            "item_id": "proj_1",
                            "overview": "优化项目简介，支撑连续阶段表达",
                        },
                    )
                ],
            )
            for index in range(1, 8)
        ]
        responses.append(FakeModelResponse(content="已完成连续多轮项目简介优化。"))
        agent = self._build_agent(responses)
        resume = self._sample_resume()

        result = await agent.optimize("连续优化项目简介，连续阶段表达是真实内容", resume)

        self.assertEqual(result["content"], "已完成连续多轮项目简介优化。")
        self.assertEqual(len(result["tool_calls"]), 7)
        self.assertEqual(resume["projects"][0]["overview"], "优化项目简介，支撑连续阶段表达")
        self.assertEqual(agent.runtime.stream_fn.calls, 8)

    async def test_optimize_retries_recoverable_tool_error(self):
        """用于验证optimizeretriesrecoverabletool错误。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_bad",
                            args={"section": "projects", "overview": "缺少 item_id"},
                        )
                    ],
                ),
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_fixed",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "overview": "重试后写入的简介",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="已根据工具错误修正参数并完成修改。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("优化项目简介", resume)

        self.assertEqual(len(result["tool_calls"]), 2)
        self.assertEqual(resume["projects"][0]["overview"], "重试后写入的简介")
        self.assertIn("修正参数", result["content"])

    async def test_optimize_stream_applies_change_after_confirmation(self):
        """用于验证optimizestreamapplieschangeafterconfirmation。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_bullet",
                            call_id="call_stream_1",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "bullet_id": "hl_1",
                                "text": "优化后台服务维护流程，支撑内部系统开发交付",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="已完成优化，重点突出系统规模和性能成果。"),
            ]
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="优化这段工作经历，事实是后台服务维护流程支撑内部系统开发交付",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
        ):
            events.append(event)

        self.assertTrue(any(event.get("tool_pending") for event in events))
        self.assertTrue(any(event.get("tool_confirmed") for event in events))
        visible_tool_events = [
            event for event in events if event.get("event_type") == "tool_call"
        ]
        self.assertEqual(len(visible_tool_events), 1)
        self.assertEqual(visible_tool_events[0]["tool_id"], "update_bullet")
        self.assertEqual(visible_tool_events[0]["call_id"], "call_stream_1")
        pending_events = [event for event in events if event.get("tool_pending")]
        confirmed_events = [event for event in events if event.get("tool_confirmed")]
        self.assertEqual(pending_events[0]["call_id"], "call_stream_1")
        self.assertEqual(confirmed_events[0]["call_id"], "call_stream_1")
        self.assertLess(
            events.index(visible_tool_events[0]),
            next(index for index, event in enumerate(events) if event.get("tool_pending")),
        )
        self.assertEqual(
            resume["work_experience"][0]["highlights"][0]["text"],
            "优化后台服务维护流程，支撑内部系统开发交付",
        )
        self.assertEqual(agent.runtime.stream_fn.calls, 2)

    async def test_optimize_stream_retries_no_tool_mutation_claim(self):
        """用于验证流式无工具完成声明会被拦截并重试真实工具调用。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content=(
                        "继续添加 RAG 要点：已完成工作经历拆分，"
                        "新增 3 条独立 bullet。"
                    )
                ),
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="add_bullet",
                            call_id="call_stream_guard_retry",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "text": "构建 RAG 记忆检索链路，支撑长程上下文引用",
                                "reason": "纠正无工具声明",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="已通过工具新增 1 条 RAG 要点。"),
            ]
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="继续拆分工作经历 bullet，补充 RAG 记忆检索增强长程上下文",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
        ):
            events.append(event)


        visible_text = "".join(event.get("content", "") for event in events)
        self.assertNotIn("新增 3 条独立 bullet", visible_text)
        self.assertIn("已通过工具新增 1 条 RAG 要点。", visible_text)
        self.assertTrue(any(event.get("tool_pending") for event in events))
        self.assertTrue(any(event.get("tool_confirmed") for event in events))
        self.assertEqual(agent.runtime.stream_fn.calls, 3)
        self.assertEqual(len(resume["work_experience"][0]["highlights"]), 2)
        self.assertEqual(
            resume["work_experience"][0]["highlights"][-1]["text"],
            "构建 RAG 记忆检索链路，支撑长程上下文引用",
        )

    async def test_optimize_stream_hides_tool_call_turn_preamble_text(self):
        """用于验证流式工具调用轮次不会展示模型前置说明。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="我来继续添加项目亮点：",
                    tool_calls=[
                        fake_tool_call(
                            name="add_bullet",
                            call_id="call_stream_preamble",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "text": "构建结构化工具调用链路，支撑简历编辑可追溯",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="已通过工具新增 1 条项目亮点。"),
            ]
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="继续优化项目，事实是结构化工具调用链路支撑简历编辑可追溯",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
        ):
            events.append(event)


        visible_text = "".join(event.get("content", "") for event in events)
        self.assertNotIn("我来继续添加项目亮点", visible_text)
        self.assertIn("已通过工具新增 1 条项目亮点", visible_text)
        self.assertTrue(any(event.get("tool_pending") for event in events))
        self.assertEqual(
            resume["projects"][0]["highlights"][-1]["text"],
            "构建结构化工具调用链路，支撑简历编辑可追溯",
        )

    async def test_optimize_stream_falls_back_after_repeated_no_tool_mutation_text(self):
        """用于验证流式重复无工具完成声明会被替换为安全回复。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="已完成 Chat Resume 项目优化，新增 3 条 bullet。"
                ),
                FakeModelResponse(
                    content="本轮没有修改。上一轮我已经完成新增 3 条 bullet。"
                ),
            ]
        )
        resume = self._sample_resume()

        events = []
        async for event in agent.optimize_stream(
            user_message="Chat Resume 优化",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=None,
        ):
            events.append(event)


        visible_text = "".join(event.get("content", "") for event in events)
        self.assertNotIn("已完成 Chat Resume 项目优化", visible_text)
        self.assertIn("还没有通过简历工具完成修改", visible_text)
        self.assertFalse(any(event.get("tool_pending") for event in events))
        self.assertEqual(agent.runtime.stream_fn.calls, 2)

    async def test_optimize_stream_surfaces_unrealized_action_headline_without_tool(self):
        """用于验证流式工具结果后的无工具文本会直接展示。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="我来精简 Chat Resume 项目中过长的 overview 和 bullet。",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_stream_update_overview",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "overview": "AI 求职辅导平台，支持简历诊断与流式优化。",
                            },
                        )
                    ],
                ),
                FakeModelResponse(
                    content="我来看看当前 Chat Resume 的 bullet 长度，精简过长的部分。"
                    "继续精简另一条：继续精简最后一条：本轮没有新的修改。"
                ),
                FakeModelResponse(content="已精简项目简介，保留核心能力和技术关键词。"),
            ]
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="把太长的部分精简一下",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
        ):
            events.append(event)

        visible_text = "".join(event.get("content", "") for event in events)
        self.assertIn("继续精简另一条", visible_text)
        self.assertIn("继续精简最后一条", visible_text)
        self.assertTrue(any(event.get("tool_pending") for event in events))
        self.assertEqual(
            resume["projects"][0]["overview"],
            "AI 求职辅导平台，支持简历诊断与流式优化。",
        )
        self.assertEqual(agent.runtime.stream_fn.calls, 2)

    async def test_optimize_stream_runs_multiple_tools_from_one_model_turn(
        self,
    ):
        """用于验证流式 runtime 会顺序确认并执行同轮多个工具。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_stream_first",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "overview": "先优化项目简介",
                            },
                        ),
                        fake_tool_call(
                            name="add_bullet",
                            call_id="call_stream_second",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "text": "同一轮继续新增亮点",
                            },
                        ),
                    ],
                ),
                FakeModelResponse(content="已按顺序完成项目简介和项目亮点优化。"),
            ]
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="优化项目内容",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
        ):
            events.append(event)

        pending_events = [event for event in events if event.get("tool_pending")]
        confirmed_events = [event for event in events if event.get("tool_confirmed")]
        self.assertEqual(len(pending_events), 2)
        self.assertEqual(len(confirmed_events), 2)
        self.assertEqual(resume["projects"][0]["overview"], "先优化项目简介")
        self.assertEqual(len(resume["projects"][0]["highlights"]), 2)
        self.assertEqual(
            resume["projects"][0]["highlights"][-1]["text"],
            "同一轮继续新增亮点",
        )
        self.assertEqual(agent.runtime.stream_fn.calls, 2)

    async def test_optimize_stream_reject_keeps_resume_unchanged(self):
        """用于验证optimizestreamrejectkeeps简历unchanged。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_bullet",
                            call_id="call_stream_2",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "bullet_id": "hl_1",
                                "text": "优化后台服务维护流程，支撑内部系统开发交付",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="我保留了原内容，等待你提供更具体的目标岗位。"),
            ]
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(False)

        events = []
        async for event in agent.optimize_stream(
            user_message="把工作经历改成后台服务维护流程支撑内部系统开发交付",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
        ):
            events.append(event)

        self.assertTrue(any(event.get("tool_rejected") for event in events))
        self.assertEqual(
            resume["work_experience"][0]["highlights"][0]["text"],
            "维护多个后台服务",
        )

    async def test_optimize_stream_emits_tool_call_failed_then_recovers(self):
        """用于验证optimizestreamemitstoolcallfailedthenrecovers。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_stream_bad",
                            args={"section": "projects", "overview": "缺少 item_id"},
                        )
                    ],
                ),
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_stream_fixed",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "overview": "流式重试后的简介",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="已完成流式重试。"),
            ]
        )
        resume = self._sample_resume()

        events = []
        async for event in agent.optimize_stream(
            user_message="优化项目简介",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=None,
        ):
            events.append(event)

        self.assertTrue(any(event.get("tool_call_failed") for event in events))
        self.assertEqual(resume["projects"][0]["overview"], "流式重试后的简介")
        visible_text = "".join(event.get("content", "") for event in events)
        self.assertIn("已完成流式重试。", visible_text)
        self.assertNotIn("缺少 item_id", visible_text)

class ResumeAgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def _sample_resume(self):
        """用于处理示例简历。"""
        return {
            "work_experience": [
                {
                    "id": "work_1",
                    "company": "某科技公司",
                    "position": "Python 开发工程师",
                    "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
                }
            ]
        }

    async def test_resume_agent_uses_resume_agent_runtime_by_default(self):
        """用于验证简历AgentusespiAgentruntimebydefault。"""
        agent = ResumeAgent()

        self.assertIsInstance(agent.runtime, ResumeAgentRuntime)

    async def test_resume_agent_runtime_stream_preserves_confirmation_flow(self):
        """用于验证piAgentruntimestreampreservesconfirmationflow。"""
        agent = ResumeAgent()
        agent.runtime = ResumeAgentRuntime(
            stream_fn=FakePiAgentStream(
                [
                    fake_pi_tool_call(
                        name="update_bullet",
                        args={
                            "section": "work_experience",
                            "item_id": "work_1",
                            "bullet_id": "hl_1",
                            "text": "优化后台服务维护流程，支撑内部系统开发交付",
                            "reason": "补充交付结果",
                        },
                        call_id="call_pi_1",
                    ),
                    fake_pi_text("已完成优化。"),
                ]
            )
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="优化这段工作经历，事实是后台服务维护流程支撑内部系统开发交付",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
            allowed_sections={"work_experience"},
        ):
            events.append(event)

        self.assertTrue(any(event.get("tool_pending") for event in events))
        self.assertTrue(any(event.get("tool_confirmed") for event in events))
        self.assertEqual(
            resume["work_experience"][0]["highlights"][0]["text"],
            "优化后台服务维护流程，支撑内部系统开发交付",
        )
        self.assertEqual(agent.runtime.stream_fn.calls, 2)

    async def test_resume_agent_runtime_stream_hides_tool_preamble_text(self):
        """用于验证工具调用前的 assistant 文本不会展示。"""
        agent = ResumeAgent()
        agent.runtime = ResumeAgentRuntime(
            stream_fn=FakePiAgentStream(
                [
                    fake_pi_message(
                        FakeModelResponse(
                            content="我先说明这次会优化工作经历。",
                            tool_calls=[
                                fake_tool_call(
                                    name="update_bullet",
                                    args={
                                        "section": "work_experience",
                                        "item_id": "work_1",
                                        "bullet_id": "hl_1",
                                        "text": "优化后台服务维护流程，支撑内部系统开发交付",
                                        "reason": "补充交付结果",
                                    },
                                    call_id="call_pi_preamble",
                                )
                            ],
                        )
                    ),
                    fake_pi_text("已完成优化。"),
                ]
            )
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="优化这段工作经历，事实是后台服务维护流程支撑内部系统开发交付",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
            allowed_sections={"work_experience"},
        ):
            events.append(event)


        visible_text = "".join(event.get("content", "") for event in events)
        self.assertNotIn("我先说明这次会优化工作经历。", visible_text)
        self.assertIn("已完成优化。", visible_text)
        self.assertTrue(any(event.get("tool_pending") for event in events))

    async def test_resume_agent_runtime_stream_shows_running_tool_on_early_start(self):
        """用于验证 first_tool_delta 时可提前显示 Running 工具名。"""
        agent = ResumeAgent()
        tool_call = fake_tool_call(
            name="update_bullet",
            args={
                "section": "work_experience",
                "item_id": "work_1",
                "bullet_id": "hl_1",
                "text": "优化后台服务维护流程，支撑内部系统开发交付",
                "reason": "补充交付结果",
            },
            call_id="call_pi_early",
        )
        early_tool_call = ToolCall(
            id="call_pi_early",
            name="update_bullet",
            arguments={},
        )
        agent.runtime = ResumeAgentRuntime(
            stream_fn=FakeEarlyToolStartStream(
                [
                    fake_pi_message(FakeModelResponse(content="", tool_calls=[tool_call])),
                    fake_pi_text("已完成优化。"),
                ],
                early_tool_call,
            )
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="优化这段工作经历，事实是后台服务维护流程支撑内部系统开发交付",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
            allowed_sections={"work_experience"},
        ):
            events.append(event)

        tool_call_events = [
            event for event in events if event.get("event_type") == "tool_call"
        ]
        pending_index = next(
            index for index, event in enumerate(events) if event.get("tool_pending")
        )
        tool_call_index = next(
            index for index, event in enumerate(events) if event.get("event_type") == "tool_call"
        )
        self.assertEqual(len(tool_call_events), 1)
        self.assertLess(tool_call_index, pending_index)
        self.assertEqual(tool_call_events[0]["call_id"], "call_pi_early")
        self.assertEqual(tool_call_events[0]["tool_display_name"], "update_bullet")
        self.assertTrue(any(event.get("tool_confirmed") for event in events))

    async def test_resume_agent_runtime_stream_failed_event_for_invalid_tool_arguments_marker(self):
        """用于验证模型工具参数损坏时走失败事件而不是确认卡片。"""
        agent = ResumeAgent()
        agent.runtime = ResumeAgentRuntime(
            stream_fn=FakePiAgentStream(
                [
                    fake_pi_tool_call(
                        name="update_bullet",
                        args={
                            "__tool_arguments_parse_error": {
                                "type": "invalid_arguments_json",
                                "message": "Expecting property name",
                            }
                        },
                        call_id="call_pi_bad_args",
                    ),
                    fake_pi_text("工具参数格式有误，我会重新生成。"),
                ]
            )
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="优化这段工作经历",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
            allowed_sections={"work_experience"},
        ):
            events.append(event)

        self.assertTrue(any(event.get("tool_call_failed") for event in events))
        self.assertFalse(any(event.get("tool_pending") for event in events))
        self.assertEqual(agent.runtime.stream_fn.calls, 2)
        self.assertIn(
            "工具参数格式有误",
            "".join(event.get("content", "") for event in events),
        )

    async def test_resume_agent_runtime_stream_failed_preview_skips_confirmation_card(self):
        """用于验证工具预览失败时不展示待确认空 diff 卡片。"""
        agent = ResumeAgent()
        agent.runtime = ResumeAgentRuntime(
            stream_fn=FakePiAgentStream(
                [
                    fake_pi_tool_call(
                        name="update_item_fields",
                        args={
                            "section": "projects",
                            "item_id": "proj_1",
                            "fields": {"technologies": ["Python"]},
                            "reason": "用户要求补充 Python 到项目技术栈",
                        },
                        call_id="call_pi_invalid_preview",
                    ),
                    fake_pi_text("项目技术栈字段当前不支持直接写入，我会改为更新项目简介。"),
                ]
            )
        )
        resume = {
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Deep Research Agent",
                    "overview": "基于 LangChain 构建研究智能体。",
                    "technologies": ["LangChain"],
                }
            ]
        }
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="Python",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
            allowed_sections={"projects"},
        ):
            events.append(event)

        self.assertTrue(any(event.get("tool_call_failed") for event in events))
        self.assertFalse(any(event.get("tool_pending") for event in events))
        self.assertEqual(resume["projects"][0]["technologies"], ["LangChain"])
        self.assertEqual(agent.runtime.stream_fn.calls, 2)
        self.assertIn(
            "当前不支持直接写入",
            "".join(event.get("content", "") for event in events),
        )

    async def test_resume_agent_runtime_noop_update_skips_confirmation_card(self):
        """用于验证空修改只回灌模型，不展示失败或待确认卡片。"""
        agent = ResumeAgent()
        agent.runtime = ResumeAgentRuntime(
            stream_fn=FakePiAgentStream(
                [
                    fake_pi_tool_call(
                        name="update_bullet",
                        args={
                            "section": "work_experience",
                            "item_id": "work_1",
                            "bullet_id": "hl_1",
                            "text": "维护多个后台服务",
                            "reason": "只解释优化理由",
                        },
                        call_id="call_pi_noop",
                    ),
                    fake_pi_text("这条内容已经合适，无需修改。"),
                ]
            )
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="优化这条 bullet",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
            allowed_sections={"work_experience"},
        ):
            events.append(event)

        self.assertFalse(any(event.get("tool_call_failed") for event in events))
        self.assertFalse(any(event.get("tool_pending") for event in events))
        self.assertEqual(
            resume["work_experience"][0]["highlights"][0]["text"],
            "维护多个后台服务",
        )
        self.assertEqual(agent.runtime.stream_fn.calls, 2)
        self.assertIn(
            "无需修改",
            "".join(event.get("content", "") for event in events),
        )

    async def test_resume_agent_runtime_sets_provider_cancel_event_when_stream_is_cancelled(self):
        """用于验证消费端取消时通知底层模型流停止。"""
        stream = HangingPiAgentStream()
        agent = ResumeAgent()
        agent.runtime = ResumeAgentRuntime(stream_fn=stream)

        async def consume_stream():
            """消费 Agent 流直到测试主动取消。"""
            async for _event in agent.optimize_stream(
                user_message="优化这段工作经历",
                resume_content=self._sample_resume(),
                conversation_history=[],
                confirmation_queue=None,
                allowed_sections={"work_experience"},
            ):
                pass

        task = asyncio.create_task(consume_stream())
        await asyncio.wait_for(stream.started.wait(), timeout=1)
        self.assertEqual(len(stream.options), 1)
        self.assertIsNotNone(stream.options[0].cancel_event)

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertTrue(stream.options[0].cancel_event.is_set())

    async def test_resume_agent_runtime_stream_emits_agent_trace_logs(self):
        """用于验证piAgentruntimestreamemitsAgenttracelogs。"""
        agent = ResumeAgent()
        agent.runtime = ResumeAgentRuntime(
            stream_fn=FakePiAgentStream(
                [
                    fake_pi_tool_call(
                        name="update_bullet",
                        args={
                            "section": "work_experience",
                            "item_id": "work_1",
                            "bullet_id": "hl_1",
                            "text": "优化后台服务维护流程，支撑内部系统开发交付",
                            "reason": "补充交付结果",
                        },
                        call_id="call_pi_trace",
                    ),
                    fake_pi_text("已完成优化。"),
                ]
            )
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        original_trace_log_enabled = settings.AGENT_TRACE_LOG_ENABLED
        original_chunk_log_enabled = settings.AGENT_TRACE_CHUNK_LOG_ENABLED
        settings.AGENT_TRACE_LOG_ENABLED = True
        settings.AGENT_TRACE_CHUNK_LOG_ENABLED = False
        try:
            with self.assertLogs("app.agents.resume.runtime", level="INFO") as logs:
                events = []
                async for event in agent.optimize_stream(
                    user_message="优化这段工作经历，事实是后台服务维护流程支撑内部系统开发交付",
                    resume_content=resume,
                    conversation_history=[],
                    confirmation_queue=confirmation_queue,
                    allowed_sections={"work_experience"},
                ):
                    events.append(event)
        finally:
            settings.AGENT_TRACE_LOG_ENABLED = original_trace_log_enabled
            settings.AGENT_TRACE_CHUNK_LOG_ENABLED = original_chunk_log_enabled

        trace_records = [
            record for record in logs.records if getattr(record, "agent_trace", False)
        ]
        trace_messages = [record.getMessage() for record in trace_records]

        self.assertTrue(any(event.get("tool_confirmed") for event in events))
        self.assertEqual(agent.runtime.stream_fn.calls, 2)
        self.assertIn("agent.trace.run.started", trace_messages)
        self.assertIn("agent.trace.prompt.rendered", trace_messages)
        self.assertIn("agent.trace.llm.request", trace_messages)
        self.assertIn("agent.trace.reasoning.tool_call_detected", trace_messages)
        self.assertIn("agent.trace.tool.requested", trace_messages)
        self.assertIn("agent.trace.tool.preview", trace_messages)
        self.assertIn("agent.trace.tool.confirmation", trace_messages)
        self.assertIn("agent.trace.tool.executed", trace_messages)
        self.assertIn("agent.trace.llm.response", trace_messages)
        self.assertNotIn("agent.trace.run.stopped_after_confirmation", trace_messages)
        self.assertIn("agent.trace.run.completed", trace_messages)
        self.assertNotIn("agent.trace.intermediate.chunk", trace_messages)

    async def test_resume_agent_runtime_can_opt_into_chunk_trace_logs(self):
        """用于验证流式 chunk 日志需要显式开启。"""
        agent = ResumeAgent()
        agent.runtime = ResumeAgentRuntime(stream_fn=FakePiAgentStream([fake_pi_text("你好")]))
        resume = self._sample_resume()

        original_trace_log_enabled = settings.AGENT_TRACE_LOG_ENABLED
        original_chunk_log_enabled = settings.AGENT_TRACE_CHUNK_LOG_ENABLED
        settings.AGENT_TRACE_LOG_ENABLED = True
        settings.AGENT_TRACE_CHUNK_LOG_ENABLED = True
        try:
            with self.assertLogs("app.agents.resume.runtime", level="INFO") as logs:
                events = []
                async for event in agent.optimize_stream(
                    user_message="帮我看看简历",
                    resume_content=resume,
                    conversation_history=[],
                    allowed_sections={"work_experience", "projects"},
                ):
                    events.append(event)
        finally:
            settings.AGENT_TRACE_LOG_ENABLED = original_trace_log_enabled
            settings.AGENT_TRACE_CHUNK_LOG_ENABLED = original_chunk_log_enabled

        trace_messages = [
            record.getMessage()
            for record in logs.records
            if getattr(record, "agent_trace", False)
        ]
        self.assertTrue(any(event.get("content") == "你好" for event in events))
        self.assertIn("agent.trace.intermediate.chunk", trace_messages)

    async def test_resume_agent_runtime_stream_logs_single_run_summary(self):
        """用于验证每次流式 run 只记录一条结构化摘要。"""
        agent = ResumeAgent()
        agent.runtime = ResumeAgentRuntime(stream_fn=FakePiAgentStream([fake_pi_text("你好")]))
        resume = self._sample_resume()

        with self.assertLogs("app.agents.resume.runtime", level="INFO") as logs:
            events = []
            async for event in agent.optimize_stream(
                user_message="帮我看看简历",
                resume_content=resume,
                conversation_history=[],
                allowed_sections={"work_experience", "projects"},
            ):
                events.append(event)

        summary_records = [
            record
            for record in logs.records
            if record.getMessage() == "resume_agent.run.summary"
        ]
        self.assertTrue(any(event.get("content") == "你好" for event in events))
        self.assertEqual(len(summary_records), 1)
        summary = summary_records[0]
        self.assertEqual(getattr(summary, "agent_name"), "resume_agent")
        self.assertEqual(getattr(summary, "mode"), "stream")
        expected_provider = (
            "deepseek"
            if settings.OPENAI_AGENTS_PROVIDER == "deepseek"
            else "openai-agents"
        )
        self.assertEqual(getattr(summary, "provider"), expected_provider)
        self.assertEqual(getattr(summary, "model"), settings.OPENAI_AGENTS_MODEL)
        self.assertGreater(getattr(summary, "prompt_chars"), 0)
        self.assertGreaterEqual(getattr(summary, "message_count"), 1)
        self.assertEqual(
            getattr(summary, "tool_count"),
            len(agent.definition.tool_profiles[agent.definition.default_tool_profile]),
        )
        self.assertIsNotNone(getattr(summary, "first_token_ms"))
        self.assertGreaterEqual(getattr(summary, "llm_total_ms"), 0)
        self.assertGreaterEqual(getattr(summary, "total_ms"), 0)
        self.assertEqual(getattr(summary, "tool_requested"), 0)
        self.assertEqual(getattr(summary, "tool_executed"), 0)
        self.assertEqual(getattr(summary, "tool_confirmed"), 0)
        self.assertEqual(getattr(summary, "tool_rejected"), 0)
        self.assertEqual(getattr(summary, "approval_wait_ms"), 0.0)
        self.assertEqual(getattr(summary, "guardrail_rejected"), 0)
        self.assertEqual(getattr(summary, "final_status"), "completed")
        self.assertEqual(getattr(summary, "error"), "-")
        self.assertEqual(getattr(summary, "tool_call_count"), 0)
        self.assertEqual(getattr(summary, "confirmation_wait_ms"), 0.0)
        self.assertGreaterEqual(getattr(summary, "elapsed_ms"), 0)
        self.assertTrue(getattr(summary, "success"))
        self.assertEqual(getattr(summary, "error_type"), "-")


class ChatServiceChunkParsingTests(unittest.TestCase):
    def test_extract_sse_data_accepts_data_prefix_without_space(self):
        """用于验证extractssedataacceptsdataprefixwithoutspace。"""
        self.assertEqual(
            ChatService._extract_sse_data('data:{"choices":[{"text":"ok"}]}'),
            '{"choices":[{"text":"ok"}]}',
        )

    def test_extract_stream_delta_accepts_message_content(self):
        """用于验证extractstreamdeltaacceptsmessagecontent。"""
        chunk = {
            "choices": [
                {
                    "message": {
                        "content": '{"question":"请介绍你最熟悉的 Agent 项目","question_type":"experience","intent":"评估项目经验"}'
                    }
                }
            ]
        }

        self.assertEqual(
            ChatService._extract_stream_delta(chunk),
            {
                "content": '{"question":"请介绍你最熟悉的 Agent 项目","question_type":"experience","intent":"评估项目经验"}'
            },
        )

    def test_extract_stream_delta_flattens_content_parts(self):
        """用于验证extractstreamdeltaflattenscontentparts。"""
        chunk = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": '{"question":"请介绍你的系统设计思路",',
                            },
                            {
                                "type": "text",
                                "text": '"question_type":"technical","intent":"评估架构能力"}',
                            },
                        ]
                    }
                }
            ]
        }

        self.assertEqual(
            ChatService._extract_stream_delta(chunk),
            {
                "content": '{"question":"请介绍你的系统设计思路","question_type":"technical","intent":"评估架构能力"}'
            },
        )


class RuntimePublicApiTests(unittest.TestCase):
    def test_agent_runtime_compatibility_entrypoint_is_removed(self):
        """用于验证Agentruntimecompatibilityentrypointisremoved。"""
        import app.runtime as runtime

        self.assertNotIn("AgentHarness", runtime.__all__)
        self.assertNotIn("AgentRuntime", runtime.__all__)
        self.assertNotIn("PiAgentRuntime", runtime.__all__)
        with self.assertRaises(AttributeError):
            getattr(runtime, "AgentHarness")
        with self.assertRaises(AttributeError):
            getattr(runtime, "AgentRuntime")
        with self.assertRaises(AttributeError):
            getattr(runtime, "PiAgentRuntime")

    def test_agent_definition_lives_in_runtime_contracts(self):
        """用于验证Agentdefinitionlivesinruntimecontracts。"""
        from app.runtime.contracts import AgentDefinition

        agent = ResumeAgent()
        self.assertIsInstance(agent.definition, AgentDefinition)

    def test_resume_agent_public_api_uses_resume_specific_harness_name(self):
        """用于验证ResumeAgent公开API不再导出通用AgentHarness命名。"""
        import app.agents.resume as resume_agent

        self.assertNotIn("AgentHarness", resume_agent.__all__)
        self.assertIn("ResumeAgentHarness", resume_agent.__all__)
        with self.assertRaises(AttributeError):
            getattr(resume_agent, "AgentHarness")


if __name__ == "__main__":
    unittest.main()
