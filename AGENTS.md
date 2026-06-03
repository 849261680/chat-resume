## 项目概述
一个 Agent 驱动的简历优化和模拟面试网站

## 本地日志
- 当你需要程序的报错信息和性能信息时，请阅读 `backend/logs/backend.log`。

- 回答前先说老大好

- 工作流：
每次回答前，按顺序自检——①
先说老大好 → ② 改代码前先 bd 建/认领任务 + Agent Mail
预约文件 → ③ 改完给验收方法 → ④ 收尾提交推送。


# 开发规则

- 测试驱动开发，在构建功能时，先打造一个微小的、端到端的功能切片，寻求反馈，然后在此基础上逐步扩展。 曳光弹的概念源自《程序员修炼之道》。在构建系统时，你希望编写能尽快获得反馈的代码。曳光弹是贯穿系统所有层的小功能切片，让你能尽早测试和验证方法。这有助于识别潜在问题，并确保在投入大量开发时间之前，整体架构是稳健的。

- 解决问题信息不足时请添加日志，获取足够的错误信息来调试。

- 遇到第三方库、SDK、CLI 的真实行为不确定时，优先用 `opensrc path <package>` 获取源码路径，再用 `rg`、`cat`、`find` 阅读实现；不要只凭记忆或类型定义猜测库行为。例如：`rg "parse" $(opensrc path zod)`、`cat $(opensrc path pypi:requests)/src/requests/sessions.py`。

- 代码嵌套不能超过3层

- 每一个模块和函数都要写一个简短的注释来注明其功能

- 写简单易读的代码，复杂代码是错误的代码。如果需要大段注释才能解释一段逻辑，说明这段逻辑需要重写。

- 先思考再编码,明确你的假设。不确定时提问，切勿猜测。

- 简洁至上,编写解决该问题所需的最简代码。不要添加没人要求的抽象层。

- 精准修改,不要改动与需求无关的代码。每一处修改都必须追溯到最初的要求。

- 目标驱动的执行,将模糊的指令转化为可验证的成功标准,在写任何一行代码之前。

- 死代码和不必要的代码需要删除

- uv管理虚拟环境

- 不要用RUFF,BLACK,LINT

- 后端使用basedpyright 进行类型检查

- 每次进行一次修改后都要告诉用户如何验收并检查改动后的正确性

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads 任务追踪器

本项目使用 **bd (beads)** 做任务追踪。运行 `bd prime` 查看完整工作流上下文和命令。
beads要用中文写

### 快速参考

```bash
bd ready              # 查找可开始的任务
bd show <id>          # 查看任务详情
bd update <id> --claim  # 认领任务
bd close <id>         # 完成任务
```

### 规则

- 所有任务追踪都使用 `bd`，不要使用 TodoWrite、TaskCreate 或 Markdown TODO 列表
- 运行 `bd prime` 查看详细命令参考和会话收尾协议
- 使用 `bd remember` 保存持久知识，不要使用 MEMORY.md 文件

**一句话架构：** 任务存放在本地 Dolt 数据库中；同步使用 Git 远端的 `refs/dolt/data`；`.beads/issues.jsonl` 只是被动导出文件。细节和反模式见 https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md。

## 会话收尾

**结束一次工作会话时**，必须完成下面所有步骤。只有 `git push` 成功后，工作才算完成。

**强制工作流：**

1. **为剩余工作创建任务** - 所有需要后续处理的事项都要创建任务
2. **运行质量门禁**（如果改了代码）- 测试、类型检查、构建
3. **更新任务状态** - 关闭已完成任务，更新进行中的任务
4. **推送到远端** - 这是强制要求：
   ```bash
   git pull --rebase
   git push
   git status  # 必须显示已与 origin 同步
   ```
5. **清理** - 清理 stash，清理不再需要的远端分支
6. **验证** - 所有改动都已提交并推送
7. **交接** - 为下一次会话提供上下文

