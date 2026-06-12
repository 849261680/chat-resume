"""用于覆盖简历评分服务的确定性回归测试。"""

import pytest

from app.services.agent.resume_score import score_resume


def _full_resume() -> dict:
    """用于构造一份字段齐全、含量化结果的简历。"""
    return {
        "personal_info": {"name": "张三", "email": "z@s.com", "phone": "13800000000"},
        "summary": {"text": "5 年后端工程师，擅长高并发系统设计与性能优化。"},
        "education": [
            {"id": "edu1", "school": "北京大学", "highlights": [{"id": "h0", "text": "主修计算机科学，GPA 3.8"}]}
        ],
        "work_experience": [
            {
                "id": "work1",
                "company": "某科技",
                "highlights": [
                    {"id": "h1", "text": "重构核心服务，将接口 P99 延迟从 800ms 降到 120ms"},
                    {"id": "h2", "text": "搭建监控体系，覆盖 30+ 关键链路，故障定位时间缩短 60%"},
                ],
            }
        ],
        "projects": [
            {"id": "proj1", "name": "增长平台", "highlights": [{"id": "h3", "text": "设计实时分析管线，支撑日均 1000万 事件"}]}
        ],
        "skills": [{"id": "sk1", "category": "后端", "items": ["Python", "FastAPI", "Redis"]}],
        "job_application": {"jd_text": "要求 Python、FastAPI、高并发 与 Redis 经验。"},
    }


@pytest.mark.asyncio
async def test_full_resume_scores_high_with_all_dimensions():
    """用于验证齐全且量化的简历能拿到高分并覆盖四个维度。"""
    result = await score_resume(_full_resume())

    assert result["success"] is True
    assert result["total_score"] >= 85
    assert result["grade"] in {"A", "B"}
    keys = {dim["key"] for dim in result["dimensions"]}
    assert keys == {"completeness", "quantification", "expression", "jd_match"}


@pytest.mark.asyncio
async def test_unquantified_bullet_produces_actionable_finding():
    """用于验证缺少量化的 bullet 会生成带 item_id/bullet_id 的修改建议。"""
    resume = {
        "personal_info": {"name": "李四", "email": "l@s.com"},
        "summary": {"text": "前端工程师。"},
        "education": [{"id": "edu1", "school": "清华", "highlights": [{"id": "h0", "text": "计算机本科毕业生"}]}],
        "work_experience": [
            {"id": "work1", "company": "某厂", "highlights": [{"id": "h1", "text": "负责维护前端页面和组件库"}]}
        ],
        "skills": [{"id": "sk1", "category": "前端", "items": ["React"]}],
    }

    result = await score_resume(resume)
    quant = next(dim for dim in result["dimensions"] if dim["key"] == "quantification")
    finding = next(f for f in quant["findings"] if f["item_id"] == "work1")

    assert finding["bullet_id"] == "h1"
    assert "量化" in finding["suggestion"]


@pytest.mark.asyncio
async def test_score_payload_prioritizes_evidence_backed_agent_actions():
    """用于验证评分结果给出证据、优先风险和下一步工具动作。"""
    resume = {
        "personal_info": {"name": "李四", "email": "l@s.com"},
        "summary": {"text": "前端工程师。"},
        "education": [{"id": "edu1", "school": "清华", "highlights": [{"id": "h0", "text": "计算机本科毕业生"}]}],
        "work_experience": [
            {"id": "work1", "company": "某厂", "highlights": [{"id": "h1", "text": "负责维护前端页面和组件库"}]}
        ],
        "skills": [{"id": "sk1", "category": "前端", "items": ["React"]}],
        "job_application": {"jd_text": "要求 React、性能优化、TypeScript 经验。"},
    }

    result = await score_resume(resume)
    action = result["priority_actions"][0]

    assert result["diagnosis"]["primary_risk"]["dimension_key"] in {
        "quantification",
        "jd_match",
        "expression",
        "impact_clarity",
        "responsibility_depth",
    }
    assert result["diagnosis"]["evidence"]
    assert action["tool_hint"] == "update_bullet"
    assert action["target"] == {"item_id": "work1", "bullet_id": "h1"}
    assert "重新评估简历" in result["agent_next_step"]


