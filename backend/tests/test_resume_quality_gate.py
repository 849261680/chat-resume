"""用于覆盖简历 Agent 修改质量门禁。"""

from app.agents.resume.quality_gate import evaluate_resume_edit_quality


def _resume_with_basic_project() -> dict:
    """用于构造缺少量化和中间件事实的原始简历。"""
    return {
        "projects": [
            {
                "id": "p1",
                "name": "校园二手交易平台",
                "highlights": [
                    {"id": "b1", "text": "用 Spring Boot 写了商品发布和搜索接口"}
                ],
            }
        ],
        "skills": [{"id": "s1", "category": "后端", "items": ["Spring Boot", "MySQL"]}],
    }


def test_quality_gate_blocks_unsupported_numbers_and_technologies():
    """用于验证新增无来源数字和技术栈时阻止 diff 进入用户确认。"""
    result = {
        "success": True,
        "diff_items": [
            {
                "before": '{"id":"b1","text":"用 Spring Boot 写了商品发布和搜索接口"}',
                "after": '{"id":"b1","text":"引入 Redis 与 Kafka 优化搜索链路，支撑 10万 DAU 并将延迟降低 70%"}',
                "reason": "贴合后端 JD",
            }
        ],
    }

    gate = evaluate_resume_edit_quality(
        resume_content=_resume_with_basic_project(),
        tool_name="update_bullet",
        tool_input={"text": "引入 Redis 与 Kafka 优化搜索链路，支撑 10万 DAU 并将延迟降低 70%"},
        preview_result=result,
        user_message="帮我优化这个项目经历",
    )

    assert gate["passed"] is False
    assert gate["error_type"] == "unsupported_resume_claim"
    assert "Redis" in gate["message"]
    assert "10万" in gate["message"]
    assert gate["recoverable"] is True


def test_quality_gate_allows_facts_present_in_user_message():
    """用于验证用户刚提供的事实可作为本轮改写来源。"""
    result = {
        "success": True,
        "diff_items": [
            {
                "before": '{"id":"b1","text":"用 Spring Boot 写了商品发布和搜索接口"}',
                "after": '{"id":"b1","text":"基于 Spring Boot 和 Redis 优化商品搜索链路，将平均查询延迟降低 40%"}',
                "reason": "使用用户补充事实改写",
            }
        ],
    }

    gate = evaluate_resume_edit_quality(
        resume_content=_resume_with_basic_project(),
        tool_name="update_bullet",
        tool_input={"text": "基于 Spring Boot 和 Redis 优化商品搜索链路，将平均查询延迟降低 40%"},
        preview_result=result,
        user_message="我实际用过 Redis，搜索延迟从 500ms 降到 300ms，大约降低 40%",
    )

    assert gate["passed"] is True


def test_quality_gate_blocks_keyword_stuffing_without_improvement():
    """用于验证只堆 JD 关键词但没有优秀度提升时会被拦截。"""
    result = {
        "success": True,
        "diff_items": [
            {
                "before": '{"id":"b1","text":"用 Spring Boot 写了商品发布和搜索接口"}',
                "after": '{"id":"b1","text":"负责 Spring Boot、MySQL、后端、接口、数据库优化相关工作"}',
                "reason": "覆盖 JD 关键词",
            }
        ],
    }

    gate = evaluate_resume_edit_quality(
        resume_content=_resume_with_basic_project(),
        tool_name="update_bullet",
        tool_input={"text": "负责 Spring Boot、MySQL、后端、接口、数据库优化相关工作"},
        preview_result=result,
        user_message="帮我改得更贴后端 JD",
    )

    assert gate["passed"] is False
    assert gate["error_type"] == "low_quality_resume_edit"
    assert "堆关键词" in gate["message"]
    assert "具体" in gate["message"]
