"""用于覆盖 Braintrust 项目级简历 scorer。"""

from braintrust_resume_scorers import (
    final_resume_score_scorer,
    hallucination_safety_scorer,
    jd_match_scorer,
    project,
    star_quality_scorer,
    uplift_score_scorer,
)


def test_star_quality_rewards_structured_quantified_bullet():
    """用于验证 STAR scorer 会奖励有动作、量化和结果的 bullet。"""
    result = star_quality_scorer(
        output="主导 FastAPI 接口优化，将 P99 响应从 2s 降至 200ms，支撑日均 500 万请求"
    )

    assert result["score"] >= 0.8


def test_uplift_score_compares_output_to_original():
    """用于验证 uplift scorer 会比较原文和优化结果。"""
    result = uplift_score_scorer(
        input={"original": "负责后端开发"},
        output="设计 FastAPI 服务治理方案，将接口错误率降低 40%",
    )

    assert result["score"] > 0.5
    assert result["metadata"]["missing_original"] is False


def test_jd_match_uses_job_description_keywords():
    """用于验证 JD scorer 能识别岗位关键词匹配。"""
    result = jd_match_scorer(
        input={"jd_text": "需要 Python FastAPI Agent 评测经验"},
        output="基于 Python 和 FastAPI 构建 Agent 评测服务",
    )

    assert result["score"] > 0
    assert "python" in result["metadata"]["matched_keywords"]


def test_jd_match_gracefully_handles_missing_jd():
    """用于验证缺失 JD 时 scorer 不报错并返回中性分。"""
    result = jd_match_scorer(output="主导接口优化，错误率降低 40%")

    assert result["score"] == 0.5
    assert result["metadata"]["missing_jd"] is True


def test_hallucination_safety_penalizes_unsupported_claims():
    """用于验证幻觉风险 scorer 会惩罚原文不支持的夸大信息。"""
    result = hallucination_safety_scorer(
        input={"original": "负责日常开发工作"},
        output="带领 50 人团队实现营收增长 300%，获得 CEO 特别嘉奖",
    )

    assert result["score"] < 1
    assert result["metadata"]["hallucination_count"] >= 2


def test_final_score_combines_core_dimensions():
    """用于验证总分 scorer 返回可解释的组件分。"""
    result = final_resume_score_scorer(
        input={
            "original": "负责后端开发",
            "jd_text": "Python FastAPI 后端性能优化",
        },
        output="设计 Python FastAPI 性能优化方案，将 P99 响应从 2s 降至 200ms",
    )

    assert result["name"] == "Resume final score"
    assert 0.0 <= result["score"] <= 1.0
    assert set(result["metadata"]) == {
        "star_quality",
        "uplift",
        "jd_match",
        "hallucination_safety",
    }


def test_project_registers_five_resume_scorers():
    """用于验证文件导入后会向 Braintrust 项目注册 5 个 scorer 定义。"""
    slugs = {fn.slug for fn in project._publishable_code_functions}

    assert slugs == {
        "resume-final-score",
        "resume-uplift-score",
        "resume-jd-match-score",
        "resume-star-quality-score",
        "resume-hallucination-safety",
    }
