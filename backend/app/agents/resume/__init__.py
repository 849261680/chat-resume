"""用于暴露简历优化 Agent 相关能力。"""

__all__ = [
    "ResumeAgent",
    "ResumeAgentHarness",
    "ResumeAgentRuntime",
]


def __getattr__(name: str):
    """用于按需加载简历 Agent，避免包初始化时引入重依赖。"""
    if name == "ResumeAgentHarness":
        from .harness import ResumeAgentHarness

        return ResumeAgentHarness
    if name == "ResumeAgent":
        from .agent import ResumeAgent

        return ResumeAgent
    if name == "ResumeAgentRuntime":
        from .runtime import ResumeAgentRuntime

        return ResumeAgentRuntime
    raise AttributeError(name)
