// Tests completion handoff from live stream state to chat history.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { commitCompletedStreamMessage } = await import('./streamingCompletion.ts')

test('commitCompletedStreamMessage appends the final message before clearing live state', () => {
  const calls = []
  const message = { id: 'message_1', content: '最终回答' }

  commitCompletedStreamMessage(
    message,
    (finalMessage) => calls.push(['append', finalMessage]),
    () => calls.push(['clear']),
  )

  assert.deepEqual(calls, [
    ['append', message],
    ['clear'],
  ])
})

test('commitCompletedStreamMessage still clears live state without an append handler', () => {
  const calls = []

  commitCompletedStreamMessage(
    { id: 'message_1', content: '最终回答' },
    undefined,
    () => calls.push(['clear']),
  )

  assert.deepEqual(calls, [['clear']])
})
