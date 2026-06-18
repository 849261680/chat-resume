// Tests the resume Agent SSE payload to frontend event protocol.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const protocol = await import('./streamingEventProtocol.ts')

// Loads the shared Resume stream contract fixture.
async function loadContractFixtures() {
  const raw = await readFile(new URL('../../../docs/agents/resume-agent-stream-contract-fixtures.json', import.meta.url), 'utf8')
  return JSON.parse(raw)
}

test('shared stream contract fixtures map to frontend stream events', async () => {
  const fixtures = await loadContractFixtures()
  for (const fixture of fixtures.events) {
    const actual = fixture.public_payload.tool_confirmed || fixture.public_payload.tool_rejected
      ? protocol.toolDecisionFromSsePayload(fixture.public_payload, 'Tool call')
      : protocol.streamEventFromSsePayload(fixture.public_payload, 'Tool call')
    assert.deepEqual(
      actual,
      fixture.frontend_event,
      fixture.name,
    )
  }
})

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

test('stream reducer coalesces text events and content', () => {
  const first = protocol.reduceStreamSsePayload(
    protocol.createStreamProtocolState(),
    { event_type: 'text_delta', content: '先改' },
    'Tool call',
  )
  const second = protocol.reduceStreamSsePayload(
    first.state,
    { event_type: 'text_delta', content: '项目。' },
    'Tool call',
  )
  assert.equal(second.state.content, '先改项目。')
  assert.deepEqual(second.state.events, [{ type: 'text', content: '先改项目。' }])
})

test('stream reducer completes a tool_call with tool_result', () => {
  const started = protocol.reduceStreamSsePayload(
    protocol.createStreamProtocolState(),
    {
      event_type: 'tool_call',
      call_id: 'call_1',
      tool_id: 'update_bullet',
      tool_display_name: 'update_bullet',
    },
    'Tool call',
  )
  const completed = protocol.reduceStreamSsePayload(
    started.state,
    {
      event_type: 'tool_result',
      call_id: 'call_1',
      tool_id: 'update_bullet',
      tool_display_name: 'update_bullet',
      display_message: '已更新',
      result: { success: true },
    },
    'Tool call',
  )
  assert.equal(completed.completedToolCallId, 'call_1')
  assert.deepEqual(completed.state.events, [{
    type: 'tool_result',
    callId: 'call_1',
    toolName: 'update_bullet',
    toolId: 'update_bullet',
    displayMessage: '已更新',
  }])
})

test('stream reducer turns pending into confirmed decision', () => {
  const pending = protocol.reduceStreamSsePayload(
    protocol.createStreamProtocolState(),
    {
      event_type: 'tool_pending',
      tool_pending: true,
      call_id: 'call_1',
      tool_id: 'update_bullet',
      tool_display_name: 'update_bullet',
      diff_summary: '更新项目亮点',
      diff_items: [{ before: 'old', after: 'new' }],
    },
    'Tool call',
  )
  const confirmed = protocol.reduceStreamSsePayload(
    pending.state,
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
  )
  assert.equal(confirmed.decisionToolCallId, 'call_1')
  assert.deepEqual(confirmed.state.events, [{
    type: 'tool_confirmed',
    callId: 'call_1',
    toolName: 'update_bullet',
    toolId: 'update_bullet',
    diffSummary: '更新项目亮点',
    diffItems: [{ before: 'old', after: 'new' }],
  }])
})

test('pending diff yields when it follows a tool call for the same call id', () => {
  assert.equal(
    protocol.shouldYieldBeforePendingEvent(
      [{ type: 'tool_call', callId: 'call_1', toolName: 'update_bullet' }],
      { type: 'tool_pending', callId: 'call_1', toolName: 'update_bullet', diffSummary: '' },
    ),
    true,
  )
  assert.equal(
    protocol.shouldYieldBeforePendingEvent(
      [{ type: 'tool_call', callId: 'call_1', toolName: 'update_bullet' }],
      { type: 'tool_pending', callId: 'call_2', toolName: 'update_bullet', diffSummary: '' },
    ),
    false,
  )
})

test('stream reducer hides ask_user lifecycle tool events', () => {
  const reduced = protocol.reduceStreamSsePayload(
    protocol.createStreamProtocolState(),
    {
      event_type: 'tool_call',
      call_id: 'call_ask',
      tool_id: 'ask_user',
      tool_display_name: 'ask_user',
    },
    'Tool call',
  )
  assert.equal(reduced.ignoredAskUserToolEvent, true)
  assert.deepEqual(reduced.state.events, [])
})
