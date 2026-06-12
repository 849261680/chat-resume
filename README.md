# Chat Resume 

[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/849261680/chat-resume)

Chat Resume 是一个展示 Agent 工程能力的 AI 求职工作台：从上传简历、解析目标 JD、结构化工具调用、用户确认式 diff 修改，到导出和语音模拟面试，串成一条完整求职闭环。

- OpenAI Agents SDK 驱动的 ReAct runtime
- 结构化 tool calling
- Human-in-the-loop diff confirmation gate
- SSE 流式工具事件
- Session replay / resume
- Agent eval
- Agent observability

## 核心能力

- 简历上传解析：支持 PDF、DOC、DOCX、TXT，后台解析后生成结构化简历。
- 简历编辑工作台：结构化编辑、实时预览、自动保存、布局配置、一页适配和导出。
- JD 管理：保存目标公司、目标岗位和 JD 文本，支持 JD 图片 OCR。
- Resume Agent：基于当前简历、目标 JD 和对话上下文进行 ReAct 式工具调用。
- 用户确认式改写：所有修改类工具先展示 diff，用户确认后才写入简历。
- JD 匹配摘要：同一个工具返回命中关键词、缺失关键词、已确认改动、待补充事实提示和优先补强 Top gaps。
- 模拟面试：基于简历和目标岗位创建语音面试 session，保存问答并生成报告。
- Agent eval：提供评估用例和评分脚本，用于检查关键词提升、工具调用正确性和决策规则。

## 主要用户流程

```text
上传/创建简历
  -> 结构化编辑
  -> 填写或识别 JD
  -> Resume Agent 分析匹配
  -> 工具调用生成匹配摘要 / Top gaps / 修改 diff
  -> 用户确认后应用修改
  -> 预览、一页适配、导出
  -> 基于简历进入模拟面试
```

## Why this is an Agent system

LLM 不能直接修改简历数据，只能通过受约束的工具提出结构化变更。

```text
Observe
  -> 读取当前简历、目标 JD、聊天历史和已确认 diff
Reason
  -> 判断用户想咨询、分析匹配度，还是实际修改简历
Act
  -> 调用只读分析工具或修改类工具
Confirm
  -> 修改类工具先在 preview context 上执行，生成 diff 等待用户确认
Persist
  -> 用户确认后才在真实 resume_content 上执行并写入数据库
Replay
  -> SSE 连接中断后，可通过 session event cursor 回放并恢复
```

Agent 的输出不是“自然语言声称已修改”。只有真实工具调用成功，并通过确认门后，简历内容才会被写入。

## Agent 工具

当前 Resume Agent 的工具分为只读分析和写入修改两类。

只读工具会自动执行：

- `generate_job_match_summary`：生成岗位匹配摘要，返回 `matched_keywords`、`missing_keywords`、`resume_changes`、`fact_gaps` 和 `top_gaps`。

修改工具需要用户确认：

- `update_summary`：更新个人总结，调整整份简历的职业定位和核心能力摘要。
- `update_profile`：更新个人信息中的求职定位、headline、地点和公开链接；不修改姓名、邮箱、电话。
- `upsert_job_application`：创建或更新目标公司、目标岗位和 JD。
- `update_item_fields`：更新工作、项目、教育条目的非 bullet 字段，例如职位、项目简介、角色、技术栈、学历字段。
- `update_skills`：更新技能分类名称和技能列表，支持替换或合并。
- `add_resume_item`：新增工作、项目、教育、技能、语言或自定义条目；必须提供用户明确事实来源。
- `remove_resume_item`：删除已有工作、项目、教育、技能、语言或自定义条目。
- `update_overview`：更新项目简介。
- `update_bullet`：更新已有要点。
- `add_bullet`：新增要点。
- `remove_bullet`：删除要点。

每个修改工具都会返回结构化 diff，包括修改前、修改后和修改原因。前端展示确认卡，用户接受后才应用到简历。

## JD 匹配能力边界

当前 JD 匹配是轻量关键词、证据链和能力缺口归并，不是完整语义匹配模型。

它会：

- 从 JD 中提取中英文关键词。
- 排除 JD 字段后，在简历正文中判断命中和缺失。
- 汇总本轮已确认 diff，说明已经补强了哪些表达。
- 把零散缺失关键词归并成 2-3 个能力缺口，例如 RAG 落地经验、Agent 工具调用与工作流编排、工程基础设施经验。

它当前不会：

- 证明用户真实做过某项缺失能力。
- 编造简历里没有证据支撑的经历。

## Reliability and eval

项目包含三层验证：

- 后端测试覆盖 runtime 边界、session 恢复、工具执行、SSE cursor 和岗位匹配摘要。
- 前端 Playwright 覆盖上传、编辑器工作流、diff confirmation、导出、认证、dashboard、i18n 和面试链路。
- Agent eval 评分工具覆盖工具调用正确性、optimize-first 决策规则、JD 关键词提升和可选 LLM-as-judge。

最近一次本地验收结果：

```text
backend basedpyright: passed
backend key tests: 128 passed
frontend type-check: passed
frontend build: passed
frontend e2e: 55 passed
```

## 系统架构

