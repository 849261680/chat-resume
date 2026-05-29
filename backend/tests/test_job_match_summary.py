"""用于覆盖 JD 匹配摘要生成的回归测试。"""

import pytest

from app.services.agent import job_match_summary
from app.infra.config import settings
from app.services.agent.job_match_summary import (
    build_job_match_summary,
    build_job_match_top_gaps,
)
from app.tools.resume.job_match_summary_tool import generate_job_match_summary


class FakeSemanticJobMatchAnalyzer:
    """用于在测试中模拟岗位匹配语义模型。"""

    def __init__(self):
        """用于记录语义分析调用次数。"""
        self.calls = 0

    async def analyze(self, *, jd_text: str, resume_text: str):
        """用于返回可预测的语义匹配结果。"""
        self.calls += 1
        assert "React" in jd_text
        assert "前端框架" in resume_text
        return {
            "matched_keywords": ["React", "数据分析", "高并发"],
            "missing_keywords": ["Redis"],
            "fact_gaps": ["需要补充 Redis 缓存或队列相关真实经历"],
        }


class FakeAgentBackendAnalyzer:
    """用于模拟 Agent 后端岗位匹配结果。"""

    async def analyze(self, *, jd_text: str, resume_text: str):
        """用于返回 Agent 后端匹配证据。"""
        assert "Redis" in jd_text
        assert "Agent" in resume_text
        return {
            "matched_keywords": ["Agent", "后端"],
            "missing_keywords": ["Redis"],
            "fact_gaps": ["需要补充 Redis 相关真实经历"],
        }


class FailingSemanticAnalyzer:
    """用于模拟语义模型调用失败。"""

    async def analyze(self, *, jd_text: str, resume_text: str):
        """用于抛出语义分析异常。"""
        raise RuntimeError("semantic service unavailable")


class CountingSemanticAnalyzer:
    """用于验证无 JD 时不会触发语义分析。"""

    def __init__(self):
        """用于记录调用次数。"""
        self.calls = 0

    async def analyze(self, *, jd_text: str, resume_text: str):
        """用于记录语义分析调用。"""
        self.calls += 1
        return {
            "matched_keywords": [],
            "missing_keywords": [],
            "fact_gaps": [],
        }


class LongSemanticAnalyzer:
    """用于验证岗位匹配关键词最多保留 20 个。"""

    async def analyze(self, *, jd_text: str, resume_text: str):
        """用于返回超过展示上限的语义匹配结果。"""
        return {
            "matched_keywords": [f"命中{i}" for i in range(1, 21)],
            "missing_keywords": [f"缺失{i}" for i in range(1, 21)],
            "fact_gaps": [],
        }


@pytest.mark.asyncio
async def test_generate_job_match_summary_uses_semantic_evidence():
    """用于验证岗位匹配摘要能识别语义相近但措辞不同的证据。"""
    analyzer = FakeSemanticJobMatchAnalyzer()
    resume = {
        "job_application": {
            "jd_text": "要求 React、数据分析、高并发和 Redis 经验。",
        },
        "projects": [
            {
                "name": "增长分析平台",
                "highlights": [
                    {"text": "负责前端框架建设，搭建 BI 报表，支撑百万 QPS 服务。"}
                ],
            }
        ],
    }

    result = await generate_job_match_summary(
        resume,
        semantic_analyzer=analyzer,
    )

    assert analyzer.calls == 1
    assert result["success"] is True
    summary = result["job_match_summary"]
    assert summary["matched_keywords"] == ["React", "数据分析", "高并发"]
    assert summary["missing_keywords"] == ["Redis"]
    assert "需要补充 Redis 缓存或队列相关真实经历" in summary["fact_gaps"]


