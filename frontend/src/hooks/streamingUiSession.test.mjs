// Tests the frontend streaming UI session helper for confirmation state.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { createStreamingUiSession } = await import('./streamingUiSession.ts')

test('streaming UI session restores pending confirmation as a tool event', async () => {
  const session = createStreamingUiSession()
  const calls = []
  const client = {
    async restorePendingConfirmation(resumeId) {
      calls.push(resumeId)
      return {
        sessionId: 'session_123456',
        action: {
          call_id: 'call_1',
          tool_name: 'Update bullet',
          tool_id: 'update_bullet',
          diff_summary: '改写项目经历',
          diff_items: [{ path: 'projects.0.bullets.0', after: 'Led launch' }],
        },
      }
    },
  }

  const restored = await session.restorePendingConfirmation(client, 7)

  assert.deepEqual(calls, [7])
  assert.equal(session.sessionId(), 'session_123456')
  assert.equal(session.isStreamingLocked(), true)
  assert.deepEqual(restored, {
    sessionId: 'session_123456',
    event: {
      type: 'tool_pending',
      callId: 'call_1',
      toolName: 'Update bullet',
      toolId: 'update_bullet',
      diffSummary: '改写项目经历',
      diffItems: [{ after: 'Led launch' }],
    },
  })
})

test('streaming UI session guards duplicate confirmation and resumes paused session', async () => {
  let now = 100
  let releaseConfirm
  const debugMessages = []
  const warnMessages = []
  const confirmCalls = []
  const resumeCalls = []
  const session = createStreamingUiSession({
    nowMs: () => {
      now += 5
      return now
    },
    requestPaint: (callback) => callback(),
    debugLog: (message, payload) => debugMessages.push([message, payload]),
    warn: (message, payload) => warnMessages.push([message, payload]),
  })
  const client = {
    async confirmTool(params) {
      confirmCalls.push(params)
      await new Promise((resolve) => {
        releaseConfirm = resolve
      })
      return { ok: true, resumable: true }
    },
    async resumePausedSession(sessionId) {
      resumeCalls.push(sessionId)
      return { projects: [{ name: 'A' }] }
    },
  }

  session.setSessionId('session_abcdef')
  session.recordPendingTool({
    callId: 'call_1',
    toolName: 'Update bullet',
    diffItemCount: 1,
    streamStartedAt: 80,
    clientRequestId: 'ai_request_1',
    previousEvents: [],
    eventsAfter: [],
  })

  const firstConfirmation = session.confirmTool(client, {
    callId: 'call_1',
    confirmed: true,
    source: 'diff_card',
    feedback: '  LGTM  ',
  })
  const duplicate = await session.confirmTool(client, {
    callId: 'call_1',
    confirmed: true,
    source: 'diff_card',
  })
  releaseConfirm()
  const firstResult = await firstConfirmation

  assert.equal(duplicate.status, 'duplicate_in_flight')
  assert.equal(firstResult.status, 'resumable')
  assert.deepEqual(firstResult.resumeContent, { projects: [{ name: 'A' }] })
  assert.deepEqual(resumeCalls, ['session_abcdef'])
  assert.deepEqual(confirmCalls, [
    {
      sessionId: 'session_abcdef',
      callId: 'call_1',
      confirmed: true,
      source: 'diff_card',
      feedback: 'LGTM',
    },
  ])
  assert.equal(warnMessages.length, 1)
  assert.equal(debugMessages.some(([message]) => message === '[confirmTool] duplicate click ignored'), true)
})