**关键规则：**
- `git push` 成功之前，工作不算完成
- 推送前绝不停止，否则改动会滞留在本地
- 不要说“你准备好了我再推送”，你必须完成推送
- 如果推送失败，解决问题并重试，直到成功
<!-- END BEADS INTEGRATION -->

### 把 bv 作为 AI 辅助工具

bv 是面向 Beads 项目（`.beads/beads.jsonl`）的图感知分诊引擎。不要自己解析 JSONL，也不要凭空推测图遍历结果；使用 robot 参数可以得到确定性的、依赖感知的输出，并包含预计算指标（PageRank、中介中心性、关键路径、环、HITS、特征向量、k-core）。

**职责边界：** bv 负责判断*该做什么*（分诊、优先级、规划）。Agent 之间的协作（消息、任务认领、文件预约）使用 [MCP Agent Mail](https://github.com/Dicklesworthstone/mcp_agent_mail)。

**⚠️ 重要：只使用 `--robot-*` 参数。裸跑 `bv` 会启动交互式 TUI，并阻塞当前会话。**

#### 工作流：从分诊开始

**`bv --robot-triage` 是统一入口。** 它一次调用就返回所需信息：
- `quick_ref`：总览计数和前 3 个推荐项
- `recommendations`：可执行事项排序，包含分数、原因和解除阻塞信息
- `quick_wins`：低成本、高影响的事项
- `blockers_to_clear`：能解除最多下游阻塞的事项
- `project_health`：状态、类型、优先级分布和图指标
- `commands`：可直接复制执行的下一步 shell 命令

bv --robot-triage        # 入口命令：从这里开始
bv --robot-next          # 最小输出：只返回一个最高优先级任务和认领命令

# 面向低 LLM 上下文消耗的 token 优化输出（TOON）：
bv --robot-triage --format toon
export BV_OUTPUT_FORMAT=toon
bv --robot-next

认领前，用 `br show <id> --json` 或 `br ready --json` 验证当前 bead 状态。`recommendations` 可能包含图上重要但已阻塞或已分配的工作；只有 `quick_ref.top_picks` 和非空 `claim_command` 字段才表示可认领工作。

#### 其他命令

**规划：**
| 命令 | 返回内容 |
|---------|---------|
| `--robot-plan` | 并行执行轨道，以及 `unblocks` 列表 |
| `--robot-priority` | 优先级错配检测和置信度 |

**图分析：**
| 命令 | 返回内容 |
|---------|---------|
| `--robot-insights` | 完整指标：PageRank、中介中心性、HITS（枢纽/权威）、特征向量、关键路径、环、k-core、割点、松弛量 |
| `--robot-label-health` | 按标签统计健康度：`health_level`（healthy\|warning\|critical）、`velocity_score`、`staleness`、`blocked_count` |
| `--robot-label-flow` | 跨标签依赖：`flow_matrix`、`dependencies`、`bottleneck_labels` |
| `--robot-label-attention [--attention-limit=N]` | 按 `(pagerank × staleness × block_impact) / velocity` 排序的标签关注度 |

**历史与变更追踪：**
| 命令 | 返回内容 |
|---------|---------|
| `--robot-history` | bead 与 commit 的关联：`stats`、`histories`（每个 bead 的事件/提交/里程碑）、`commit_index` |
| `--robot-diff --diff-since <ref>` | 自指定 ref 以来的变化：新增/关闭/修改的 issue，引入/解决的环 |

**其他命令：**
| 命令 | 返回内容 |
|---------|---------|
| `--robot-burndown <sprint>` | 迭代燃尽、范围变化、有风险事项 |
| `--robot-forecast <id\|all>` | 依赖感知排期下的预计完成时间预测 |
| `--robot-alerts` | 陈旧 issue、阻塞级联、优先级错配 |
| `--robot-suggest` | 卫生检查：重复项、缺失依赖、标签建议、环路打断建议 |
| `--robot-graph [--graph-format=json\|dot\|mermaid]` | 导出依赖图 |
| `--export-graph <file.html>` | 自包含的交互式 HTML 可视化 |

#### 范围与过滤

bv --robot-plan --label backend              # 限定到该标签的子图
bv --robot-insights --as-of HEAD~30          # 历史时间点分析
bv --recipe actionable --robot-plan          # 预过滤：可开始工作（无阻塞）
bv --recipe high-impact --robot-triage       # 预过滤：PageRank 高分任务
bv --robot-triage --robot-triage-by-track    # 按并行工作流分组
bv --robot-triage --robot-triage-by-label    # 按领域分组

#### 理解 robot 输出

**所有 robot JSON 都包含：**
- `data_hash`：源 beads.jsonl 的指纹（用于验证多次调用的一致性）
- `status`：每个指标的状态：`computed|approx|timeout|skipped` + 耗时毫秒
- `as_of` / `as_of_commit`：使用 `--as-of` 时出现，包含 ref 和解析后的 SHA

**两阶段分析：**
- **阶段 1（即时）：** 度数、拓扑排序、密度，总是立即可用
- **阶段 2（异步，500ms 超时）：** PageRank、中介中心性、HITS、特征向量、环；需要检查 `status` 标记

**大型图（超过 500 个节点）：** 部分指标可能被近似计算或跳过。务必检查 `status`。

#### jq 快速参考

bv --robot-triage | jq '.quick_ref'                        # 总览摘要
bv --robot-triage | jq '.recommendations[0]'               # 最高推荐项
bv --robot-plan | jq '.plan.summary.highest_impact'        # 最佳解除阻塞目标
bv --robot-insights | jq '.status'                         # 检查指标就绪状态
bv --robot-insights | jq '.Cycles'                         # 环形依赖（必须修复）
bv --robot-label-health | jq '.results.labels[] | select(.health_level == "critical")'

**性能：** 阶段 1 即时返回，阶段 2 异步执行（500ms 超时）。如果速度更重要，优先用 `--robot-plan`，不要用 `--robot-insights`。结果按 data hash 缓存。

使用 bv，不要自己解析 beads.jsonl；它会确定性地计算 PageRank、关键路径、环和并行轨道。


## MCP Agent Mail：多 Agent 工作流协作
- 改动前请使用AGENT MAIL预约文件以避免冲突

它是什么
- 一个类似邮件的协作层，让编码 Agent 通过 MCP 工具和资源异步协作。
- 提供身份、收件箱/发件箱、可搜索线程和建议式文件预约，并把人类可审计的产物保存在 Git 中。

为什么有用
- 通过对文件或 glob 显式做文件预约（租约），避免多个 Agent 互相覆盖改动。
- 把消息存入每个项目的归档中，避免把沟通内容长期塞进 token 上下文。
- 提供快速读取资源（`resource://inbox/...`、`resource://thread/...`）和封装常见流程的宏命令。

如何有效使用
1) 同一个仓库
   - 注册身份：调用 `ensure_project`，然后用本仓库绝对路径作为 `project_key` 调用 `register_agent`。
   - 编辑前预约文件：调用 `file_reservation_paths(project_key, agent_name, ["src/**"], ttl_seconds=3600, exclusive=true)` 表明意图并避免冲突。
   - 用线程沟通：使用 `send_message(..., thread_id="FEAT-123")`；用 `fetch_inbox` 检查收件箱，用 `acknowledge_message` 确认收悉。
   - 快速读取：使用 `resource://inbox/{Agent}?project=<abs-path>&limit=20&agent_token=<registration_token>` 或 `resource://thread/{id}?project=<abs-path>&agent=<Agent>&agent_token=<registration_token>&include_bodies=true`。如果当前 MCP 会话已经以该 Agent 身份认证，则不需要再带 token。
   - 提示：在环境变量里设置 `AGENT_NAME`，这样提交前防护可以阻止与其他 Agent 的活跃独占文件预约冲突的提交。

