# 简历优化 Agent 与 OpenAI Agents SDK 最佳实践审计报告

审计时间：2026-06-12
范围：当前简历优化 Agent 的后端 runtime、工具执行、人工确认、session/恢复、eval/trace/observability，以及前端 SSE/HITL 交互。

## 结论

当前简历优化 Agent **部分符合** OpenAI Agents SDK 最佳实践：后端已经真实使用 `openai-agents`、`Agent`、`Runner.run_streamed()`、`FunctionTool`、`needs_approval`、`RunState` 恢复、`RunConfig` trace 字段和 streaming delta；前端也能消费 SSE、展示工具确认卡、提交确认/拒绝/反馈，并恢复待确认 session。

但它不是一个“完全 SDK 托管”的 Agents SDK 应用。项目仍保留自定义 `ResumeAgentLoop`、`pi_agent_core` 消息协议和应用自管 session/event store。这是合理的产品选择，因为本项目需要可见 ReAct loop、工具确认和简历持久化；但从 SDK 最佳实践角度，仍有几个明显缺口：

1. `score_resume` 评分服务存在，但未注册为 Resume Agent 可用工具，`resume_edit`/`read_only` profile 都拿不到它。
2. DeepSeek provider 分支主动 `tracing_disabled=True`，导致非 OpenAI provider 下没有 SDK trace。
3. 自定义 ReAct loop 与 SDK 自带 turn/tool loop 并存，边界复杂，后续维护成本高。
4. 前端 streaming/HITL 状态集中在一个大 hook 和编辑页中，功能完整但协议边界不够清晰。
5. eval 产物兼容 OpenAI Agents 形状，但还不是完整的平台化 eval/trace 运行闭环。

## 官方最佳实践基线

官方文档给出的关键判断标准：

- Agents 是会计划、调用工具、协作并保留足够状态完成多步任务的应用；当应用拥有编排、工具执行、审批和状态时，应使用 Agents SDK。见 OpenAI API Agents SDK guide: https://developers.openai.com/api/docs/guides/agents
- `Agent` 应以 instructions、tools、handoffs、guardrails 和 structured outputs 组织；如果想自己拥有 loop，则应清楚知道是在绕过 SDK 默认编排。见 Agents docs: https://openai.github.io/openai-agents-python/agents/
- 工具应通过 SDK 工具模型暴露，敏感工具应使用 human-in-the-loop approval，审批中断后可通过 `RunState` 序列化/恢复。见 Tools/HITL docs: https://openai.github.io/openai-agents-python/tools/ 和 https://openai.github.io/openai-agents-python/human_in_the_loop/
- streaming 应使用 `Runner.run_streamed()` 并持续消费 `stream_events()` 直到 iterator 结束；结束前不能假设 run 完成。见 Streaming/Results docs: https://openai.github.io/openai-agents-python/streaming/ 和 https://openai.github.io/openai-agents-python/results/
- tracing 默认开启，覆盖 LLM generations、tool calls、handoffs、guardrails 和 custom events；`RunConfig` 支持 workflow/trace/group/metadata 等字段。见 Tracing docs: https://openai.github.io/openai-agents-python/tracing/

## 后端审计

### 符合点

- 真实接入 Agents SDK：`backend/app/runtime/openai_agents_adapter.py` 直接导入 `Agent`、`FunctionTool`、`RunConfig`、`Runner`、`RunState`、`RawResponsesStreamEvent`，不是只做文档声明。
- 使用 SDK streaming：`OpenAIAgentsStreamAdapter.run_sdk_streamed()` 调用 `Runner.run_streamed(..., max_turns=40, run_config=...)`，`OpenAIAgentsStreamBridge.run_until_final()` 消费 `result.stream_events()`。
- 文本 delta 是真实 streaming：adapter 只把 `response.output_text.delta` 转成 `StreamTextDeltaEvent`，外层 loop 再通过 `publish_streamed_text_delta()` 立即发给 SSE。
- 工具通过 SDK `FunctionTool` 包装：现有业务工具 schema 被映射到 `params_json_schema`，执行通过 `on_invoke_tool` 进入业务 executor。
- HITL 走 SDK approval：非自动执行工具被挂上 `_sdk_needs_approval` 和 `_sdk_handle_approval`，再映射到 `FunctionTool.needs_approval`。
- approval 恢复使用 SDK 模式：streaming run 出现 `result.interruptions` 后，代码调用 `result.to_state()`，再 `state.approve(...)` 或 `state.reject(...)` 并继续 run。
- 明确禁用并行工具：`ModelSettings(parallel_tool_calls=False)`，同时业务层也用 lock 和“每个 ReAct turn 只执行一个可见工具”保证工具顺序。
- 应用层 session/事件持久化完整：`ResumeAgentStreamService` 创建 session，写入公开 SSE 事件，提供 cursor replay 和 pending confirmation 恢复。
- trace/eval 字段有接入：`OpenAIAgentsTraceConfig` 可写入 `RunConfig.workflow_name`、`trace_id`、`group_id`、`trace_metadata`、`trace_include_sensitive_data`。