```text
Frontend (Next.js / React)
  -> FastAPI HTTP API
  -> ResumeAgentStreamService
  -> OpenAI Agents SDK ResumeAgentRuntime
  -> Resume Tools
  -> Tool Confirmation Gate
  -> ResumeService / AgentSessionStore
  -> Database
```

## 技术栈

- 前端：Next.js 16.2、React 18、TypeScript、Tailwind CSS、next-intl
- 后端：FastAPI、SQLAlchemy 2、Pydantic v2、Alembic、uv
- Agent：OpenAI Agents SDK
- 语音：火山引擎实时语音对话
- 测试：pytest、Playwright

## 主要目录

```text
backend/app/entrypoints/http/  # FastAPI 路由
backend/app/agents/resume/     # 简历 Agent 定义和提示词上下文
backend/app/runtime/           # OpenAI Agents SDK 运行时适配、确认和恢复
backend/app/tools/resume/      # 简历工具
backend/app/services/          # 业务服务
backend/app/state/             # Agent session 存储和 SSE 回放
frontend/src/app/              # Next.js 页面
frontend/src/components/       # 前端组件
frontend/src/hooks/            # 页面级业务 hooks
frontend/src/i18n/             # 国际化配置
frontend/locales/              # 中英文翻译文件
eval/                          # Agent eval 脚本和用例
```

## 本地启动

要求：

- Python 3.11+
- Node.js 18+
- uv
- npm

启动前后端：

```bash
./restart.sh
```

默认地址：

- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

单独启动：

```bash
./backend.sh
./frontend.sh
```

## 环境变量

示例文件：

- `backend/.env.example`
- `frontend/.env.example`

本地最少需要：

```bash
# backend/.env
DATABASE_URL=sqlite:///./chat_resume.db
SECRET_KEY=your-secret-key-here
OPENAI_AGENTS_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_AGENTS_MODEL=gpt-5.5
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_THINKING_TYPE=disabled
OPENROUTER_API_KEY=
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_MODEL=deepseek/deepseek-v4-pro
OPENROUTER_JOB_MATCH_MODEL=deepseek/deepseek-v4-pro
OPENROUTER_RESUME_PARSER_MODEL=deepseek/deepseek-v4-pro
FRONTEND_URL=http://localhost:3000
BACKEND_CORS_ORIGINS=http://localhost:3000,https://localhost:3000

# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

将简历优化 Agent 切到 DeepSeek 官方 API 时，设置
`OPENAI_AGENTS_PROVIDER=deepseek`、`OPENAI_AGENTS_MODEL=deepseek-v4-pro`，
并填写 `DEEPSEEK_API_KEY`。该分支使用 OpenAI-compatible Chat Completions，
默认用 `DEEPSEEK_THINKING_TYPE=disabled` 避免工具确认后的 reasoning_content 回放错误。

### Agent 评估

Resume Agent 评估保留本地 `eval/` 跑法，同时输出 OpenAI Agents SDK 标准兼容产物：

- `openai_agents_eval.trace`：写入 SDK `RunConfig.workflow_name`、`trace_id`、`group_id` 和 metadata，真实 OpenAI provider 运行时可在 Traces 中定位。
- `openai_agents_eval.dataset_item`：把本地 case 转成 dataset item 形状，包含输入、期望决策、期望工具、关键词和禁止内容。
- `openai_agents_eval.model_sample`：把 Agent 回复、工具调用和最终简历状态转成 grader sample。
- `openai_agents_eval.grader`：提供 OpenAI Python grader 配置，用于评分决策、工具调用、关键词、禁止内容和回复形态。

普通评估：

```bash
cd backend
uv run python ../eval/run_eval.py --cases TC001 --output ../eval/results/latest.json
```

优秀简历黄金样例：

```bash
cd backend
uv run python ../eval/run_excellent_eval.py --cases excellent-002 --output ../eval/results/excellent_latest.json
```

默认 OpenAI provider 使用 `OPENAI_API_KEY`；切到 `OPENAI_AGENTS_PROVIDER=deepseek`
时使用 `DEEPSEEK_API_KEY`。DeepSeek 兼容分支仍可本地评分，但不会上传 OpenAI 平台 trace。

可选能力按需配置：

- Google 登录：`GOOGLE_OAUTH_CLIENT_ID`、`GOOGLE_OAUTH_CLIENT_SECRET`、`GOOGLE_OAUTH_REDIRECT_URI`
- PayPal 订阅：`PAYPAL_CLIENT_ID`、`PAYPAL_CLIENT_SECRET`、`PAYPAL_PLAN_ID`、`PAYPAL_WEBHOOK_ID`
- 豆包端到端语音面试：`VOLCENGINE_DIALOGUE_*`、`VOLCENGINE_ACCESS_TOKEN`、`VOLCENGINE_TTS_*`

## 数据库

```bash
cd backend
uv run alembic upgrade head
```

## 测试

```bash
# 后端
cd backend
uv run --extra dev python -m pytest tests

# 前端类型检查
cd frontend
npm run type-check

# 前端构建
npm run build

# E2E
npm run e2e
```

## 设计

前端设计规范见 [DESIGN.md](./DESIGN.md)。