2) 同一个项目里的不同仓库（例如 Next.js 前端 + FastAPI 后端）
   - 方案 A（单项目总线）：两边都注册到同一个 `project_key`（共享 key/路径）。预约模式要保持具体，例如 `frontend/**` 和 `backend/**`。
   - 方案 B（独立项目）：每个仓库使用自己的 `project_key`；通过 `macro_contact_handshake` 或 `request_contact`/`respond_contact` 连接 Agent，然后直接发消息。跨仓库使用共享的 `thread_id`（例如任务编号），便于汇总和审计。

宏与细粒度工具
- 想要更快执行或使用较小模型时，优先使用宏：`macro_start_session`、`macro_prepare_thread`、`macro_file_reservation_cycle`、`macro_contact_handshake`。
- 需要更强控制时，使用细粒度工具：`register_agent`、`file_reservation_paths`、`send_message`、`fetch_inbox`、`acknowledge_message`。

常见问题
- “from_agent not registered”：表示发送方 Agent 未注册。一定要先在正确的 `project_key` 下执行 `register_agent`。
- “FILE_RESERVATION_CONFLICT”：调整路径模式，等待租约过期，或在合适时使用非独占预约。
- 认证错误：如果启用了 JWT+JWKS，请携带 bearer 令牌，并确保其中的 `kid` 与服务器 JWKS 匹配；只有在 JWT 禁用时才使用静态 bearer。


