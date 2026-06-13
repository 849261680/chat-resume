# 简历优化 Agent 与 OpenAI Agents SDK 最佳实践审计报告

审计时间：2026-06-12
范围：当前简历优化 Agent 的后端 runtime、工具执行、人工确认、session/恢复、eval/trace/observability，以及前端 SSE/HITL 交互。

## 结论

当前简历优化 Agent **部分符合** OpenAI Agents SDK 最佳实践：后端已经真实使用 `openai-agents`、`Agent`、`Runner.run_streamed()`、`FunctionTool`、`needs_approval`、`RunState` 恢复、`RunConfig` trace 字段和 streaming delta；前端也能消费 SSE、展示工具确认卡、提交确认/拒绝/反馈，并恢复待确认 session。

但它不是一个“完全 SDK 托管”的 Agents SDK 应用。项目仍保留自定义 `ResumeAgentLoop`、`pi_agent_core` 消息协议和应用自管 session/event store。这是合理的产品选择，因为本项目需要可见 ReAct loop、工具确认和简历持久化；但从 SDK 最佳实践角度，仍有几个明显缺口：

1. DeepSeek provider 分支主动 `tracing_disabled=True`，导致非 OpenAI provider 下没有 SDK trace。
2. 自定义 ReAct loop 与 SDK 自带 turn/tool loop 并存，边界复杂，后续维护成本高。
3. 前端 streaming/HITL 状态集中在一个大 hook 和编辑页中，功能完整但协议边界不够清晰。
4. eval 产物兼容 OpenAI Agents 形状，但还不是完整的平台化 eval/trace 运行闭环。

## 官方最佳实践基线

官方文档给出的关键判断标准：

- Agents 是会计划、调用工具、协作并保留足够状态完成多步任务的应用；当应用拥有编排、工具执行、审批和状态时，应使用 Agents SDK。见 OpenAI API Agents SDK guide: https://developers.openai.com/api/docs/guides/agents
- Function tool 应有清晰名称、详细 description、参数说明、enum/对象结构和 strict schema；工具数量应尽量小，OpenAI 建议单轮初始可用函数软目标少于 20，并把总是连续调用的函数合并。见 OpenAI Function calling guide: https://developers.openai.com/api/docs/guides/function-calling
- `Agent` 应以 instructions、tools、handoffs、guardrails 和 structured outputs 组织；如果想自己拥有 loop，则应清楚知道是在绕过 SDK 默认编排。见 Agents docs: https://openai.github.io/openai-agents-python/agents/
- 工具应通过 SDK 工具模型暴露，敏感工具应使用 human-in-the-loop approval，审批中断后可通过 `RunState` 序列化/恢复。见 Tools/HITL docs: https://openai.github.io/openai-agents-python/tools/ 和 https://openai.github.io/openai-agents-python/human_in_the_loop/
- streaming 应使用 `Runner.run_streamed()` 并持续消费 `stream_events()` 直到 iterator 结束；结束前不能假设 run 完成。见 Streaming/Results docs: https://openai.github.io/openai-agents-python/streaming/ 和 https://openai.github.io/openai-agents-python/results/
- tracing 默认开启，覆盖 LLM generations、tool calls、handoffs、guardrails 和 custom events；`RunConfig` 支持 workflow/trace/group/metadata 等字段。见 Tracing docs: https://openai.github.io/openai-agents-python/tracing/
- Anthropic tool-use 文档要求 tool description 明确说明做什么、何时用/不用、每个参数含义和限制；复杂入参可加 examples；相关操作应合并成更少但能力更完整的工具，以减少选择歧义。见 Claude Define tools: https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
- Anthropic 工程实践进一步强调：少量面向高价值工作流的工具优于简单 API 包装；工具必须有清晰且互斥的目的；过多或重叠工具会分散 agent 策略；工具名称可用 namespace/prefix 表达任务边界；工具响应应只返回高信号上下文和可操作错误。见 Writing effective tools for AI agents: https://www.anthropic.com/engineering/writing-tools-for-agents

## 工具名称与合并拆分审计

### 当前公开工具面

`RESUME_TOOL_CATALOG` 当前暴露 17 个工具，`resume_edit` profile 全量可见，`read_only` profile 只暴露 `ask_user`、JD 读取和记忆读取：

