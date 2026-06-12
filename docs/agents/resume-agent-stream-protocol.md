# Resume Agent Stream Protocol

用于固定 `OpenAI Agents SDK event -> 后端 runtime event -> HTTP SSE -> 前端 StreamEvent` 的公开协议。以后改 streaming、工具确认或 session 恢复时，先改这张表和 contract tests，再改实现。

## Event Chain

| Layer | Owner | Contract surface |
| --- | --- | --- |
| SDK stream | `backend/app/runtime/openai_agents_adapter.py` | `response.output_text.delta` 被转成 `StreamTextDeltaEvent(delta=...)`。 |
| ReAct loop | `backend/app/agents/resume/agent_loop.py` / `tool_execution.py` | 文本 delta、工具调用、工具确认和工具结果被转成 `ResumeStreamEvent`。 |
| SSE payload | `backend/app/entrypoints/http/resume_agent.py` | 每个公开事件通过 `format_sse_event()` 输出 `id: <session_id>:<sequence>` 和 JSON `data:`。 |
| Frontend protocol | `frontend/src/hooks/streamingEventProtocol.ts` | SSE JSON 被转成 `StreamEvent`，再由 `useStreamingChat.ts` 更新 UI 状态。 |

## Public SSE Events

| SSE `event_type` | Required fields | Frontend event | Notes |
| --- | --- | --- | --- |
| `session_started` | `session_id`, `event_id`, `done:false` | no `StreamEvent`; stores active session id | First public event of a new stream. |
| `text_delta` | `content`, `event_id`, `done:false` | `{ type:"text", content }` | Comes from SDK text delta. The frontend merges adjacent text events for rendering. |
| `tool_call` | `call_id`, `tool_id` or `tool_name`, `tool_call_started:true`, `event_id` | `{ type:"tool_call", callId, toolName, toolId, toolInput }` | `ask_user` tool calls are hidden until `user_input_request`. |
| `tool_pending` | `call_id`, `tool_id`, `tool_pending:true`, `diff_summary`, `diff_items`, `event_id` | `{ type:"tool_pending", callId, toolName, toolId, diffSummary, diffItems }` | Pauses the visible Agent loop until user confirms or rejects. |
| `tool_confirmed` | `call_id`, `tool_confirmed:true`, `result`, `event_id` | pending event becomes `{ type:"tool_confirmed", ... }` | Internal `context` must not be sent to the browser. |
| `tool_rejected` | `call_id`, `tool_rejected:true`, `result`, `event_id` | pending event becomes `{ type:"tool_rejected", ... }` | Same lifecycle as confirmed, but no mutation should be applied. |
| `tool_call_failed` | `call_id`, `tool_call_failed:true`, `display_message`, `event_id` | `{ type:"tool_failed", callId, toolName, displayMessage }` | Used for failed tool execution. |
| `tool_result` | `result`, `event_id`, optional `call_id` | `{ type:"tool_result", callId?, toolName, displayMessage }` | Completes an already visible tool call when `call_id` is present. |
| `user_input_request` | `user_input_request.question`, non-empty `options`, `event_id` | `{ type:"user_input_request", request }` | Public form of `ask_user`; invalid empty question/options are ignored by frontend. |
| `done` | `done:true`, `event_id`, optional `resume_content` or `error` | completes stream | `resume_content` refreshes preview; `error` is shown through `onError`. |

## Cursor And Replay

Every persisted public event gets `event_id = "<session_id>:<sequence>"`. The HTTP layer also writes that value into the SSE `id:` line. On reconnect, the frontend sends `Last-Event-ID`; the backend parses it with `parse_sse_event_id()` and replays persisted events after that sequence.

The JSON `event_id` field and SSE `id:` line must stay equivalent. The frontend accepts either source and updates its replay cursor.

## Contract Tests

| Contract | Test file |
| --- | --- |
| SDK text delta can become public SSE `text_delta` payload | `backend/tests/test_resume_agent_stream_protocol.py` |
| Tool pending/confirmed/user input payload fields stay stable | `backend/tests/test_resume_agent_stream_protocol.py` |
| SSE `id:` / `Last-Event-ID` cursor replay stays stable | `backend/tests/test_resume_agent_sse_cursor.py` |
| Frontend maps SSE payloads to `StreamEvent` consistently | `frontend/src/hooks/streamingEventProtocol.test.mjs` |

Run:

```bash
cd backend && uv run pytest tests/test_resume_agent_stream_protocol.py tests/test_resume_agent_sse_cursor.py -q
cd frontend && node --experimental-strip-types --test src/hooks/streamingEventProtocol.test.mjs
cd frontend && npm run type-check
```