### 不符合或薄弱点

1. **评分工具未暴露给 Agent。**
   - 证据：`backend/app/services/agent/resume_score.py` 定义了 `score_resume`，但 `backend/app/tools/resume/registry.py` 只注册了 `evaluate_bullet`，没有注册 `score_resume`。
   - 证据：`backend/app/agents/resume/agent.py` 的 `resume_edit` 和 `read_only` profile 都没有 `score_resume`。
   - 影响：Agent 不能在真实编辑 loop 中先调用统一评分面板再决定下一步，只能依赖 prompt、局部 `evaluate_bullet` 或外部 eval。这不符合“工具是 Agent 能采取行动的能力边界”的 SDK 设计，也不符合本项目保留单一 `score_resume` 入口的产品方向。

2. **DeepSeek 分支没有 SDK trace。**
   - 证据：`provider_run_config()` 对 DeepSeek `RunConfig(..., tracing_disabled=True)`。
   - 影响：官方 tracing 最佳实践强调开发和生产中用 trace 调试、可视化和监控 workflow。当前 OpenAI provider 可用 trace 配置，DeepSeek provider 只能靠本地日志。
   - 说明：如果 DeepSeek 无法上传 OpenAI trace，这是工程上可接受的 provider 限制，但报告/README 应明确它是降级模式，不应宣称所有 provider 都具备 OpenAI 平台 trace。

3. **SDK loop 与自定义 ReAct loop 双层编排。**
   - 证据：`OpenAIAgentsStreamBridge` 内部运行 SDK 的 tool loop；外层 `ResumeAgentLoop.run()` 又按 assistant message -> tool call -> tool result 继续循环。
   - 优点：保留了产品需要的可见 ReAct、确认卡、业务日志和简历持久化。
   - 风险：SDK 已经管理 turn/tools/approvals/sessions 的一部分，外层又复制一次协议，后续 SDK 事件结构升级时，容易出现重复工具卡、漏关 pending、文本重复 flush、usage/trace 不一致。

4. **没有使用 SDK Agent-level guardrails。**
   - 当前 guardrail 主要在 prompt、工具 dry-run、final_resume_quality 和 trajectory eval 中实现。
   - 这能覆盖事实边界，但不等于 SDK `input_guardrails` / `output_guardrails` / tool guardrails。尤其是用户输入安全、最终输出事实校验、每次工具调用前后的统一 guardrail metadata 没有进入 SDK guardrail result。

5. **SDK Session/RunState 持久化只用于单次 streaming approval loop，跨请求仍由应用自管。**
   - 当前应用自管 session 是合理选择，因为还要持久化简历内容、cursor、确认 diff 和 UI 状态。
   - 缺口是文档边界不够明确：哪些状态由 SDK `RunState` 负责，哪些由 `AgentSessionStore` 负责，哪些断线恢复只恢复应用事件而不是完整 SDK run。

## 前端审计

### 符合点

- SSE cursor 支持：`useStreamingChat.ts` 读取 `id:` 和 `event_id`，设置 `Last-Event-ID`，并允许一次 replay。
- streaming delta 逐步渲染：`data.content` 累加到 `streamingContent` 和 `streamEvents`，不会只等最终 done。
- HITL UI 完整：`tool_pending` 转成确认卡，支持接受、拒绝、带反馈重试。
- pending 恢复完整：页面 mounted 后调用 `restorePendingConfirmation()`，从 `/api/ai/chat/pending-confirmation` 恢复 session 和 pending action。
- confirmation 防重复：`confirmingToolCallsRef` 防重复点击，409 视为状态已变化。
- 用户追问工具独立处理：`user_input_request` 有专门卡片，不混进普通工具结果。

### 薄弱点

1. **协议解析过于集中。**
   - `useStreamingChat.ts` 同时负责 fetch、SSE parse、cursor、stream state、tool lifecycle、confirmation API、resume-session API 和调试日志。功能正确，但这是一个高风险边界。
   - 建议拆成 `parseResumeSseEvent`、`reduceStreamEvents`、`useToolConfirmation` 三层，先用现有测试锁住行为再切。

