"""用于覆盖优秀简历 Agent 黄金样例集。"""

from app.agents.resume.excellent_cases import load_excellent_resume_cases
from app.agents.resume.quality_gate import evaluate_resume_edit_quality


def test_excellent_resume_cases_cover_required_scenarios():
    """用于验证黄金样例集覆盖优秀简历闭环的核心场景。"""
    cases = load_excellent_resume_cases()
    categories = {case["category"] for case in cases}

    assert len(cases) >= 10
    assert len({case["id"] for case in cases}) == len(cases)
    assert {
        "rewrite_weak_bullet",
        "clarify_missing_facts",
        "jd_keyword_without_evidence",
        "user_fact_supported_rewrite",
        "concise_rewrite",
    } <= categories


def test_excellent_resume_cases_have_actionable_acceptance_fields():
    """用于验证每个黄金样例都能被自动评测消费。"""
    cases = load_excellent_resume_cases()

    for case in cases:
        assert case["id"].startswith("excellent-")
        assert case["user_message"].strip()
        assert isinstance(case["resume"], dict)
        assert case["expected_behavior"]["decision"] in {"execute", "clarify"}
        assert isinstance(case["expected_behavior"]["expected_tool_calls"], list)
        assert isinstance(case["quality_checks"], list)
        assert isinstance(case["forbidden_claims"], list)
        assert case["acceptance"].strip()


def test_missing_fact_case_is_blocked_by_quality_gate():
    """用于验证 JD 技术栈无事实支撑时会被事实门禁拦截。"""
    case = next(
        item for item in load_excellent_resume_cases()
        if item["id"] == "excellent-003"
    )
    candidate = case["candidate_bad_diff"]

    gate = evaluate_resume_edit_quality(
        resume_content=case["resume"],
        tool_name=candidate["tool_name"],
        tool_input=candidate["tool_input"],
        preview_result=candidate["preview_result"],
        user_message=case["user_message"],
    )

    assert gate["passed"] is False
    assert set(candidate["must_block_claims"]) <= set(gate["unsupported_claims"])


def test_user_fact_supported_case_passes_quality_gate():
    """用于验证用户已补充事实时同类改写允许进入确认。"""
    case = next(
        item for item in load_excellent_resume_cases()
        if item["id"] == "excellent-004"
    )
    candidate = case["candidate_good_diff"]

    gate = evaluate_resume_edit_quality(
        resume_content=case["resume"],
        tool_name=candidate["tool_name"],
        tool_input=candidate["tool_input"],
        preview_result=candidate["preview_result"],
        user_message=case["user_message"],
    )

    assert gate["passed"] is True

