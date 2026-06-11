"""用于验证优秀简历 Agent 的轨迹评测入口。"""

from app.agents.resume.excellent_cases import load_excellent_resume_cases
from app.agents.resume.excellent_trajectory import (
    evaluate_excellent_resume_trajectory,
)


def _case(case_id: str) -> dict:
    """用于按样例 ID 读取黄金样例。"""
    return next(item for item in load_excellent_resume_cases() if item["id"] == case_id)


def test_execute_case_requires_expected_tool_call():
    """用于验证执行型样例必须调用期望的简历编辑工具。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-011"),
        trajectory={
            "tool_calls": [{"name": "优化要点", "success": True}],
            "final_text": "已基于原始经历改写，聚焦动作、方案和已有结果。",
        },
    )

    assert result["passed"] is True
    assert result["actual_decision"] == "execute"
    assert result["actual_tool_calls"] == ["update_bullet"]


def test_jd_case_with_missing_evidence_requires_ask_user():
    """用于验证 JD 关键能力缺证据时应先用 ask_user 追问。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-001"),
        trajectory={
            "tool_calls": [{"name": "询问信息"}],
            "final_text": "是否真实做过数据库优化或稳定性建设？如果有，请补充具体做法和结果。",
        },
    )

    assert result["passed"] is True
    assert result["actual_decision"] == "clarify"
    assert result["actual_tool_calls"] == ["ask_user"]


def test_clarify_case_passes_when_agent_asks_for_missing_facts():
    """用于验证信息不足时追问而不是编造成果。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-002"),
        trajectory={
            "tool_calls": [],
            "final_text": "这里缺少可量化结果，请补充转化率、用户规模或性能指标后我再改写。",
        },
    )

    assert result["passed"] is True
    assert result["actual_decision"] == "clarify"


def test_ask_user_tool_counts_as_clarify_not_execute():
    """用于验证结构化追问工具不会被误判为执行改写。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-003"),
        trajectory={
            "tool_calls": [{"name": "询问信息"}],
            "final_text": "是否真实使用过 Redis 或 Kafka？如果有，请说明具体场景。",
        },
    )

    assert result["passed"] is True
    assert result["actual_decision"] == "clarify"
    assert result["actual_tool_calls"] == ["ask_user"]


def test_gate_failure_case_counts_as_clarify_trajectory():
    """用于验证事实门禁失败后回到追问也算正确轨迹。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-003"),
        trajectory={
            "tool_calls": [
                {
                    "name": "update_bullet",
                    "success": False,
                    "error": {"type": "unsupported_resume_claim"},
                }
            ],
            "final_text": "这次会引入原简历没有的 Redis 和 Kafka，请确认是否真实使用过。",
        },
    )

    assert result["passed"] is True
    assert result["actual_decision"] == "clarify"
    assert result["gate_failure"] is True


def test_runtime_event_gate_failure_counts_as_clarify_trajectory():
    """用于验证运行时门禁失败事件能把先失败后追问判为追问轨迹。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-001"),
        trajectory={
            "tool_calls": [{"name": "优化要点"}, {"name": "询问信息"}],
            "runtime_events": [
                {
                    "tool_call_failed": True,
                    "result": {"error": {"type": "unsupported_resume_claim"}},
                }
            ],
            "final_text": "商品搜索接口有没有做过数据库索引优化？",
        },
    )

    assert result["passed"] is True
    assert result["actual_decision"] == "clarify"
    assert result["gate_failure"] is True


def test_execute_case_fails_on_missing_tool_call_or_forbidden_claim():
    """用于验证缺少工具调用或输出禁用事实会失败。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-004"),
        trajectory={
            "tool_calls": [],
            "final_text": "已改成支撑 10万 DAU 的高并发系统。",
        },
    )

    assert result["passed"] is False
    assert "missing_expected_tool_calls" in result["failure_codes"]
    assert "forbidden_claims_present" in result["failure_codes"]


def test_all_cases_have_evaluable_trajectory_expectations():
    """用于验证每个黄金样例都能被轨迹评测器消费。"""
    for case in load_excellent_resume_cases():
        result = evaluate_excellent_resume_trajectory(
            case=case,
            trajectory={"tool_calls": [], "final_text": "请补充更多真实事实后我再改写。"},
        )

        assert result["actual_decision"] in {"execute", "clarify"}
        assert isinstance(result["passed"], bool)
        assert isinstance(result["failure_codes"], list)
