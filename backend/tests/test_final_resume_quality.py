"""用于覆盖最终简历质量评分器。"""

from copy import deepcopy

from app.agents.resume.excellent_cases import load_excellent_resume_cases
from app.agents.resume.final_resume_quality import score_final_resume_quality


def test_weak_resume_does_not_pass_top_resume_quality_gate():
    """用于验证泛泛职责型简历不能被判为顶级简历。"""
    resume = {
        "projects": [
            {
                "name": "管理系统",
                "overview": "做了一个后台系统",
                "highlights": [
                    {"text": "负责开发页面"},
                    {"text": "参与接口联调"},
                ],
                "tech_stack": ["Vue"],
            }
        ]
    }

    result = score_final_resume_quality(
        resume_before=resume,
        resume_after=resume,
        jd_text="要求熟悉后端接口、性能优化和数据库设计。",
    )

    assert result["passed"] is False
    assert result["score"] < 85
    assert "insufficient_star" in result["failure_codes"]


def test_evidence_backed_resume_passes_top_resume_quality_gate():
    """用于验证有事实、有结果、有岗位匹配的简历能通过顶级质量门槛。"""
    before = {
        "projects": [
            {
                "name": "简历优化 Agent",
                "overview": "AI 简历优化工具",
                "highlights": [
                    {"text": "实现简历优化功能"},
                    {"text": "支持用户确认后修改"},
                    {"text": "已有 39 条 Agent eval 用例和 SSE 回放能力"},
                ],
                "tech_stack": ["FastAPI", "React", "PostgreSQL"],
            }
        ]
    }
    after = {
        "projects": [
            {
                "name": "简历优化 Agent",
                "overview": "面向求职场景的 ReAct 简历优化 Agent，串联 JD 分析、结构化 diff、人工确认和导出链路。",
                "highlights": [
                    {
                        "text": "构建 ReAct 简历优化 Agent，基于 FastAPI、React 和 PostgreSQL 串联 JD 差距分析、结构化 diff 与人工确认链路，支撑用户在投递前定位岗位匹配短板"
                    },
                    {
                        "text": "设计 39 条 Agent eval 回归用例，覆盖工具调用、事实边界、关键词命中和 optimize-first 决策规则，持续拦截不安全改写"
                    },
                    {
                        "text": "落地确认后写入机制和 SSE 回放，修复刷新后状态丢失问题，保障简历修改可追踪、可撤销、可复核"
                    },
                ],
                "tech_stack": ["FastAPI", "React", "PostgreSQL"],
            }
        ]
    }

    result = score_final_resume_quality(
        resume_before=before,
        resume_after=after,
        jd_text="负责 AI Agent Runtime、工具调用、评测体系和前后端工程化建设。",
    )

    assert result["passed"] is True
    assert result["score"] >= 85
    assert result["dimensions"]["interview_readiness"]["passed"] is True


def test_unsupported_claims_prevent_top_resume_pass():
    """用于验证无来源技术栈和数字会阻断顶级简历判定。"""
    before = {
        "projects": [
            {
                "name": "后台系统",
                "highlights": [{"text": "开发后台页面"}],
                "tech_stack": ["Vue"],
            }
        ]
    }
    after = {
        "projects": [
            {
                "name": "后台系统",
                "highlights": [
                    {
                        "text": "基于 Kafka 和 Redis 重构后台链路，将接口延迟降低 70%，支撑 10 万 DAU"
                    }
                ],
                "tech_stack": ["Vue", "Kafka", "Redis"],
            }
        ]
    }

    result = score_final_resume_quality(
        resume_before=before,
        resume_after=after,
        jd_text="要求熟悉高并发系统。",
    )

    assert result["passed"] is False
    assert "unsupported_claims" in result["failure_codes"]
    assert {"Kafka", "Redis", "70%", "10 万"} <= set(result["fact_check"]["unsupported_claims"])