@pytest.mark.asyncio
async def test_no_jd_drops_jd_dimension_and_renormalizes():
    """用于验证无 JD 时不计入 JD 维度，且权重归一到 100。"""
    resume = _full_resume()
    resume.pop("job_application")

    result = await score_resume(resume)
    keys = {dim["key"] for dim in result["dimensions"]}

    assert "jd_match" not in keys
    assert sum(dim["max"] for dim in result["dimensions"]) == 100


@pytest.mark.asyncio
async def test_missing_jd_keyword_listed_in_findings():
    """用于验证 JD 中未命中的关键词进入可执行建议。"""
    resume = _full_resume()
    resume["job_application"]["jd_text"] = "要求 Python、Kafka 与 Kubernetes 经验。"

    result = await score_resume(resume)
    jd = next(dim for dim in result["dimensions"] if dim["key"] == "jd_match")
    missing = {finding["missing_keyword"] for finding in jd["findings"]}

    assert "Kafka" in missing
    assert "Kubernetes" in missing




@pytest.mark.asyncio
async def test_score_resume_returns_rule_and_semantic_layers():
    """用于验证单一评分工具同时返回规则层和语义评审层。"""
    resume = _full_resume()
    resume["work_experience"][0]["highlights"][0]["text"] = "负责后端接口开发"

    result = await score_resume(resume)

    assert result["rule_checks"]["score"] >= 0
    assert result["semantic_review"]["status"] == "available"
    assert result["semantic_review"]["overall"]["score"] >= 0
    assert {item["key"] for item in result["semantic_review"]["dimensions"]} == {
        "role_fit",
        "project_persuasiveness",
        "responsibility_depth",
        "impact_clarity",
        "interview_readiness",
    }
    assert any(action["source"] == "semantic_review" for action in result["priority_actions"])


@pytest.mark.asyncio
async def test_score_resume_falls_back_when_semantic_review_fails():
    """用于验证语义评审异常时评分工具仍返回规则评分。"""
    def broken_reviewer(_resume: dict, _dimensions: list[dict]) -> dict:
        """用于模拟语义评审 provider 或解析失败。"""
        raise ValueError("bad semantic json")

    result = await score_resume(
        _full_resume(),
        fallback_semantic_reviewer=broken_reviewer,
    )

    assert result["semantic_review"]["status"] == "unavailable"
    assert result["semantic_review"]["reason"] == "bad semantic json"
    assert result["total_score"] == result["rule_checks"]["score"]


@pytest.mark.asyncio
async def test_score_resume_uses_llm_reviewer_when_provided():
    """用于验证传入 LLM 语义评审时优先使用 LLM 结果。"""
    async def mock_llm_reviewer(_resume: dict, _dimensions: list[dict]) -> dict:
        """用于模拟 LLM 语义评审成功返回。"""
        return {
            "status": "available",
            "method": "llm_semantic_review",
            "overall": {"score": 88, "level": "strong", "reason": "测试用"},
            "dimensions": [
                {"key": "role_fit", "score": 90, "evidence": "贴合", "risk": "low", "suggestion": "好"},
                {"key": "project_persuasiveness", "score": 85, "evidence": "有说服力", "risk": "low", "suggestion": "好"},
                {"key": "responsibility_depth", "score": 88, "evidence": "深度好", "risk": "low", "suggestion": "好"},
                {"key": "impact_clarity", "score": 90, "evidence": "清晰", "risk": "low", "suggestion": "好"},
                {"key": "interview_readiness", "score": 87, "evidence": "准备好了", "risk": "low", "suggestion": "好"},
            ],
            "selling_points": ["测试卖点"],
            "weak_signals": [],
            "interview_risks": [],
            "priority_actions": [],
        }

    result = await score_resume(
        _full_resume(),
        async_semantic_reviewer=mock_llm_reviewer,
    )

    assert result["semantic_review"]["method"] == "llm_semantic_review"
    assert result["semantic_review"]["overall"]["score"] == 88


@pytest.mark.asyncio
async def test_score_resume_falls_back_to_heuristic_when_llm_fails():
    """用于验证 LLM 语义评审失败时降级到本地启发式。"""

    async def broken_llm_reviewer(_resume: dict, _dimensions: list[dict]) -> dict:
        """用于模拟 LLM 语义评审失败。"""
        raise ValueError("LLM service unavailable")

    result = await score_resume(
        _full_resume(),
        async_semantic_reviewer=broken_llm_reviewer,
    )

    # 应该降级到本地启发式，仍然成功
    assert result["semantic_review"]["status"] == "available"
    assert result["semantic_review"]["method"] == "local_semantic_heuristic"
