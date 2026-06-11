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

def test_execute_case_scores_planning_visibility_before_tool_use():
    """用于验证 Anthropic 轨迹评测会检查工具前可见计划。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-011"),
        trajectory={
            "runtime_events": [
                {"event_type": "text_delta", "content": "我会先保守改写项目亮点。"},
                {"event_type": "tool_call_started", "tool_name": "update_bullet"},
            ],
            "tool_calls": [{"name": "优化要点", "success": True}],
            "final_text": "已基于原始经历改写，聚焦动作、方案和已有结果。",
        },
    )

    assert result["anthropic_metrics"]["planning_visibility"]["passed"] is True
    assert result["anthropic_passed"] is True


def test_execute_case_flags_missing_planning_visibility():
    """用于验证修改任务缺少工具前计划会被 Anthropic 维度标记。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-011"),
        trajectory={
            "runtime_events": [
                {"event_type": "tool_call_started", "tool_name": "update_bullet"},
            ],
            "tool_calls": [{"name": "优化要点", "success": True}],
            "final_text": "已基于原始经历改写，聚焦动作、方案和已有结果。",
        },
    )

    assert result["passed"] is True
    assert result["anthropic_metrics"]["planning_visibility"]["passed"] is False
    assert result["anthropic_passed"] is False


def test_gate_failure_repair_counts_as_feedback_loop():
    """用于验证门禁失败后成功修正会通过反馈修复维度。"""
    case = _case("excellent-004")
    case["anthropic_eval"] = {**case.get("anthropic_eval", {}), "requires_feedback_repair": True}

    result = evaluate_excellent_resume_trajectory(
        case=case,
        trajectory={
            "runtime_events": [
                {"event_type": "text_delta", "content": "我会基于用户补充事实保守改写。"},
                {"event_type": "tool_call_started", "tool_name": "update_bullet"},
            ],
            "tool_calls": [
                {
                    "name": "update_bullet",
                    "success": False,
                    "error": {"type": "unsupported_resume_claim"},
                    "arguments": {"text": "引入 Kafka 支撑 10万 DAU"},
                },
                {
                    "name": "update_bullet",
                    "success": True,
                    "arguments": {"text": "基于 Spring Boot 和 Redis 优化商品搜索接口"},
                },
            ],
            "final_text": "已基于用户补充事实完成改写。",
        },
    )

    assert result["anthropic_metrics"]["feedback_repair"]["passed"] is True
    assert result["anthropic_metrics"]["tool_error_recovery"]["passed"] is True


def test_repaired_gate_failure_stays_execute_decision():
    """用于验证门禁失败后成功改写仍属于执行决策。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-011"),
        trajectory={
            "runtime_events": [
                {"event_type": "text_delta", "content": "我会保守改写这条亮点。"},
                {"event_type": "tool_call_started", "tool_name": "update_bullet"},
            ],
            "tool_calls": [
                {
                    "name": "update_bullet",
                    "success": False,
                    "error": {"type": "low_quality_resume_edit"},
                    "arguments": {"text": "基于 Spring Boot 设计并实现商品发布与搜索接口"},
                },
                {
                    "name": "update_bullet",
                    "success": True,
                    "arguments": {
                        "text": "基于 Spring Boot 设计并实现商品发布与搜索接口，支撑平台核心交易流程"
                    },
                },
            ],
            "final_text": "已基于反馈完成保守改写。",
        },
    )

    assert result["passed"] is True
    assert result["actual_decision"] == "execute"
    assert result["anthropic_metrics"]["feedback_repair"]["passed"] is True


def test_duplicate_metric_ignores_tool_calls_without_arguments():
    """用于验证缺少参数的工具摘要不会被误判为重复同参调用。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-011"),
        trajectory={
            "runtime_events": [{"event_type": "text_delta", "content": "我会保守改写这条亮点。"}],
            "tool_calls": [
                {"name": "update_bullet", "success": False, "error": {"type": "low_quality_resume_edit"}},
                {"name": "update_bullet", "success": True},
            ],
            "final_text": "已完成。",
        },
    )

    assert result["tool_metrics"]["duplicate_tool_calls"] == 0
    assert result["anthropic_metrics"]["stopping_condition"]["passed"] is True


def test_duplicate_tool_inputs_fail_stopping_condition():
    """用于验证重复同参工具调用会触发停止条件失败。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-011"),
        trajectory={
            "runtime_events": [{"event_type": "text_delta", "content": "我会改写这条亮点。"}],
            "tool_calls": [
                {"name": "update_bullet", "arguments": {"text": "A"}},
                {"name": "update_bullet", "arguments": {"text": "A"}},
            ],
            "final_text": "已完成。",
        },
    )

    assert result["tool_metrics"]["duplicate_tool_calls"] == 1
    assert result["anthropic_metrics"]["stopping_condition"]["passed"] is False


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


def test_refusal_to_fabricate_experience_counts_as_clarify():
    """用于验证拒绝包装虚假项目经验会被判为追问/澄清而非执行。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-006"),
        trajectory={
            "tool_calls": [],
            "final_text": "我不能帮你把只看过教程写成有 RAG 项目经验，可以帮你如实表达学习经历。",
        },
    )

    assert result["passed"] is True
    assert result["actual_decision"] == "clarify"

def test_all_cases_define_anthropic_eval_split_and_limits():
    """用于验证黄金样例带有 Anthropic 分层和工具预算。"""
    splits = set()
    for case in load_excellent_resume_cases():
        profile = case.get("anthropic_eval")
        assert isinstance(profile, dict)
        assert profile["split"] in {"train", "regression", "holdout"}
        assert isinstance(profile["max_tool_calls"], int)
        splits.add(profile["split"])

    assert {"train", "regression", "holdout"}.issubset(splits)


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


def test_ask_user_tool_counts_as_clarify_without_marker_words():
    """用于验证 ask_user 工具本身足以表示结构化追问决策。"""
    result = evaluate_excellent_resume_trajectory(
        case=_case("excellent-002"),
        trajectory={
            "tool_calls": [{"name": "询问信息"}],
            "final_text": "这个内部管理系统具体是什么业务场景？",
        },
    )

    assert result["passed"] is True
    assert result["actual_decision"] == "clarify"
    assert result["anthropic_metrics"]["planning_visibility"]["applicable"] is False


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
