// Tests the pure UI patch layer for Resume Agent streaming reductions.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { registerHooks } from 'node:module'

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.endsWith('./streamingEventProtocol')) {
      return {
        shortCircuit: true,
        url: new URL('./streamingEventProtocol.ts', import.meta.url).href,
      }
    }
    return nextResolve(specifier, context)
  },
})

const { buildStreamingViewStatePatch } = await import('./streamingViewState.ts')

test('streaming view patch exposes completed message and resume update', () => {
  const patch = buildStreamingViewStatePatch({
    data: {
      done: true,
      resume_content: { projects: [] },
    },
    state: {
      content: '已完成',
      events: [{ type: 'text', content: '已完成' }],
      userInputRequest: null,
    },
    previousEvents: [],
    protocolEvent: null,
    ignoredAskUserToolEvent: false,
    replayAttempted: false,
  })

  assert.deepEqual(patch.doneMessage, {
    content: '已完成',
    streamEvents: [{ type: 'text', content: '已完成' }],
    resumeContent: { projects: [] },
  })
})

test('streaming view patch yields before pending diff after matching tool call', () => {
  const previousEvents = [
    { type: 'tool_call', callId: 'call_1', toolName: 'update_bullet' },
  ]
  const events = [
    ...previousEvents,
    { type: 'tool_pending', callId: 'call_1', toolName: 'update_bullet', diffSummary: 'diff' },
  ]

  const patch = buildStreamingViewStatePatch({
    data: {},
    state: {
      content: '',
      events,
      userInputRequest: null,
    },
    previousEvents,
    protocolEvent: events[1],
    pendingToolCallId: 'call_1',
    ignoredAskUserToolEvent: false,
    replayAttempted: false,
  })

  assert.equal(patch.yieldBeforeStreamEvents, true)
  assert.deepEqual(patch.previousEventsBeforeYield, previousEvents)
  assert.deepEqual(patch.streamEvents, events)
  assert.equal(patch.pendingToolCallId, 'call_1')
})