@pytest.mark.asyncio
async def test_generate_job_match_summary_uses_default_semantic_llm(monkeypatch):
    """用于验证默认工具路径会调用 LLM 生成语义匹配证据。"""
    calls: list[dict[str, object]] = []
    models: list[str | None] = []

    class FakeChatService:
        """用于模拟项目统一 LLM 服务。"""

        def __init__(self, model: str | None = None):
            """用于记录岗位匹配工具使用的模型。"""
            models.append(model)

        @staticmethod
        def _coerce_content_text(value):
            """用于返回模型文本内容。"""
            return value if isinstance(value, str) else ""

        async def __aenter__(self):
            """用于进入异步上下文。"""
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            """用于退出异步上下文。"""
            return None

        async def chat_completion(self, **kwargs):
            """用于返回语义匹配 JSON。"""
            calls.append(kwargs)
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"matched_keywords":["React"],'
                                '"missing_keywords":["Redis"],'
                                '"fact_gaps":["需要补充 Redis 相关真实经历"]}'
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr(job_match_summary, "ChatService", FakeChatService, raising=False)
    resume = {
        "job_application": {"jd_text": "要求 React 和 Redis 经验。"},
        "projects": [{"name": "前端平台", "overview": "负责前端框架建设"}],
    }

    result = await generate_job_match_summary(resume)

    assert len(calls) == 1
    prompt = str(calls[0]["system_prompt"])
    assert "概念级关键词" in prompt
    assert "不要把 JD 当作分词任务" in prompt
    assert "Function Calling" in prompt
    assert "不要同时输出 AGENT 和 Agent" in prompt
    assert models == [settings.DEEPSEEK_JOB_MATCH_MODEL]
    assert result["success"] is True
    assert result["job_match_summary"]["matched_keywords"] == ["React"]
    assert result["job_match_summary"]["missing_keywords"] == ["Redis"]


@pytest.mark.asyncio
async def test_generate_job_match_summary_reuses_default_semantic_cache(monkeypatch):
    """用于验证相同 JD 和简历会复用默认语义匹配缓存。"""
    calls = 0

    class FakeChatService:
        """用于模拟可计数的 LLM 服务。"""

        def __init__(self, model: str | None = None):
            """用于兼容生产代码传入的岗位匹配模型。"""
            self.model = model

        @staticmethod
        def _coerce_content_text(value):
            """用于返回模型文本内容。"""
            return value if isinstance(value, str) else ""

        async def __aenter__(self):
            """用于进入异步上下文。"""
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            """用于退出异步上下文。"""
            return None

        async def chat_completion(self, **kwargs):
            """用于返回岗位匹配 JSON 并计数。"""
            nonlocal calls
            calls += 1
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"matched_keywords":["数据分析"],'
                                '"missing_keywords":["Redis"],'
                                '"fact_gaps":["需要补充 Redis 相关真实经历"]}'
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr(job_match_summary, "ChatService", FakeChatService, raising=False)
    resume = {
        "job_application": {"jd_text": "要求数据分析和 Redis 经验。"},
        "projects": [{"name": "分析平台", "overview": "搭建 BI 报表"}],
    }

    first = await generate_job_match_summary(resume)
    second = await generate_job_match_summary(resume)

    assert calls == 1
    assert first["job_match_summary"] == second["job_match_summary"]


@pytest.mark.asyncio
async def test_generate_job_match_summary_falls_back_when_semantic_fails():
    """用于验证语义分析失败时仍返回规则版岗位匹配摘要。"""
    resume = {
        "job_application": {"jd_text": "要求 Agent、后端和 Redis 经验。"},
        "work_experience": [{"highlights": [{"text": "负责 Agent 后端服务"}]}],
    }

    result = await generate_job_match_summary(
        resume,
        semantic_analyzer=FailingSemanticAnalyzer(),
    )

    assert result["success"] is True
    assert result["job_match_summary"]["matched_keywords"] == ["Agent", "后端"]
    assert "Redis" in result["job_match_summary"]["missing_keywords"]


@pytest.mark.asyncio
async def test_generate_job_match_summary_keeps_up_to_twenty_keywords():
    """用于验证岗位匹配摘要最多保留 20 个命中和缺失关键词。"""
    result = await generate_job_match_summary(
        {
            "job_application": {"jd_text": "要求多个岗位关键词。"},
            "projects": [{"name": "测试项目", "overview": "覆盖多个关键词"}],
        },
        semantic_analyzer=LongSemanticAnalyzer(),
    )

    summary = result["job_match_summary"]
    assert summary["matched_keywords"] == [f"命中{i}" for i in range(1, 21)]
    assert summary["missing_keywords"] == [f"缺失{i}" for i in range(1, 21)]