```text
ask_user
update_summary
update_profile
upsert_job_application
add_resume_item
remove_resume_item
update_item_fields
update_skills
show_section
hide_section
update_overview
update_bullet
add_bullet
remove_bullet
list_job_posts
read_job_post
read_memory
update_memory
```

这个数量低于 OpenAI “少于 20 个初始函数”的软建议，且比历史工具面更干净：`evaluate_bullet` 已删除，`read_resume` 未注册，`add_highlight`/`update_highlight`/`remove_highlight` 没有暴露为工具名。当前简历全文通过 `prompt_context.py` 注入，不需要运行时 `read_resume`；单条质量判断已由 final quality gate、trajectory/eval 和工具反馈承担，不再需要单独 `evaluate_bullet` 工具。

### 命名规则审计

- **动词 + 业务对象基本成立。** `update_bullet`、`add_bullet`、`remove_bullet`、`update_item_fields`、`add_resume_item`、`remove_resume_item` 都直接表达动作和对象，符合 OpenAI/Anthropic 对“工具名可被模型按自然任务路由”的要求。
- **读写边界清楚。** `list_job_posts`/`read_job_post`/`read_memory` 是只读；`update_memory` 是长期记忆写入；简历正文写入工具都不是 auto execute，仍走 human-in-the-loop approval。
- **历史术语已收敛。** 代码和 schema 采用 `bullet`，只在 `RESUME_TOOL_ARGUMENT_ALIASES` 保留 `highlight_id -> bullet_id` 兼容旧模型输出。这比继续暴露 highlight 别名更好，因为重复工具名会制造选择歧义。
- **profile 目前像粗 namespace。** 当前没有使用 OpenAI namespace 对象或 Anthropic MCP prefix，但 `resume_edit`/`read_only` profile 已经把读写能力分层。由于只有 17 个工具，暂时不需要引入 `resume_*` 前缀；若后续接入更多外部系统，再考虑 `resume_update_bullet`、`memory_read` 这类命名空间。
- **一个维护瑕疵：`update_skills` 对模型暴露 `skills`，handler 内部使用 `items`。** 运行时通过 `RESUME_TOOL_ARGUMENT_ALIASES` 归一化，因此不是 bug；但新贡献者需要知道 schema 名是面向模型语义，handler 名是旧内部字段。若未来再碰该模块，优先把 handler 形参也改成 `skills`，减少认知分裂。

### 合并/拆分判断矩阵

| 工具组 | 当前形态 | 是否调整 | 理由 |
| --- | --- | --- | --- |
| `update_skills` | 一个工具覆盖新增、替换、合并、删除分类，靠 `mode` 区分 | 保持合并 | 技能分类增删改共享同一对象和参数，用户意图也常是“调整技能板块”；合并符合 Anthropic “相关操作用 action/mode 收敛”的建议，并已用 schema/test 锁住。 |
| `add_resume_item` / `update_item_fields` / `remove_resume_item` | 三个条目级工具 | 保持拆分 | 新增、修改字段、删除整条经历的风险和必填参数不同；删除需要更明确的用户意图和确认。若合并成 `manage_resume_item(action=...)`，会把 `fields`、`item_id`、删除语义塞进一个大 schema，反而增加误删和参数组合错误。 |
| `add_bullet` / `update_bullet` / `remove_bullet` | 三个 bullet 级工具 | 保持拆分 | 本项目 eval/quality_judge 明确检查新增、改写、删除意图是否匹配工具。拆分能让错误调用更可观测，也让删除独立走确认；合并会削弱轨迹质量判断。 |
| `show_section` / `hide_section` | 两个可见性工具 | 保持拆分 | 这两个工具只改显示开关，不改内容。虽然可合并为 `set_section_visibility(visible)`，但当前名称对模型和前端展示都更直观，且无证据显示选择歧义。若未来工具数膨胀，可作为低风险合并候选。 |
| `update_summary` / `update_profile` / `upsert_job_application` | 三个顶层上下文工具 | 保持拆分 | 三者写入位置、事实来源和用户风险不同：summary 是简历正文，profile 含身份联系方式，job_application 是目标上下文非正文。拆分有利于审批和事实边界。 |
| `update_overview` vs `update_item_fields` | overview 既可作为项目字段，也有专用工具 | 暂时保留，但列为观察项 | 专用 `update_overview` 限定 `projects`，更贴近“只改项目简介”的高频意图；`update_item_fields` 是泛化字段工具。这里有轻微重叠，但 prompt 已明确“只改项目简介用 overview，不改 bullet”。如果后续工具选择 eval 显示混淆，再把 overview 合并进 `update_item_fields`。 |
| `list_job_posts` / `read_job_post` | 先列再读 | 暂时保留，不合并 | Anthropic 倾向 search over list，但当前数据规模和用户体验需要先展示已保存 JD 摘要，再读取完整 JD。若 JD 数量变大，应升级为 `search_job_posts(query, limit, include_full_text)`，减少连续调用。 |
| `read_memory` / `update_memory` | 读写分开 | 保持拆分 | 长期记忆写入风险高于读取，且 `update_memory` 只允许记录用户明说内容；拆分能让审批/审计更清晰。 |
| `ask_user` | 人类输入工具 | 保持独立 | 这是事实缺口和用户确认的交互边界，不应和任何编辑工具合并。 |
| `evaluate_bullet` | 已删除 | 不恢复 | 评分/评价如果只是给模型内部参考，会增加工具数和回合数；当前更适合放在质量门禁、eval 或工具失败反馈中。 |
| `read_resume` | 未暴露 | 不恢复 | 当前简历已经完整注入 prompt；恢复只读工具会浪费一次工具调用并可能制造“先 read_resume 再改”的低效策略。 |

