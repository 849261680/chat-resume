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

def test_role_fit_counts_performance_evidence_aliases():
    """用于验证加载时间等证据可命中 JD 中的性能要求。"""
    before = {
        "work_experience": [
            {
                "highlights": [
                    {"text": "重构商品详情页组件，将首屏加载时间从 2.8s 降到 1.6s"}
                ]
            }
        ],
        "skills": [{"category": "前端", "items": ["Vue", "组件化"]}],
    }
    after = deepcopy(before)
    after["work_experience"][0]["highlights"][0]["text"] = (
        "重构商品详情页前端组件，拆分复杂交互模块并优化首屏加载链路，将首屏加载时间从 2.8s 降至 1.6s"
    )

    result = score_final_resume_quality(
        resume_before=before,
        resume_after=after,
        jd_text="前端岗位强调组件化、性能优化和复杂交互。",
    )

    assert result["dimensions"]["role_fit"]["passed"] is True
    assert "性能" in result["dimensions"]["role_fit"]["matched"]


def test_role_fit_counts_frontend_engineering_evidence_aliases():
    """用于验证页面重构和权限逻辑可命中前端工程化要求。"""
    before = {
        "work_experience": [
            {
                "highlights": [
                    {
                        "text": "参与并负责多个后台页面的重构工作，对表单、列表、弹窗和权限逻辑进行了整理，最终让页面加载时间从 3 秒缩短到 1.2 秒"
                    }
                ]
            }
        ]
    }
    after = deepcopy(before)
    after["work_experience"][0]["highlights"][0]["text"] = (
        "重构多个后台页面，梳理表单、列表、弹窗及权限逻辑，将页面加载时间从 3 秒缩短至 1.2 秒"
    )

    result = score_final_resume_quality(
        resume_before=before,
        resume_after=after,
        jd_text="需要表达清晰、重点突出的前端工程化经验。",
    )

    assert result["dimensions"]["role_fit"]["passed"] is True
    assert {"前端", "工程化"} <= set(result["dimensions"]["role_fit"]["matched"])



def test_spring_boot_counts_as_technical_evidence():
    """用于验证 Spring Boot 经历可计入技术证据密度。"""
    resume = {
        "projects": [
            {
                "highlights": [
                    {
                        "text": "基于 Spring Boot 设计并实现商品发布与搜索接口，支撑校园二手交易平台核心业务流转"
                    }
                ]
            }
        ]
    }

    result = score_final_resume_quality(
        resume_before=resume,
        resume_after=resume,
        jd_text="强调后端业务系统和接口设计经验。",
    )

    assert result["dimensions"]["evidence_density"]["passed"] is True


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

def test_added_strong_bullet_is_scored_without_penalizing_unchanged_weak_bullet():
    """用于验证新增亮点样例只评分本轮新增的高质量 bullet。"""
    before = {
        "work_experience": [
            {
                "id": "work_backend",
                "highlights": [{"id": "b1", "text": "开发订单查询接口"}],
            }
        ]
    }
    after = deepcopy(before)
    after["work_experience"][0]["highlights"].append(
        {
            "id": "b2",
            "text": "搭建 Prometheus 监控体系，覆盖 20 个核心接口，将故障定位时间从 30 分钟缩短至 10 分钟",
        }
    )

    result = score_final_resume_quality(
        resume_before=before,
        resume_after=after,
        jd_text="需要能体现监控、稳定性和问题排查能力。",
        user_message="我还搭过 Prometheus 监控，覆盖了 20 个接口，故障定位从 30 分钟降到 10 分钟",
    )

    assert result["passed"] is True
    assert result["dimensions"]["star_strength"]["total"] == 1



def test_excellent_005_expert_rewrite_passes_final_quality_gate():
    """用于验证 excellent-005 专家答案能通过最终质量门槛。"""
    case = _excellent_case("excellent-005")
    resume_after = _resume_with_target_rewrite(case, case["expert_rewrite"]["text"])

    result = score_final_resume_quality(
        resume_before=case["resume"],
        resume_after=resume_after,
        jd_text=case["jd_text"],
    )

    assert result["passed"] is True
    assert result["score"] >= 85