2. **SDK 语义在前端被映射为自定义事件，缺少显式协议文档。**
   - 前端并不直接知道 SDK 的 `interruption` / `RunState` / `stream_events()`，只知道 `tool_pending`、`tool_confirmed`、`tool_rejected`。
   - 建议把 `docs/agents/domain.md` 或新增协议文档补齐：SDK event -> backend ResumeStreamEvent -> frontend StreamEvent 的映射表。

3. **历史消息与 live stream 渲染逻辑重复。**
   - 编辑页对历史 `message.streamEvents` 和 live `streamEvents` 分别处理 confirmed/rejected/pending/tool_result/text。
   - 建议抽一个纯渲染组件，降低工具事件新增时两边漏改风险。

## Eval 与可观测性

### 符合点

- `eval/openai_agents_standard.py` 已生成 `workflow_name`、`trace_id`、`group_id`、metadata、dataset item、model sample、python grader。
- `docs/OBSERVABILITY.md` 记录 request/client/session/tool call 关联字段，以及 `backend/logs/backend.log` 排障入口。
- 聚焦测试覆盖 runtime boundary、SDK adapter trace config、tool approval、streaming delta、trajectory、score 和 final quality。

### 薄弱点

- `eval/excellent_eval_results.json` 是历史产物，不等于当前 live worktree 的完整证明。
- 当前 eval 更像“OpenAI Agents eval 兼容 artifact”，不是直接提交到 OpenAI 平台、可在平台 trace/eval dashboard 一键追溯的闭环。
- 质量门禁与 Agent 工具能力脱节：`score_resume` 服务和 final quality gate 存在，但 Agent 当前工具 profile 里没有统一评分工具。

## 风险分级

### P0：当前不应称为完全符合

- `score_resume` 未注册为 Agent 工具。
- DeepSeek provider 没有 SDK trace。
- SDK loop 与自定义 loop 双层编排，没有明确边界文档。

### P1：建议近期修

- 把 `score_resume` 以一个公开工具注册到 `RESUME_TOOL_CATALOG`，并放入至少 `read_only` profile；是否放进 `resume_edit` 需要用现有 trajectory/runtime tests 重新确认。
- 明确 DeepSeek trace 降级策略：本地日志字段、trace id 替代、无法进入 OpenAI dashboard 的原因。
- 给 SDK event -> backend event -> frontend event 补协议文档和 contract tests。

### P2：架构整理

- 拆 `useStreamingChat.ts` 的协议 reducer。
- 把历史消息和 live stream 的工具事件渲染收敛到一个组件。
- 评估是否把 fact/quality guardrail 接入 SDK guardrail 或 tool guardrail，至少让 guardrail result 进入 trace metadata。

## 验证结果

已运行：

```bash
cd backend && uv run pytest tests/test_resume_agent_runtime_boundaries.py tests/test_agent_trajectory.py tests/test_resume_score.py tests/test_eval_openai_agents_standard.py tests/test_excellent_resume_eval_runner.py tests/test_final_resume_quality.py -q
```

结果：`103 passed, 1 warning`。

```bash
cd backend && uv run basedpyright app/runtime/openai_agents_adapter.py app/agents/resume/agent_loop.py app/agents/resume/tool_execution.py app/agents/resume/turn_context.py app/services/agent/resume_agent_stream_service.py
```

结果：`0 errors, 0 warnings, 0 notes`。

```bash
cd frontend && npm run type-check
```

结果：通过。

一次误用命令：

```bash
cd frontend && npm test -- --runTestsByPath src/hooks/useStreamingChat.test.ts || npm run typecheck
```

结果：失败，因为项目没有 `typecheck` 脚本，实际脚本是 `type-check`。随后已用正确命令通过。

## 最终判断

如果问题是“当前是否已经迁到 OpenAI Agents SDK”：答案是 **是，核心模型/工具/streaming/approval 已经走 SDK**。

如果问题是“是否完全符合 OpenAI Agents SDK 最佳实践”：答案是 **还没有**。当前更准确的表述是：

> 这是一个以 OpenAI Agents SDK 作为模型、工具、streaming 和 approval 内核的 Resume Agent，但为了保留产品级 ReAct 可见性、简历持久化和确认 UI，外层仍自管 loop/session/protocol。它具备工业化雏形，但距离“SDK 最佳实践完全闭环”还差工具能力边界、trace 一致性、guardrail 接入和协议文档四块。