def test_single_strong_bullet_can_pass_bullet_scoped_quality_gate():
    """用于验证单条改写样例不要求至少两条强 bullet。"""
    before = {
        "work_experience": [
            {
                "highlights": [
                    {"text": "参与并负责多个后台页面的重构工作，最终让页面加载时间从 3 秒缩短到 1.2 秒"}
                ]
            }
        ],
        "job_application": {"target_title": "优秀简历 Agent 黄金样例"},
    }
    after = {
        "work_experience": [
            {
                "highlights": [
                    {"text": "以工程化方式重构多个前端后台页面，优化表单、列表和权限逻辑，将页面加载时间从 3 秒缩短至 1.2 秒"}
                ]
            }
        ],
        "job_application": {"target_title": "优秀简历 Agent 黄金样例"},
    }

    result = score_final_resume_quality(
        resume_before=before,
        resume_after=after,
        jd_text="需要表达清晰、重点突出的前端工程化经验。",
    )

    assert result["passed"] is True
    assert "Agent" not in result["fact_check"]["unsupported_claims"]


def test_generated_ids_do_not_count_as_unsupported_number_claims():
    """用于验证结构化 id 中的数字不会被当成简历事实。"""
    before = {
        "projects": [
            {
                "id": "proj_1",
                "highlights": [{"id": "b1", "text": "实现监控能力，覆盖 20 个核心接口"}],
            }
        ]
    }
    after = {
        "projects": [
            {
                "id": "proj_1895",
                "highlights": [
                    {
                        "id": "proj_1895_hl_65",
                        "text": "搭建 Prometheus 监控体系，覆盖 20 个核心接口，将故障定位时间从 30 分钟压缩至 10 分钟"
                    }
                ],
            }
        ]
    }

    result = score_final_resume_quality(
        resume_before=before,
        resume_after=after,
        user_message="故障定位时间从 30 分钟压缩至 10 分钟",
    )

    assert "1895" not in result["fact_check"]["unsupported_claims"]
    assert "65" not in result["fact_check"]["unsupported_claims"]


def test_excellent_005_expert_rewrite_passes_final_quality_gate():
    """用于验证 excellent-005 专家答案能通过最终质量门槛。"""
    case = _excellent_005_case()
    resume_after = _resume_with_rewrite(case, case["expert_rewrite"]["text"])

    result = score_final_resume_quality(
        resume_before=case["resume"],
        resume_after=resume_after,
        jd_text=case["jd_text"],
    )

    assert result["passed"] is True
    assert result["score"] >= 85


def test_excellent_005_rewrite_without_metric_fails_final_quality_gate():
    """用于验证删除关键结果的 excellent-005 改写不能通过。"""
    case = _excellent_005_case()
    resume_after = _resume_with_rewrite(
        case,
        "以工程化方式重构多个前端后台页面，优化表单、列表、弹窗及权限逻辑，提升页面体验",
    )

    result = score_final_resume_quality(
        resume_before=case["resume"],
        resume_after=resume_after,
        jd_text=case["jd_text"],
    )

    assert result["passed"] is False
    assert "weak_evidence" in result["failure_codes"]


def test_excellent_005_rewrite_with_fabricated_stack_fails_fact_check():
    """用于验证 excellent-005 不能为了显高级编造技术栈或比例。"""
    case = _excellent_005_case()
    resume_after = _resume_with_rewrite(
        case,
        "基于 React 和 TypeScript 重构多个前端后台页面，优化表单、列表、弹窗及权限逻辑，将页面加载时间缩短 50%",
    )

    result = score_final_resume_quality(
        resume_before=case["resume"],
        resume_after=resume_after,
        jd_text=case["jd_text"],
    )

    assert result["passed"] is False
    assert {"React", "TypeScript", "50%"} <= set(result["fact_check"]["unsupported_claims"])


def _excellent_005_case() -> dict:
    """用于读取 excellent-005 黄金样例。"""
    return next(case for case in load_excellent_resume_cases() if case["id"] == "excellent-005")


def _resume_with_rewrite(case: dict, text: str) -> dict:
    """用于把 excellent-005 的目标 bullet 替换成候选改写。"""
    resume = deepcopy(case["resume"])
    resume["work_experience"][0]["highlights"][0]["text"] = text
    return resume
