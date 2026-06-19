"""用于覆盖统一 Resume Quality Judgment 接口。"""

import pytest

from app.agents.resume.excellent_cases import load_excellent_resume_cases
from app.services.agent.resume_quality_judgment import judge_resume_quality


def _excellent_case(case_id: str) -> dict:
    """用于按 ID 读取优秀简历黄金样例。"""
    return next(item for item in load_excellent_resume_cases() if item["id"] == case_id)


@pytest.mark.asyncio
async def test_quality_judgment_unifies_score_final_and_trajectory_layers():
    """用于验证统一判断会聚合评分、最终质量和轨迹评测。"""
    before = {
        "personal_info": {"name": "张三", "email": "z@s.com", "phone": "13800000000"},
        "summary": {"text": "5 年后端工程师，擅长 AI Agent Runtime 和工程化建设。"},
        "education": [{"school": "北京大学", "degree": "本科", "major": "计算机科学"}],
        "projects": [
            {
                "name": "简历优化 Agent",
                "overview": "AI 简历优化工具",
                "highlights": [
                    {"text": "实现简历优化功能"},
                    {"text": "已有 39 条 Agent eval 用例和 SSE 回放能力"},
                ],
                "tech_stack": ["FastAPI", "React", "PostgreSQL"],
            }
        ],
        "skills": [{"category": "后端", "items": ["FastAPI", "React", "PostgreSQL"]}],
    }
    after = {
        "personal_info": {"name": "张三", "email": "z@s.com", "phone": "13800000000"},
        "summary": {"text": "5 年后端工程师，擅长 AI Agent Runtime、工具调用、评测体系和前后端工程化建设。"},
        "education": [{"school": "北京大学", "degree": "本科", "major": "计算机科学"}],
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
                ],
                "tech_stack": ["FastAPI", "React", "PostgreSQL"],
            }
        ],
        "skills": [{"category": "后端", "items": ["FastAPI", "React", "PostgreSQL"]}],
    }

    judgment = await judge_resume_quality(
        resume_before=before,
        resume_after=after,
        jd_text="负责 AI Agent Runtime、工具调用、评测体系和前后端工程化建设。",
        trajectory={
            "runtime_events": [
                {"event_type": "text_delta", "content": "我会先保守改写项目亮点。"},
                {"event_type": "tool_call_started", "tool_name": "update_bullet"},
            ],
            "tool_calls": [{"name": "优化要点", "success": True}],
            "final_text": "已基于原始经历改写，聚焦动作、方案和已有结果。",
        },
        trajectory_case=_excellent_case("excellent-011"),
    )

    assert judgment["passed"] is True
    assert judgment["layers"]["resume_score"]["total_score"] >= 70
    assert judgment["layers"]["final_resume_quality"]["passed"] is True
    assert judgment["layers"]["trajectory"]["passed"] is True
    assert judgment["failure_codes"] == []
    assert judgment["evidence"]


@pytest.mark.asyncio
async def test_quality_judgment_surfaces_failures_and_priority_actions():
    """用于验证统一判断会暴露失败代码和下一步动作。"""
    weak_resume = {
        "projects": [
            {
                "id": "proj_1",
                "name": "管理系统",
                "overview": "做了一个后台系统",
                "highlights": [{"id": "hl_1", "text": "负责开发页面"}],
                "tech_stack": ["Vue"],
            }
        ]
    }

    judgment = await judge_resume_quality(
        resume_before=weak_resume,
        resume_after=weak_resume,
        jd_text="要求熟悉后端接口、性能优化和数据库设计。",
    )

    assert judgment["passed"] is False
    assert "final_resume_quality:insufficient_star" in judgment["failure_codes"]
    assert judgment["priority_actions"]
    assert judgment["agent_next_step"]