def test_build_job_match_summary_extracts_evidence_from_jd_resume_and_diff():
    """用于验证岗位匹配摘要只基于 JD、简历和已确认改动生成。"""
    original_resume = {
        "job_application": {
            "jd_text": "负责复杂前端交互、性能优化和工程化建设，要求 React 和 TypeScript。",
        },
        "projects": [
            {
                "name": "简历编辑器",
                "highlights": [{"text": "负责 React 前端开发"}],
            }
        ],
    }
    latest_resume = {
        **original_resume,
        "projects": [
            {
                "name": "简历编辑器",
                "highlights": [
                    {"text": "负责 React 前端开发，首屏性能优化 35%"}
                ],
            }
        ],
    }

    summary = build_job_match_summary(
        original_resume=original_resume,
        latest_resume_content=latest_resume,
        confirmed_diff_items=[
            {
                "before": "负责 React 前端开发",
                "after": "负责 React 前端开发，首屏性能优化 35%",
                "reason": "补充岗位关键词和量化结果",
            }
        ],
    )

    assert summary is not None
    assert "React" in summary["matched_keywords"]
    assert "性能优化" in summary["matched_keywords"]
    assert "TypeScript" in summary["missing_keywords"]
    assert summary["top_gaps"]
    assert summary["resume_changes"] == [
        "补充岗位关键词和量化结果：负责 React 前端开发，首屏性能优化 35%"
    ]
    assert "可补充与「TypeScript」相关的真实经历或结果" in summary["fact_gaps"]


def test_build_job_match_summary_returns_none_without_jd_text():
    """用于验证缺少 JD 时不会生成空洞摘要。"""
    summary = build_job_match_summary(
        original_resume={"projects": [{"name": "内部系统"}]},
        latest_resume_content={"projects": [{"name": "内部系统"}]},
        confirmed_diff_items=[],
    )

    assert summary is None


@pytest.mark.asyncio
async def test_generate_job_match_summary_does_not_call_semantic_without_jd():
    """用于验证缺少 JD 时不会调用语义模型。"""
    analyzer = CountingSemanticAnalyzer()

    result = await generate_job_match_summary(
        {"projects": [{"name": "内部系统"}]},
        semantic_analyzer=analyzer,
    )

    assert analyzer.calls == 0
    assert result["success"] is False
    assert "缺少 JD" in result["message"]


@pytest.mark.asyncio
async def test_generate_job_match_summary_tool_returns_summary_payload():
    """用于验证岗位匹配摘要工具返回前端可直接消费的 payload。"""
    resume = {
        "job_application": {"jd_text": "要求 Agent、后端和 Redis 经验。"},
        "work_experience": [{"highlights": [{"text": "负责 Agent 后端服务"}]}],
    }

    result = await generate_job_match_summary(
        resume,
        confirmed_diff_items=[
            {
                "after": "负责 Agent 后端服务，支撑高并发接口",
                "reason": "补充岗位关键词",
            }
        ],
        semantic_analyzer=FakeAgentBackendAnalyzer(),
    )

    assert result["success"] is True
    assert result["job_match_summary"]["matched_keywords"] == ["Agent", "后端"]
    assert "Redis" in result["job_match_summary"]["missing_keywords"]
    assert result["job_match_summary"]["resume_changes"] == [
        "补充岗位关键词：负责 Agent 后端服务，支撑高并发接口"
    ]
    assert result["job_match_summary"]["top_gaps"]


def test_build_job_match_top_gaps_groups_keywords_into_capability_gaps():
    """用于验证 JD 工具返回能力缺口，而不是只返回零散关键词。"""
    resume = {
        "job_application": {
            "jd_text": (
                "负责基于 LLM 的 Agent 应用开发，设计 tool calling、workflow "
                "orchestration 和 human-in-the-loop 机制。构建 RAG、LlamaIndex "
                "或 LangChain 工具链，熟悉 FastAPI、React、SSE。"
            )
        },
        "projects": [
            {
                "name": "Chat Resume",
                "overview": "基于 Agent 的简历优化工具",
                "highlights": [{"text": "实现 FastAPI 后端和 React 前端"}],
            }
        ],
    }

    summary = build_job_match_summary(
        original_resume=resume,
        latest_resume_content=resume,
        confirmed_diff_items=[],
    )

    assert summary is not None
    top_gaps = summary["top_gaps"]
    assert 1 <= len(top_gaps) <= 3
    assert any(gap["gap"] == "RAG / LlamaIndex 落地经验" for gap in top_gaps)
    assert all(gap["jd_evidence"] for gap in top_gaps)
    assert all(gap["resume_anchor"] for gap in top_gaps)
    assert all(
        gap["risk"]
        in {"can_improve", "needs_user_confirmation", "insufficient_evidence"}
        for gap in top_gaps
    )


def test_build_job_match_top_gaps_returns_empty_without_missing_keywords():
    """用于验证没有缺失关键词时不生成空洞 Top gaps。"""
    gaps = build_job_match_top_gaps(
        resume_content={"projects": [{"name": "Agent", "overview": "RAG FastAPI"}]},
        matched_keywords=["Agent", "RAG", "FastAPI"],
        missing_keywords=[],
        jd_text="要求 Agent、RAG、FastAPI。",
    )

    assert gaps == []