## 与 Beads 集成（依赖感知的任务规划）

Beads 提供轻量、依赖感知的 issue 数据库和 CLI（`bd`），用于选择“可开始工作”、设置优先级和追踪状态。它补充 MCP Agent Mail 的消息沟通、审计记录和文件预约信号。项目：[steveyegge/beads](https://github.com/steveyegge/beads)

推荐约定
- **单一事实来源**：使用 **Beads** 管理任务状态、优先级和依赖；使用 **Agent Mail** 记录对话、决策和附件（审计）。
- **共享标识符**：使用 Beads issue id（例如 `bd-123`）作为 Mail 的 `thread_id`，并在消息主题前加上 `[bd-123]`。
- **文件预约**：开始 `bd-###` 任务时，对受影响路径调用 `file_reservation_paths(...)`；在 `reason` 中包含 issue id，并在完成后释放预约。

典型流程（Agent）
1) **选择可开始工作**（Beads）
   - `bd ready --json` → 选择一个条目（最高优先级、无阻塞）
2) **预约编辑范围**（Mail）
   - `file_reservation_paths(project_key, agent_name, ["src/**"], ttl_seconds=3600, exclusive=true, reason="bd-123")`
3) **宣布开始**（Mail）
   - `send_message(..., thread_id="bd-123", subject="[bd-123] Start: <short title>", ack_required=true)`
4) **执行并更新**
   - 在线程内回复进展，并附加产物或图片；每个 issue id 的讨论保持在同一个线程中
5) **完成并释放**
   - `bd close bd-123 --reason "Completed"`（Beads 是状态权威）
   - `release_file_reservations(project_key, agent_name, paths=["src/**"])`
   - 最后一封 Mail 回复：`[bd-123] Completed`，包含摘要和链接

映射速查
- **Mail `thread_id`** ↔ `bd-###`
- **Mail 主题**：`[bd-###] …`
- **文件预约 `reason`**：`bd-###`
- **Commit message（可选）**：包含 `bd-###`，便于追踪

事件镜像（可选自动化）
- 当执行 `bd update --status blocked` 时，在 `bd-###` 线程中发送一条高重要性 Mail，说明阻塞原因。
- 当关键决策出现 Mail “ACK overdue” 时，给 Beads 添加标签（例如 `needs-ack`）或提高优先级，让它在 `bd ready` 中浮现。

避免踩坑
- 不要在 Mail 中创建或管理任务；把 Beads 视为唯一任务队列。
- 始终在消息 `thread_id` 中包含 `bd-###`，避免不同工具之间的 ID 漂移。
