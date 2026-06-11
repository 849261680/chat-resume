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

def test_quality_gate_allows_same_numbers_with_spacing_changes():
    """用于验证数字和单位间空白变化不会被误判为编造。"""
    result = {
        "success": True,
        "diff_items": [
            {
                "before": '{"id":"b1","text":"页面加载时间从 3 秒缩短到 1.2 秒"}',
                "after": '{"id":"b1","text":"优化前端页面加载链路，将加载时间从 3秒缩短至 1.2秒"}',
                "reason": "精简表达",
            }
        ],
    }

    gate = evaluate_resume_edit_quality(
        resume_content={
            "work_experience": [
                {"highlights": [{"text": "页面加载时间从 3 秒缩短到 1.2 秒"}]}
            ]
        },
        tool_name="update_bullet",
        tool_input={"text": "优化前端页面加载链路，将加载时间从 3秒缩短至 1.2秒"},
        preview_result=result,
        user_message="这条太长了，帮我精简，但别删掉关键结果。",
    )

    assert gate["passed"] is True


def test_quality_gate_allows_stability_claim_when_monitoring_fact_exists():
    """用于验证监控和故障定位事实可以支撑稳定性表达。"""
    result = {
        "success": True,
        "diff_items": [
            {
                "before": '{"id":"b1","text":"开发订单查询接口"}',
                "after": '{"id":"b2","text":"搭建 Prometheus 监控体系，覆盖 20 个核心接口，提升系统稳定性并将故障定位时间从 30 分钟缩短至 10 分钟"}',
                "reason": "补充用户提供的监控事实",
            }
        ],
    }

    gate = evaluate_resume_edit_quality(
        resume_content=_resume_with_basic_project(),
        tool_name="add_bullet",
        tool_input={
            "text": "搭建 Prometheus 监控体系，覆盖 20 个核心接口，提升系统稳定性并将故障定位时间从 30 分钟缩短至 10 分钟"
        },
        preview_result=result,
        user_message="我还搭过 Prometheus 监控，覆盖了 20 个接口，故障定位从 30 分钟降到 10 分钟",
    )

    assert gate["passed"] is True





def test_quality_gate_does_not_treat_embedded_jd_as_fact_source():
    """用于验证用户消息里的 JD 不能支撑新能力事实。"""
    result = {
        "success": True,
        "diff_items": [
            {
                "before": '{"id":"b1","text":"用 Spring Boot 写了商品发布和搜索接口"}',
                "after": '{"id":"b1","text":"基于 Spring Boot 设计并实现商品发布与搜索 RESTful 接口，结合 MySQL 完成商品表结构设计与索引优化，保障核心查询链路稳定高效"}',
                "reason": "贴合后端 JD",
            }
        ],
    }

    gate = evaluate_resume_edit_quality(
        resume_content=_resume_with_basic_project(),
        tool_name="update_bullet",
        tool_input={
            "text": "基于 Spring Boot 设计并实现商品发布与搜索 RESTful 接口，结合 MySQL 完成商品表结构设计与索引优化，保障核心查询链路稳定高效"
        },
        preview_result=result,
        user_message=(
            "帮我优化成适合投后端岗位的项目亮点。\n\n"
            "【目标岗位JD】负责接口设计、数据库优化和稳定性建设经验。"
        ),
    )

    assert gate["passed"] is False
    assert gate["error_type"] == "unsupported_resume_claim"
    assert {"索引优化", "稳定"} <= set(gate["unsupported_claims"])

def test_quality_gate_does_not_treat_job_application_jd_as_fact_source():
    """用于验证简历投递元数据里的 JD 不能支撑新能力事实。"""
    resume = _resume_with_basic_project()
    resume["job_application"] = {
        "jd_text": "负责接口设计、数据库优化和稳定性建设经验。"
    }
    result = {
        "success": True,
        "diff_items": [
            {
                "before": '{"id":"b1","text":"用 Spring Boot 写了商品发布和搜索接口"}',
                "after": '{"id":"b1","text":"基于 Spring Boot 设计商品发布接口，保障核心查询链路稳定高效"}',
                "reason": "贴合后端 JD",
            }
        ],
    }

    gate = evaluate_resume_edit_quality(
        resume_content=resume,
        tool_name="update_bullet",
        tool_input={"text": "基于 Spring Boot 设计商品发布接口，保障核心查询链路稳定高效"},
        preview_result=result,
        user_message="帮我优化成适合投后端岗位的项目亮点。",
    )

    assert gate["passed"] is False
    assert "稳定" in gate["unsupported_claims"]

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

    assert gate["error_type"] == "unsupported_resume_claim"
    assert "数据库优化" in gate["message"]
    assert gate["recoverable"] is True
