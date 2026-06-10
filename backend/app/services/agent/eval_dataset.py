"""简历优化效果评测数据集。

每条 = (场景描述, 原简历bullet, 用户请求, 优化后bullet, 期望是好优化?)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ── 结构定义 ────────────────────────────────────────────────

@dataclass
class EvalCase:
    """单个评测用例。"""

    case_id: str
    category: str  # "good" | "bad" | "edge"
    original: str  # 原 bullet
    user_request: str  # 用户请求
    optimized: str  # 优化后 bullet
    expected_good: bool  # 期望是好优化
    notes: str = ""  # 为什么好/坏


@dataclass
class EvalResult:
    """单条评测结果。"""

    case: EvalCase
    rule_score: float
    llm_score: float | None = None
    combined_score: float = 0.0
    passed: bool = False
    llm_dimensions: list[dict[str, Any]] | None = None
    llm_summary: str = ""


# ── 评测数据集 ──────────────────────────────────────────────

EVAL_CASES: list[EvalCase] = [
    # ━━ 好优化案例 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    EvalCase(
        case_id="good-001",
        category="good",
        original="负责前端开发",
        user_request="优化亮点，补充量化数据",
        optimized="主导前端架构重构，将首屏加载时间从 3.2s 降至 1.1s，提升 65%",
        expected_good=True,
        notes="✅ 补充了具体数字、动作动词、结果对比",
    ),
    EvalCase(
        case_id="good-002",
        category="good",
        original="参与系统性能优化",
        user_request="写得更具体一点",
        optimized="设计并实施数据库查询优化方案，慢查询从 120 条/天降至 3 条/天，接口响应 P99 从 2s 降至 200ms",
        expected_good=True,
        notes="✅ 从模糊参与变为可验证的具体成果",
    ),
    EvalCase(
        case_id="good-003",
        category="good",
        original="写了一些接口",
        user_request="优化这条亮点",
        optimized="独立设计 RESTful API 网关，统一 12 个微服务的认证与限流，日均处理 500 万请求",
        expected_good=True,
        notes="✅ 补充了技术细节、规模和数字",
    ),
    EvalCase(
        case_id="good-004",
        category="good",
        original="使用了 React 技术栈",
        user_request="优化这条亮点",
        optimized="基于 React 18 + TypeScript 搭建组件库，封装 40+ 业务组件，团队开发效率提升 30%",
        expected_good=True,
        notes="✅ 从罗列技术栈变为展示工程成果",
    ),
    EvalCase(
        case_id="good-005",
        category="good",
        original="负责用户增长",
        user_request="补充具体数据",
        optimized="设计 A/B 实验体系与增长飞轮策略，6 个月内 DAU 从 10 万增长至 50 万，留存率提升 15pp",
        expected_good=True,
        notes="✅ 时间范围 + 数字对比 + 多维度结果",
    ),
    # ━━ 坏优化案例 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    EvalCase(
        case_id="bad-001",
        category="bad",
        original="负责日常开发工作",
        user_request="让亮点看起来更厉害",
        optimized="主导公司核心战略产品的全链路架构设计，带领 50 人团队实现年营收增长 300%，获得 CEO 特别嘉奖",
        expected_good=False,
        notes="❌ 编造：从普通开发变成了带50人团队的架构师，明显幻觉",
    ),
    EvalCase(
        case_id="bad-002",
        category="bad",
        original="写了一些测试用例",
        user_request="优化",
        optimized="本着严谨负责的工作态度，认真细致地编写了测试用例，确保了产品质量的稳步提升",
        expected_good=False,
        notes="❌ 空洞：全是形容词没有具体信息，比原文还差",
    ),
    EvalCase(
        case_id="bad-003",
        category="bad",
        original="负责后端接口开发",
        user_request="优化",
        optimized="负责后端接口开发，按时完成分配的任务，与同事配合良好",
        expected_good=False,
        notes="❌ 没有改进：只是加了废话，内容和原文一样",
    ),
    EvalCase(
        case_id="bad-004",
        category="bad",
        original="参与项目",
        user_request="写详细一点",
        optimized="我负责这个项目的前端部分，主要是用 Vue 写了一些页面，后来因为人手不够，又帮忙写了一部分后端代码，反正就是什么都做了一些",
        expected_good=False,
        notes="❌ 口语化、啰嗦、没有量化，不如原文",
    ),
    EvalCase(
        case_id="bad-005",
        category="bad",
        original="维护已有系统",
        user_request="写得好看一点",
        optimized="重构了承载 10 亿用户的全栈系统，P99 延迟优化至 0.01ms，系统可用性达到 99.99999%",
        expected_good=False,
        notes="❌ 数字夸张到不可信：0.01ms 和 7 个 9，明显编造",
    ),
    # ━━ 边界案例 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    EvalCase(
        case_id="edge-001",
        category="edge",
        original="参与了团队的日常站会和代码 review",
        user_request="优化",
        optimized="参与代码评审流程，审查 200+ PR，发现并修复 30+ 潜在生产问题",
        expected_good=True,
        notes="⚠️ 边界：从站会+review 变成了量化成果，合理但数字可能偏高",
    ),
    EvalCase(
        case_id="edge-002",
        category="edge",
        original="搭建了公司内部 wiki",
        user_request="优化",
        optimized="搭建公司知识管理平台，沉淀 500+ 技术文档，月活跃用户覆盖全公司 300+ 工程师",
        expected_good=True,
        notes="⚠️ 从 wiki 变成了知识管理平台，有一点包装但可接受",
    ),
    EvalCase(
        case_id="edge-003",
        category="edge",
        original="对接第三方支付接口",
        user_request="量化",
        optimized="对接微信/支付宝支付接口，日均交易笔数 5 万+，支付成功率 99.8%",
        expected_good=True,
        notes="⚠️ 数字是真实可达的，但不确定用户是否真知道这些数字",
    ),
    EvalCase(
        case_id="edge-004",
        category="edge",
        original="负责数据处理",
        user_request="优化",
        optimized="设计 ETL 数据管道，处理 2TB 日增量日志数据，数据延时从 4h 降至 15min",
        expected_good=True,
        notes="⚠️ 从简单描述变成了很有技术含量的表述，合理但跳跃较大",
    ),
    EvalCase(
        case_id="edge-005",
        category="edge",
        original="编写技术文档",
        user_request="优化",
        optimized="编写团队技术文档，我只是一个程序员，没什么好写的",
        expected_good=False,
        notes="⚠️ 后半句自我贬低，不应该出现在简历中",
    ),
]
