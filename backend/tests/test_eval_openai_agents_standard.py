"""用于覆盖 OpenAI Agents SDK eval 标准化产物。"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
EVAL_DIR = ROOT_DIR / "eval"
for path in (ROOT_DIR, BACKEND_DIR, EVAL_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _load_standard_module() -> ModuleType:
    """用于按文件路径加载 OpenAI Agents eval 标准化模块。"""
    spec = importlib.util.spec_from_file_location(
        "openai_agents_standard",
        EVAL_DIR / "openai_agents_standard.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load openai_agents_standard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STANDARD = _load_standard_module()
OPENAI_AGENTS_EVAL_NAME = STANDARD.OPENAI_AGENTS_EVAL_NAME
build_dataset_item = STANDARD.build_dataset_item
build_eval_artifact = STANDARD.build_eval_artifact
build_eval_run_summary = STANDARD.build_eval_run_summary
build_model_sample = STANDARD.build_model_sample
build_python_grader = STANDARD.build_python_grader
build_trace_config = STANDARD.build_trace_config


def test_build_trace_config_uses_openai_trace_fields():
    """用于验证 trace 配置符合 OpenAI Agents SDK RunConfig 字段。"""
    trace_config = build_trace_config("TC001")

    assert trace_config.workflow_name == "chat-resume.resume-agent.eval"
    assert trace_config.trace_id.startswith("trace_")
    assert trace_config.group_id == "chat-resume-eval:TC001"
    assert trace_config.metadata["case_id"] == "TC001"
    assert trace_config.metadata["standard"] == "openai-agents-sdk"
    assert trace_config.trace_include_sensitive_data is False


def test_build_dataset_item_preserves_case_expectations():
    """用于验证本地 case 会转换成 dataset item。"""
    item = build_dataset_item(
        case={
            "id": "TC001",
            "expected_decision": "execute",
            "expected_tool_calls": ["update_bullet"],
            "must_contain_keywords": ["FastAPI"],
            "forbidden_content": ["虚构"],
        },
        inputs={
            "case_id": "TC001",
            "user_message": "优化简历",
            "resume": {"projects": []},
            "jd": {"title": "后端"},
        },
    )

    assert item["case_id"] == "TC001"
    assert item["input"]["user_message"] == "优化简历"
    assert item["expected_decision"] == "execute"
    assert item["expected_tool_calls"] == ["update_bullet"]
    assert item["must_contain_keywords"] == ["FastAPI"]
    assert item["forbidden_content"] == ["虚构"]


def test_python_grader_scores_matching_workflow_sample():
    """用于验证生成的 Python grader 能评分工具和输出状态。"""
    grader = build_python_grader()
    namespace: dict[str, Any] = {}
    exec(str(grader["source"]), namespace)
    sample = build_model_sample(
        {
            "agent_reply": "已完成优化。",
            "decision": "execute",
            "tool_calls": ["update_bullet"],
            "resume_after": {"projects": [{"highlights": [{"text": "使用 FastAPI"}]}]},
            "runtime_events": [],
        }
    )
    item = {
        "expected_decision": "execute",
        "expected_tool_calls": ["update_bullet"],
        "must_contain_keywords": ["FastAPI"],
        "forbidden_content": ["虚构"],
    }

    assert namespace["grade"](sample, item) == 1.0


def test_build_eval_artifact_contains_trace_dataset_sample_and_grader():
    """用于验证单条 eval artifact 同时包含 trace、dataset、sample 和 grader。"""
    trace_config = build_trace_config("TC001")
    artifact = build_eval_artifact(
        case={"id": "TC001", "expected_tool_calls": ["update_bullet"]},
        inputs={"case_id": "TC001", "user_message": "优化", "resume": {}, "jd": None},
        result={
            "agent_reply": "已完成。",
            "decision": "execute",
            "tool_calls": ["update_bullet"],
            "resume_after": {},
            "runtime_events": [],
        },
        trace_config=trace_config,
    )

    assert artifact["eval_name"] == OPENAI_AGENTS_EVAL_NAME
    assert artifact["trace"]["trace_id"] == trace_config.trace_id
    assert artifact["dataset_item"]["case_id"] == "TC001"
    assert artifact["model_sample"]["output_tools"][0]["function"]["name"] == "update_bullet"
    assert artifact["grader"]["type"] == "python"


def test_build_eval_run_summary_collects_trace_ids():
    """用于验证整次 eval summary 会收集所有可查 trace id。"""
    summary = build_eval_run_summary(
        [
            {
                "openai_agents_eval": {
                    "trace": {"trace_id": "trace_1234567890abcdef1234567890abcdef"}
                }
            }
        ]
    )

    assert summary["eval_name"] == OPENAI_AGENTS_EVAL_NAME
    assert summary["trace_ids"] == ["trace_1234567890abcdef1234567890abcdef"]
    assert summary["dataset_item_count"] == 1
