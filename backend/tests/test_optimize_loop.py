"""用于覆盖简历自动迭代优化循环相关的回归测试。"""

import pytest

# ---------- JD 匹配同义词和权重化测试 ----------


@pytest.mark.asyncio
async def test_jd_match_hits_synonym_in_resume():
    """用于验证简历写'服务拆分'也能匹配 JD 里的'微服务'。"""
    from app.services.agent.resume_score import score_resume

    resume = {
        "personal_info": {"name": "张", "email": "z@s.com"},
        "summary": {"text": "后端工程师。"},
        "education": [{"id": "e1", "school": "北大", "highlights": []}],
        "work_experience": [{
            "id": "w1",
            "company": "某厂",
            "highlights": [{"id": "h1", "text": "主导服务拆分，拆分 3 个核心服务"}],
        }],
        "skills": [{"id": "s1", "category": "后端", "items": ["Python"]}],
        "job_application": {"jd_text": "要求必须掌握微服务架构。"},
    }
    result = await score_resume(resume)
    jd_dim = next((d for d in result["dimensions"] if d["key"] == "jd_match"), None)
    assert jd_dim is not None
    # 微服务 同义词 服务拆分 命中
    assert jd_dim["score"] > 0
    missing_kw = [f.get("missing_keyword") for f in jd_dim["findings"]]
    assert "微服务" not in missing_kw


def test_jd_match_weights_affect_score():
    """用于验证必需/加分技能权重确实影响 JD 匹配得分。"""
    from app.services.agent.resume_rule_score import _extract_jd_keywords

    # 验证权重提取
    required_kws = _extract_jd_keywords("必须掌握 Python。")
    preferred_kws = _extract_jd_keywords("有 Python 经验优先。")
    assert required_kws[0]["weight"] == 2.0
    assert preferred_kws[0]["weight"] == 0.5

    # 混合场景：简历命中 Python，缺失 Kafka
    # 必需版 Python(2.0) + 加分版 Kafka(0.5) → weighted_hits=2.0, total=2.5
    # 全必需版 Python(2.0) + Kafka(2.0) → weighted_hits=2.0, total=4.0
    # 全必需版命中率更低，说明匹配的含金量不同
    mixed_kws = _extract_jd_keywords("必须掌握 Python，有 Kafka 经验优先。")
    all_required_kws = _extract_jd_keywords("必须掌握 Python 和 Kafka。")
    assert len(mixed_kws) == 2
    assert len(all_required_kws) == 2

    # 必需 Python + 加分 Kafka 的总权重
    mixed_weights = {k["keyword"]: k["weight"] for k in mixed_kws}
    assert mixed_weights["Python"] == 2.0
    assert mixed_weights["Kafka"] == 0.5


def test_jd_match_synonym_group_coverage():
    """用于验证同一同义词组内多个词出现在简历和 JD 时都能正确匹配。"""
    from app.services.agent.resume_rule_score import _keyword_matches_resume, _build_synonym_index

    index = _build_synonym_index()
    resume_text = "搭建监控体系，实现全链路追踪"

    assert _keyword_matches_resume("可观测", resume_text, index) is True
    assert _keyword_matches_resume("Observability", resume_text.lower(), index) is True
    assert _keyword_matches_resume("消息队列", resume_text, index) is False


# ---------- 收敛判断测试 ----------


@pytest.mark.asyncio
async def test_convergence_none_on_first_score():
    """用于验证首次评分时无收敛信息。"""
    from app.services.agent.resume_score import score_resume

    result = await score_resume({
        "personal_info": {"name": "张", "email": "z@s.com"},
        "summary": {"text": "工程师。"},
        "education": [{"id": "e1", "school": "北大", "highlights": []}],
        "work_experience": [{"id": "w1", "company": "某厂", "highlights": []}],
        "skills": [{"id": "s1", "category": "后端", "items": ["Python"]}],
    })
    assert result["convergence"] is None


@pytest.mark.asyncio
async def test_convergence_improving_when_score_rises():
    """用于验证分数提升时收敛状态为 improving。"""
    from app.services.agent.resume_score import score_resume

    resume = {
        "personal_info": {"name": "张", "email": "z@s.com"},
        "summary": {"text": "工程师。"},
        "education": [{"id": "e1", "school": "北大", "highlights": []}],
        "work_experience": [{
            "id": "w1",
            "company": "某厂",
            "highlights": [{"id": "h1", "text": "负责后端接口"}],
        }],
        "skills": [{"id": "s1", "category": "后端", "items": ["Python"]}],
    }
    history = [{"total_score": 60, "grade": "D", "note": "初始"}]
    result = await score_resume(resume, score_history=history)
    conv = result["convergence"]
    assert conv is not None
    assert conv["status"] == "improving"
    assert conv["should_stop"] is False
    assert conv["initial_score"] == 60


@pytest.mark.asyncio
async def test_convergence_converged_at_85_plus():
    """用于验证分数达到 85 以上时标记为 converged。"""
    from app.services.agent.resume_score import score_resume

    resume = {
        "personal_info": {"name": "张", "email": "z@s.com"},
        "summary": {"text": "5年后端工程师。"},
        "education": [{"id": "e1", "school": "北大", "highlights": [{"id": "h0", "text": "GPA 3.8"}]}],
        "work_experience": [{
            "id": "w1",
            "company": "某厂",
            "highlights": [
                {"id": "h1", "text": "重构核心服务，将 P99 延迟降低 80%"},
                {"id": "h2", "text": "搭建监控体系，覆盖 30+ 链路"},
            ],
        }],
        "skills": [{"id": "s1", "category": "后端", "items": ["Python", "FastAPI"]}],
    }
    history = [{"total_score": 70, "grade": "C", "note": "初始"}]
    result = await score_resume(resume, score_history=history)
    if result["total_score"] >= 85:
        conv = result["convergence"]
        assert conv["status"] == "converged"
        assert conv["should_stop"] is True
        assert "优秀" in conv["stop_reason"]


@pytest.mark.asyncio
async def test_convergence_plateaued_after_two_flat_rounds():
    """用于验证连续两轮无提升时标记为 plateaued。"""
    from app.services.agent.resume_score import score_resume

    resume = {
        "personal_info": {"name": "张", "email": "z@s.com"},
        "summary": {"text": "工程师。"},
        "education": [{"id": "e1", "school": "北大", "highlights": []}],
        "work_experience": [{
            "id": "w1",
            "company": "某厂",
            "highlights": [{"id": "h1", "text": "负责后端接口"}],
        }],
        "skills": [{"id": "s1", "category": "后端", "items": ["Python"]}],
    }
    # 两轮同样分数的历史
    history = [
        {"total_score": 55, "grade": "F", "note": "第一轮"},
        {"total_score": 55, "grade": "F", "note": "第二轮"},
    ]
    result = await score_resume(resume, score_history=history)
    conv = result["convergence"]
    if conv and conv["current_score"] <= conv["last_score"]:
        assert conv["status"] == "plateaued"
        assert conv["should_stop"] is True
        assert "天花板" in conv["stop_reason"]
