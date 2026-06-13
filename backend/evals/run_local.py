#!/usr/bin/env python
"""用于本地运行 Resume Agent 行为门禁。"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pi_agent_core import (
    AgentContext,
    AgentTool,
    AgentToolSchema,
    AssistantMessage,
    Model,
    SimpleStreamOptions,
    StreamDoneEvent,
    StreamStartEvent,
    StreamTextDeltaEvent,
    StreamTextEndEvent,
    StreamTextStartEvent,
    StreamToolCallEndEvent,
    StreamToolCallStartEvent,
    TextContent,
    ToolCall,
    UserMessage,
)
from pi_agent_core.types import StreamResult
from openai.types.responses import ResponseFunctionToolCall
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseCreatedEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseInProgressEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
)
from agents.items import ModelResponse
from agents.models.interface import Model as OpenAIAgentsModel
from agents.usage import Usage as OpenAIAgentsUsage

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.agents.resume.observability import (  # noqa: E402
    bind_observability_state,
    reset_observability_state,
)
from app.agents.resume.runtime import ResumeAgentRuntime  # noqa: E402
from app.runtime.openai_agents_adapter import OpenAIAgentsStreamAdapter  # noqa: E402


@dataclass
class EvalResult:
    """用于保存单条本地 eval 结果。"""

    id: str
    category: str
    passed: bool
    checks: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class ScriptedStream:
    """用于给 ResumeAgentRuntime 提供确定性模型输出。"""

    def __init__(self, messages: list[AssistantMessage]):
        """用于保存预设 assistant 消息。"""
        self.messages = list(messages)
        self.calls = 0

    async def __call__(
        self,
        _model: Model,
        _context: AgentContext,
        _options: SimpleStreamOptions,
    ) -> StreamResult:
        """用于返回 pi-agent-core StreamResult。"""
        message = self.messages[self.calls]
        self.calls += 1
        events = self.events_for(message)

        async def events_iter():
            """用于按顺序产出预设流事件。"""
            for event in events:
                yield event

        async def result():
            """用于返回完整 assistant 消息。"""
            return message

        return {"events": events_iter(), "result": result}

    @staticmethod
    def events_for(message: AssistantMessage) -> list[Any]:
        """用于把完整 assistant 消息转换成流事件。"""
        events: list[Any] = [StreamStartEvent(partial=message)]
        for index, block in enumerate(message.content):
            if isinstance(block, TextContent):
                events.extend([
                    StreamTextStartEvent(content_index=index, partial=message),
                    StreamTextDeltaEvent(content_index=index, delta=block.text, partial=message),
                    StreamTextEndEvent(content_index=index, content=block.text, partial=message),
                ])
            if isinstance(block, ToolCall):
                events.extend([
                    StreamToolCallStartEvent(content_index=index, partial=message),
                    StreamToolCallEndEvent(content_index=index, tool_call=block, partial=message),
                ])
        events.append(StreamDoneEvent(reason=message.stop_reason, message=message))
        return events


class GuardrailRejectModel(OpenAIAgentsModel):
    """用于模拟 SDK 模型先输出坏工具参数再恢复。"""

    def __init__(self):
        """用于初始化调用记录。"""
        self.calls = 0
        self.tool_executed = False

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: Any,
        tools: list[Any],
        output_schema: Any,
        handoffs: list[Any],
        tracing: Any,
        *,
        previous_response_id: str | None = None,
        conversation_id: str | None = None,
        prompt: Any = None,
    ) -> ModelResponse:
        """用于生成 SDK Runner 可消费的 ModelResponse。"""
        del system_instructions, input, model_settings, tools, output_schema
        del handoffs, tracing, previous_response_id, conversation_id, prompt

        self.calls += 1
        if self.calls == 1:
            output = [
                    ResponseFunctionToolCall(
                        id="fc_eval_bad",
                        call_id="call_eval_bad",
                        name="update_bullet",
                        arguments="{bad-json",
                        type="function_call",
                    )
                ]
        else:
            output = [
                ResponseOutputMessage(
                    id="msg_eval_guardrail",
                    role="assistant",
                    status="completed",
                    type="message",
                    content=[
                        ResponseOutputText(
                            annotations=[],
                            text="工具参数已被拦截。",
                            type="output_text",
                        )
                    ],
                )
            ]
        return ModelResponse(
            output=output,
            usage=OpenAIAgentsUsage(input_tokens=1, output_tokens=1, total_tokens=2),
            response_id=f"resp_eval_guardrail_{self.calls}",
        )

    async def stream_response(self, *args: Any, **kwargs: Any) -> Any:
        """用于生成 SDK streaming events。"""
        model_response = await self.get_response(*args, **kwargs)
        response = Response(
            id=model_response.response_id or "resp_eval",
            created_at=0,
            model="eval-model",
            object="response",
            output=model_response.output,
            parallel_tool_calls=False,
            tool_choice="auto",
            tools=[],
        )
        sequence_number = 0
        yield ResponseCreatedEvent(type="response.created", response=response, sequence_number=sequence_number)
        sequence_number += 1
        yield ResponseInProgressEvent(type="response.in_progress", response=response, sequence_number=sequence_number)
        sequence_number += 1
        for output_index, output_item in enumerate(model_response.output):
            yield ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                item=output_item,
                output_index=output_index,
                sequence_number=sequence_number,
            )
            sequence_number += 1
            if isinstance(output_item, ResponseFunctionToolCall):
                yield ResponseFunctionCallArgumentsDeltaEvent(
                    type="response.function_call_arguments.delta",
                    item_id=output_item.call_id,
                    output_index=output_index,
                    delta=output_item.arguments,
                    sequence_number=sequence_number,
                )
                sequence_number += 1
                yield ResponseFunctionCallArgumentsDoneEvent(
                    type="response.function_call_arguments.done",
                    item_id=output_item.call_id,
                    output_index=output_index,
                    arguments=output_item.arguments,
                    name=output_item.name,
                    sequence_number=sequence_number,
                )
                sequence_number += 1
            if isinstance(output_item, ResponseOutputMessage):
                content = output_item.content[0]
                if isinstance(content, ResponseOutputText):
                    yield ResponseContentPartAddedEvent(
                        type="response.content_part.added",
                        content_index=0,
                        item_id=output_item.id,
                        output_index=output_index,
                        part=content,
                        sequence_number=sequence_number,
                    )
                    sequence_number += 1
                    yield ResponseTextDeltaEvent(
                        type="response.output_text.delta",
                        content_index=0,
                        item_id=output_item.id,
                        output_index=output_index,
                        delta=content.text,
                        logprobs=[],
                        sequence_number=sequence_number,
                    )
                    sequence_number += 1
                    yield ResponseTextDoneEvent(
                        type="response.output_text.done",
                        content_index=0,
                        item_id=output_item.id,
                        output_index=output_index,
                        text=content.text,
                        logprobs=[],
                        sequence_number=sequence_number,
                    )
                    sequence_number += 1
                    yield ResponseContentPartDoneEvent(
                        type="response.content_part.done",
                        content_index=0,
                        item_id=output_item.id,
                        output_index=output_index,
                        part=content,
                        sequence_number=sequence_number,
                    )
                    sequence_number += 1
            yield ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=output_item,
                output_index=output_index,
                sequence_number=sequence_number,
            )
            sequence_number += 1
        yield ResponseCompletedEvent(
            type="response.completed",
            response=response,
            sequence_number=sequence_number,
        )


def sample_resume() -> dict[str, Any]:
    """用于生成本地 eval 的最小简历。"""
    return {
        "personal_info": {
            "name": "张三",
            "email": "zhangsan@example.com",
            "photo_url": "data:image/jpeg;base64,avatar-payload",
        },
        "summary": {"text": "3 年 Python 后端开发经验"},
        "work_experience": [
            {
                "id": "work_1",
                "company": "某科技公司",
                "position": "后端开发",
                "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
            }
        ],
        "projects": [],
    }


def text_message(text: str) -> AssistantMessage:
    """用于构造文本 assistant 消息。"""
    return AssistantMessage(content=[TextContent(text=text)], stop_reason="stop")


def tool_message(name: str, call_id: str, args: dict[str, Any]) -> AssistantMessage:
    """用于构造工具调用 assistant 消息。"""
    return AssistantMessage(
        content=[ToolCall(id=call_id, name=name, arguments=args)],
        stop_reason="toolUse",
    )


async def eval_avatar_not_in_prompt() -> EvalResult:
    """用于验证头像不会进入 Agent prompt。"""
    agent = ResumeAgent()
    prompt_context = agent._build_prompt_context({"resume_content": sample_resume()})
    resume_json = prompt_context["resume_json"]
    checks = {
        "contains_name": "张三" in resume_json,
        "contains_photo_url": "photo_url" in resume_json,
        "contains_data_image": "data:image" in resume_json,
    }
    return EvalResult(
        id="avatar_not_in_prompt",
        category="prompt_context",
        passed=checks["contains_name"] and not checks["contains_photo_url"] and not checks["contains_data_image"],
        checks=checks,
    )


async def eval_reject_diff_keeps_resume_unchanged() -> EvalResult:
    """用于验证用户拒绝 diff 后不修改简历。"""
    agent = ResumeAgent()
    agent.runtime = ResumeAgentRuntime(stream_fn=ScriptedStream([
        tool_message(
            "update_bullet",
            "call_eval_reject",
            {
                "section": "work_experience",
                "item_id": "work_1",
                "bullet_id": "hl_1",
                "text": "优化后台服务维护流程，支撑交付效率提升",
            },
        ),
        text_message("已取消这处修改。"),
    ]))
    resume = sample_resume()
    confirmation_queue: asyncio.Queue[Any] = asyncio.Queue()
    confirmation_queue.put_nowait(False)
    events = []
    async for event in agent.optimize_stream(
        user_message="优化第一条工作经历",
        resume_content=resume,
        conversation_history=[],
        confirmation_queue=confirmation_queue,
    ):
        events.append(event)
    checks = {
        "saw_tool_rejected": any(event.get("tool_rejected") for event in events),
        "original_text_kept": resume["work_experience"][0]["highlights"][0]["text"] == "维护多个后台服务",
    }
    return EvalResult(
        id="reject_diff_keeps_resume_unchanged",
        category="approval",
        passed=all(checks.values()),
        checks=checks,
    )


async def eval_invalid_tool_json_guardrail() -> EvalResult:
    """用于验证 SDK guardrail 会拦截非法工具 JSON。"""
    model = GuardrailRejectModel()
    adapter = OpenAIAgentsStreamAdapter(sdk_model=model)

    async def execute_tool(_call_id: str, _params: dict[str, Any]) -> Any:
        """用于确保 guardrail 触发时业务工具不执行。"""
        model.tool_executed = True
        return None

    context = AgentContext(
        system_prompt="你是简历优化 Agent。",
        messages=[UserMessage(content=[TextContent(text="优化项目 bullet")])],
        tools=[
            AgentTool(
                name="update_bullet",
                description="更新已有简历要点。",
                parameters=AgentToolSchema(
                    type="object",
                    properties={"section": {"type": "string"}},
                    required=["section"],
                ),
                execute=execute_tool,
            )
        ],
    )
    state = {"guardrail_rejected_count": 0}
    token = bind_observability_state(state)
    try:
        response = await adapter(
            Model(api="responses", provider="openai-agents", id="eval-model"),
            context,
            SimpleStreamOptions(api_key="test-key", temperature=0.0, max_tokens=128),
        )
        result = response["result"]()
        if inspect.isawaitable(result):
            await result
    finally:
        reset_observability_state(token)
    checks = {
        "guardrail_rejected": state["guardrail_rejected_count"] == 1,
        "business_tool_not_executed": not model.tool_executed,
    }
    return EvalResult(
        id="invalid_tool_json_guardrail",
        category="guardrail",
        passed=all(checks.values()),
        checks=checks,
    )

async def run_cases() -> list[EvalResult]:
    """用于执行所有本地 eval case。"""
    cases = [
        eval_avatar_not_in_prompt,
        eval_reject_diff_keeps_resume_unchanged,
        eval_invalid_tool_json_guardrail,
    ]
    results = []
    for case in cases:
        try:
            results.append(await case())
        except Exception as exc:
            results.append(EvalResult(id=case.__name__, category="error", passed=False, error=str(exc)))
    return results


def write_report(results: list[EvalResult]) -> Path:
    """用于写入最新 eval 结果。"""
    result_path = BACKEND_DIR / "evals" / "results" / "latest.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": sum(1 for item in results if item.passed),
        "failed": sum(1 for item in results if not item.passed),
        "results": [item.__dict__ for item in results],
    }
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return result_path


async def main() -> int:
    """用于执行本地 eval gate 并返回进程退出码。"""
    results = await run_cases()
    report_path = write_report(results)
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        print(f"{status} {item.id}")
        if item.error:
            print(f"  error={item.error}")
    failed = [item for item in results if not item.passed]
    print(f"wrote {report_path}")
    print(f"passed={len(results) - len(failed)}/{len(results)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