### 当前结论

当前工具设计总体符合“少量、清晰、面向工作流”的方向：读写能力分层，危险写入经过确认，公开工具数可控，历史别名基本删除，技能工具已正确合并。不要为了追求表面上的少工具数，把 bullet 或经历条目工具强行合并；这会牺牲用户意图可观测性、删除风险隔离和现有 eval 的判断能力。

近期最值得做的不是再合并，而是补三类验证：

1. 为 `update_overview` 与 `update_item_fields` 增加 trajectory/eval case，确认“只改项目简介”不会误走泛化字段工具。
2. 为 `update_skills(skills=...)` 的 schema 参数路径增加 SDK 原生工具回归测试，证明别名归一化覆盖 streaming/HITL 路径。
3. 记录每次 run 的 `tool_names`、`tool_call_count`、`guardrail_rejected_count`、`unexpected_tool_call_names`，用真实日志判断是否存在工具选择混淆，再决定是否合并可见性或 JD 工具。

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

1. **DeepSeek 分支没有 SDK trace。**
   - 证据：`provider_run_config()` 对 DeepSeek `RunConfig(..., tracing_disabled=True)`。
   - 影响：官方 tracing 最佳实践强调开发和生产中用 trace 调试、可视化和监控 workflow。当前 OpenAI provider 可用 trace 配置，DeepSeek provider 只能靠本地日志。
   - 说明：如果 DeepSeek 无法上传 OpenAI trace，这是工程上可接受的 provider 限制，但报告/README 应明确它是降级模式，不应宣称所有 provider 都具备 OpenAI 平台 trace。

2. **SDK loop 与自定义 ReAct loop 双层编排。**
   - 证据：`OpenAIAgentsStreamBridge` 内部运行 SDK 的 tool loop；外层 `ResumeAgentLoop.run()` 又按 assistant message -> tool call -> tool result 继续循环。
   - 优点：保留了产品需要的可见 ReAct、确认卡、业务日志和简历持久化。
   - 风险：SDK 已经管理 turn/tools/approvals/sessions 的一部分，外层又复制一次协议，后续 SDK 事件结构升级时，容易出现重复工具卡、漏关 pending、文本重复 flush、usage/trace 不一致。

3. **没有使用 SDK Agent-level guardrails。**
   - 当前 guardrail 主要在 prompt、工具 dry-run、final_resume_quality 和 trajectory eval 中实现。
   - 这能覆盖事实边界，但不等于 SDK `input_guardrails` / `output_guardrails` / tool guardrails。尤其是用户输入安全、最终输出事实校验、每次工具调用前后的统一 guardrail metadata 没有进入 SDK guardrail result。

4. **SDK Session/RunState 持久化只用于单次 streaming approval loop，跨请求仍由应用自管。**
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
- 质量门禁主要存在于 eval 与 final quality gate，尚未形成平台化 eval/trace 运行闭环。

## 风险分级

### P0：当前不应称为完全符合

- DeepSeek provider 没有 SDK trace。
- SDK loop 与自定义 loop 双层编排，没有明确边界文档。

### P1：建议近期修

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