def test_excellent_005_rewrite_without_metric_fails_final_quality_gate():
    """用于验证删除关键结果的 excellent-005 改写不能通过。"""
    case = _excellent_case("excellent-005")
    resume_after = _resume_with_target_rewrite(
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
    case = _excellent_case("excellent-005")
    resume_after = _resume_with_target_rewrite(
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

def test_english_rewrite_without_comma_is_interview_ready():
    """用于验证英文连接词也能形成可追问的技术链路。"""
    before = {
        "work_experience": [
            {
                "highlights": [
                    {"text": "Built React admin pages and REST APIs for internal operations"}
                ]
            }
        ],
        "skills": [{"category": "Full-stack", "items": ["React", "REST API"]}],
    }
    after = deepcopy(before)
    after["work_experience"][0]["highlights"][0]["text"] = (
        "Designed and delivered React admin interfaces and REST APIs that streamlined internal operations and improved team workflow efficiency"
    )

    result = score_final_resume_quality(
        resume_before=before,
        resume_after=after,
        jd_text="Full-stack role requiring React, API design, and measurable product impact.",
    )

    assert result["dimensions"]["interview_readiness"]["passed"] is True



def test_excellent_011_expert_rewrite_passes_final_quality_gate():
    """用于验证 excellent-011 专家答案能通过最终质量门槛。"""
    case = _excellent_case("excellent-011")
    resume_after = _resume_with_target_rewrite(case, case["expert_rewrite"]["text"])

    result = score_final_resume_quality(
        resume_before=case["resume"],
        resume_after=resume_after,
        jd_text=case["jd_text"],
    )

    assert result["passed"] is True
    assert result["score"] >= 85


def test_conservative_professional_rewrite_relaxes_interview_readiness_gate():
    """用于验证保守润色任务不因禁止扩写而被面试追问维度误杀。"""
    case = _excellent_case("excellent-011")
    resume_after = _resume_with_target_rewrite(
        case,
        "基于 Spring Boot 设计并实现商品发布与搜索接口，支撑平台核心交易流程",
    )

    result = score_final_resume_quality(
        resume_before=case["resume"],
        resume_after=resume_after,
        jd_text=case["jd_text"],
        user_message=case["user_message"],
    )

    assert result["passed"] is True
    assert result["score"] >= 85
    assert result["dimensions"]["interview_readiness"]["passed"] is False
    assert "low_interview_readiness" not in result["failure_codes"]


def test_excellent_011_rewrite_without_core_impact_fails_final_quality_gate():
    """用于验证 excellent-011 删除后端业务价值后不能通过。"""
    case = _excellent_case("excellent-011")
    resume_after = _resume_with_target_rewrite(
        case,
        "使用 Spring Boot 完成商品发布和搜索接口开发",
    )

    result = score_final_resume_quality(
        resume_before=case["resume"],
        resume_after=resume_after,
        jd_text=case["jd_text"],
    )

    assert result["passed"] is False
    assert "weak_evidence" in result["failure_codes"]


def test_excellent_011_rewrite_with_fabricated_claims_fails_fact_check():
    """用于验证 excellent-011 不能编造技术栈、规模或比例。"""
    case = _excellent_case("excellent-011")
    resume_after = _resume_with_target_rewrite(
        case,
        "基于 Redis 和 Kafka 重构商品搜索链路，将接口延迟降低 70%，支撑 10万 DAU",
    )

    result = score_final_resume_quality(
        resume_before=case["resume"],
        resume_after=resume_after,
        jd_text=case["jd_text"],
    )

    assert result["passed"] is False
    assert {"Redis", "Kafka", "70%"} <= set(result["fact_check"]["unsupported_claims"])




def test_english_rewrite_with_source_backed_product_impact_passes_final_gate():
    """用于验证英文无量化改写可用来源里的业务影响通过质量门禁。"""
    before = {
        "work_experience": [
            {
                "id": "work_fullstack",
                "company": "Startup",
                "highlights": [
                    {"id": "b1", "text": "Built React admin pages and REST APIs for internal operations"}
                ],
            }
        ],
        "skills": [{"id": "s1", "category": "Full-stack", "items": ["React", "REST API"]}],
    }
    after = deepcopy(before)
    after["work_experience"][0]["highlights"][0]["text"] = (
        "Designed and built React admin interfaces and REST APIs to streamline "
        "internal operations, reducing manual workflows and improving team efficiency"
    )

    result = score_final_resume_quality(
        resume_before=before,
        resume_after=after,
        jd_text="Full-stack role requiring React, API design, and measurable product impact.",
    )

    assert result["passed"] is True
    assert result["score"] >= 85
def test_excellent_011_rewrite_with_unsupported_jd_capabilities_fails_fact_check():
    """用于验证 excellent-011 不能把 JD 能力词包装成无来源事实。"""
    case = _excellent_case("excellent-011")
    resume_after = _resume_with_target_rewrite(
        case,
        "基于 Spring Boot 设计并实现商品发布与搜索接口，完成 MySQL 数据库查询优化与参数校验，保障核心交易链路的稳定性",
    )

    result = score_final_resume_quality(
        resume_before=case["resume"],
        resume_after=resume_after,
        jd_text=case["jd_text"],
    )

    assert result["passed"] is False
    assert {"数据库查询优化", "参数校验", "稳定性"} <= set(
        result["fact_check"]["unsupported_claims"]
    )


def _excellent_case(case_id: str) -> dict:
    """用于按 ID 读取优秀简历黄金样例。"""
    return next(case for case in load_excellent_resume_cases() if case["id"] == case_id)


def _resume_with_target_rewrite(case: dict, text: str) -> dict:
    """用于把黄金样例的目标 bullet 替换成候选改写。"""
    resume = deepcopy(case["resume"])
    target = case["expert_rewrite"]
    for item in resume[target["section"]]:
        if item.get("id") == target["item_id"]:
            _rewrite_highlight(item, target["bullet_id"], text)
            return resume
    raise AssertionError(f"missing target item: {target['item_id']}")


def _rewrite_highlight(item: dict, bullet_id: str, text: str) -> None:
    """用于替换单个经历条目的指定 bullet 文本。"""
    for highlight in item["highlights"]:
        if highlight.get("id") == bullet_id:
            highlight["text"] = text
            return
    raise AssertionError(f"missing target bullet: {bullet_id}")
