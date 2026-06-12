// Tests the resume Agent SSE payload to frontend event protocol.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const protocol = await import('./streamingEventProtocol.ts')

test('text_delta payload maps to frontend text event', () => {
  assert.deepEqual(
    protocol.streamEventFromSsePayload(
      { event_type: 'text_delta', content: '先改写项目亮点。' },
      'Tool call',
    ),
    { type: 'text', content: '先改写项目亮点。' },
  )
})

test('tool_pending payload keeps confirmation fields', () => {
  assert.deepEqual(
    protocol.streamEventFromSsePayload(
      {
        event_type: 'tool_pending',
        tool_pending: true,
        call_id: 'call_1',
        tool_id: 'update_highlight',
        tool_display_name: 'update_highlight',
        tool_input: { section: 'projects' },
        diff_summary: '更新项目亮点',
        diff_items: [{ before: 1, after: 'new', reason: null }],
      },
      'Tool call',
    ),
    {
      type: 'tool_pending',
      callId: 'call_1',
      toolName: 'update_bullet',
      toolId: 'update_bullet',
      toolInput: { section: 'projects' },
      diffSummary: '更新项目亮点',
      diffItems: [{ before: '1', after: 'new' }],
    },
  )
})

test('tool decision payload maps to confirmed event', () => {
  assert.deepEqual(
    protocol.toolDecisionFromSsePayload(
      {
        event_type: 'tool_confirmed',
        tool_confirmed: true,
        call_id: 'call_1',
        tool_id: 'update_bullet',
        tool_display_name: 'update_bullet',
        diff_summary: '更新项目亮点',
        diff_items: [{ before: 'old', after: 'new' }],
      },
      'Tool call',
    ),
    {
      type: 'tool_confirmed',
      callId: 'call_1',
      toolName: 'update_bullet',
      toolId: 'update_bullet',
      diffSummary: '更新项目亮点',
      diffItems: [{ before: 'old', after: 'new' }],
    },
  )
})

test('user_input_request payload requires a question and options', () => {
  assert.deepEqual(
    protocol.streamEventFromSsePayload(
      {
        event_type: 'user_input_request',
        call_id: 'call_ask',
        tool_display_name: 'ask_user',
        user_input_request: {
          question: '这个指标来自哪里？',
          options: ['来自日志', '不确定'],
          allow_custom: false,
        },
      },
      'Tool call',
    ),
    {
      type: 'user_input_request',
      callId: 'call_ask',
      toolName: 'ask_user',
      request: {
        question: '这个指标来自哪里？',
        options: ['来自日志', '不确定'],
        allowCustom: false,
      },
    },
  )
})
