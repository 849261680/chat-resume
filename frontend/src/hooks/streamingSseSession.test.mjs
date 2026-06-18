// Tests the frontend Resume Agent SSE session parser and reducer.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { createStreamingSseSession } = await import('./streamingSseSession.ts')

test('streaming SSE session parses split id/data chunks and tracks cursor', () => {
  const session = createStreamingSseSession('Tool call')

  assert.deepEqual(session.pushChunk('id: sess_1:1\ndata: {"event_type":"text_delta"'), [])

  const reductions = session.pushChunk(',"content":"先改"}\n')

  assert.equal(reductions.length, 1)
  assert.equal(reductions[0].nextCursor, 'sess_1:1')
  assert.deepEqual(reductions[0].protocolEvent, { type: 'text', content: '先改' })
  assert.equal(reductions[0].state.content, '先改')
})

test('streaming SSE session exposes previous events before reducing pending diff', () => {
  const session = createStreamingSseSession('Tool call')
  session.pushChunk(
    'id: sess_1:1\n' +
      'data: {"event_type":"tool_call","call_id":"call_1","tool_id":"update_bullet"}\n',
  )

  const reductions = session.pushChunk(
    'id: sess_1:2\n' +
      'data: {"event_type":"tool_pending","tool_pending":true,"call_id":"call_1","tool_id":"update_bullet","diff_summary":"更新"}\n',
  )

  assert.equal(reductions.length, 1)
  assert.equal(reductions[0].nextCursor, 'sess_1:2')
  assert.deepEqual(reductions[0].previousEvents, [
    {
      type: 'tool_call',
      callId: 'call_1',
      toolName: 'Tool call',
      toolId: 'update_bullet',
      toolInput: undefined,
      displayMessage: undefined,
    },
  ])
  assert.equal(reductions[0].pendingToolCallId, 'call_1')
  assert.deepEqual(reductions[0].protocolEvent, {
    type: 'tool_pending',
    callId: 'call_1',
    toolName: 'Tool call',
    toolId: 'update_bullet',
    toolInput: undefined,
    diffSummary: '更新',
    diffItems: [],
  })
})
