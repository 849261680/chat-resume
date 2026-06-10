"""Resume Agent eval 的共享 case 规范化和执行 harness。"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
EVAL_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.infra.config import settings  # noqa: E402
from app.runtime.openai_agents_eval import use_openai_agents_trace_config  # noqa: E402
from app.schemas.resume import dump_resume_content_for_frontend  # noqa: E402
from eval.openai_agents_standard import (  # noqa: E402
    build_eval_artifact,
    build_trace_config,
)


def load_backend_env() -> None:
    """用于在 shell 未导出时读取 backend/.env 里的 eval 依赖。"""
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def build_agent() -> ResumeAgent:
    """用于构建当前代码路径下的真实 Resume Agent。"""
    return ResumeAgent()


def required_agent_api_key_name() -> str:
    """用于返回当前 Agents SDK provider 需要的 API key 环境变量名。"""
    provider = settings.OPENAI_AGENTS_PROVIDER.strip().lower()
    if provider == "deepseek":
        return "DEEPSEEK_API_KEY"
    return "OPENAI_API_KEY"


def has_required_agent_api_key() -> bool:
    """用于判断当前 eval provider 是否具备模型调用密钥。"""
    return bool(os.environ.get(required_agent_api_key_name()))


def normalize_legacy_highlights(items: Any) -> list[Any]:
    """用于把旧样本里的 string highlights 转成当前对象结构。"""
    if not isinstance(items, list):
        return []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        next_item = dict(item)
        highlights = next_item.get("highlights")
        if isinstance(highlights, list) and all(
            isinstance(highlight, str) for highlight in highlights
        ):
            next_item["highlights"] = [
                {"text": str(highlight).strip()}
                for highlight in highlights
                if str(highlight).strip()
            ]
        normalized.append(next_item)
    return normalized


def normalize_resume(resume: Any) -> dict[str, Any]:
    """用于把 eval resume 输入规范化成前端简历 schema。"""
    if not isinstance(resume, dict):
        return {}
    next_resume = dict(resume)
    for section in ("education", "work_experience", "projects"):
        if isinstance(next_resume.get(section), list):
            next_resume[section] = normalize_legacy_highlights(next_resume[section])
    return dump_resume_content_for_frontend(next_resume)


def inject_job_application(
    resume: dict[str, Any],
    jd: dict[str, Any] | None,
) -> dict[str, Any]:
    """用于把 JD 信息写入 resume_content.job_application。"""
    if jd is None:
        return resume
    next_resume = dict(resume)
    current = next_resume.get("job_application")
    job_application = dict(current) if isinstance(current, dict) else {}
    job_application.update(
        {
            "target_title": str(jd.get("title", "") or ""),
            "target_company": str(jd.get("company", "") or ""),
            "jd_text": str(jd.get("description", "") or ""),
        }
    )
    next_resume["job_application"] = job_application
    return next_resume


def build_message_with_jd(user_message: str, jd: dict[str, Any] | None) -> str:
    """用于把 JD 文本追加到 eval 用户消息中。"""
    if jd is None:
        return user_message
    jd_text = f"\n\n【目标岗位JD】\n职位：{jd.get('title', '')}\n{jd.get('description', '')}"
    return user_message + jd_text


def tool_names(tool_calls: Any) -> list[str]:
    """用于从 runtime 结果中提取工具名。"""
    if not isinstance(tool_calls, list):
        return []
    names: list[str] = []
    for item in tool_calls:
        if isinstance(item, dict):
            name = item.get("name") or item.get("tool") or item.get("tool_name")
        else:
            name = item
        if name:
            names.append(str(name))
    return names


def infer_decision(reply: str, tools: list[str]) -> str:
    """用于为 optimize-first eval 推断粗粒度决策标签。"""
    if tools:
        return "execute"
    if "?" in reply or "？" in reply:
        return "clarify"
    return "respond"


async def run_agent_target(
    agent: ResumeAgent,
    inputs: dict[str, Any],
    case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """用于执行本地 eval 的单条目标函数。"""
    resume = normalize_resume(inputs.get("resume"))
    jd = inputs.get("jd") if isinstance(inputs.get("jd"), dict) else None
    resume = inject_job_application(resume, jd)
    message = build_message_with_jd(str(inputs.get("user_message", "")), jd)
    runtime_events: list[dict[str, Any]] = []
    trace_config = build_trace_config(str(inputs.get("case_id", "case")))
    started_at = time.time()
    with use_openai_agents_trace_config(trace_config):
        result = await agent.runtime.run(
            agent=agent.definition,
            user_message=message,
            context={"resume_content": resume, "allowed_sections": None},
            event_callback=lambda event: runtime_events.append(dict(event)),
        )
    elapsed_s = round(time.time() - started_at, 2)
    reply = str(result.get("content", ""))
    tools = tool_names(result.get("tool_calls"))
    resume_after = resume_after_from_result(result, runtime_events)
    output = {
        "case_id": inputs.get("case_id"),
        "agent_reply": reply,
        "tool_calls": tools,
        "decision": infer_decision(reply, tools),
        "elapsed_s": elapsed_s,
        "resume_after": resume_after,
        "runtime_events": runtime_events,
    }
    if case is not None:
        output["openai_agents_eval"] = build_eval_artifact(
            case=case,
            inputs={**inputs, "user_message": message, "resume": resume, "jd": jd},
            result=output,
            trace_config=trace_config,
        )
    return output


def resume_after_from_result(
    result: dict[str, Any],
    runtime_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """用于从最终结果或工具事件中恢复最新简历内容。"""
    final_context = result.get("context")
    resume_after = _resume_from_context(final_context)
    if resume_after:
        return resume_after
    for event in reversed(runtime_events):
        resume_after = _resume_from_context(event.get("context"))
        if resume_after:
            return resume_after
    return {}


def _resume_from_context(context: Any) -> dict[str, Any]:
    """用于从 runtime context 中读取 resume_content。"""
    if not isinstance(context, dict):
        return {}
    resume = context.get("resume_content")
    return resume if isinstance(resume, dict) else {}


__all__ = [
    "EVAL_DIR",
    "build_agent",
    "build_message_with_jd",
    "infer_decision",
    "has_required_agent_api_key",
    "inject_job_application",
    "load_backend_env",
    "normalize_resume",
    "required_agent_api_key_name",
    "resume_after_from_result",
    "run_agent_target",
    "tool_names",
]
