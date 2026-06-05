"""用于覆盖简历评分工具的确定性回归测试。"""

from app.services.agent.resume_score import score_resume
from app.tools.resume.score_resume_tool import score_resume_tool


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


def test_full_resume_scores_high_with_all_dimensions():
    """用于验证齐全且量化的简历能拿到高分并覆盖四个维度。"""
    result = score_resume(_full_resume())

    assert result["success"] is True
    assert result["total_score"] >= 85
    assert result["grade"] in {"A", "B"}
    keys = {dim["key"] for dim in result["dimensions"]}
    assert keys == {"completeness", "quantification", "expression", "jd_match"}


def test_unquantified_bullet_produces_actionable_finding():
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

    result = score_resume(resume)
    quant = next(dim for dim in result["dimensions"] if dim["key"] == "quantification")
    finding = next(f for f in quant["findings"] if f["item_id"] == "work1")

    assert finding["bullet_id"] == "h1"
    assert "量化" in finding["suggestion"]


def test_no_jd_drops_jd_dimension_and_renormalizes():
    """用于验证无 JD 时不计入 JD 维度，且权重归一到 100。"""
    resume = _full_resume()
    resume.pop("job_application")

    result = score_resume(resume)
    keys = {dim["key"] for dim in result["dimensions"]}

    assert "jd_match" not in keys
    assert sum(dim["max"] for dim in result["dimensions"]) == 100


def test_missing_jd_keyword_listed_in_findings():
    """用于验证 JD 中未命中的关键词进入可执行建议。"""
    resume = _full_resume()
    resume["job_application"]["jd_text"] = "要求 Python、Kafka 与 Kubernetes 经验。"

    result = score_resume(resume)
    jd = next(dim for dim in result["dimensions"] if dim["key"] == "jd_match")
    missing = {finding["missing_keyword"] for finding in jd["findings"]}

    assert "Kafka" in missing
    assert "Kubernetes" in missing


def test_tool_wrapper_returns_score_payload():
    """用于验证工具封装返回标准评分结果结构。"""
    result = score_resume_tool(_full_resume())

    assert result["success"] is True
    assert "total_score" in result
    assert isinstance(result["top_suggestions"], list)
