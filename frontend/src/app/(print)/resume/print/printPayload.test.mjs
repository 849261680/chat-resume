// Tests print page readiness rules through pure helpers.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { isResumePrintReady } = await import('./printPayload.ts')

test('isResumePrintReady only becomes true after payload content and preview pages are rendered', () => {
  assert.equal(isResumePrintReady(null, true), false)
  assert.equal(isResumePrintReady({ content: null }, true), false)
  assert.equal(isResumePrintReady({ content: { personal_info: { name: '张三' } } }, false), false)
  assert.equal(isResumePrintReady({ content: { personal_info: { name: '张三' } } }, true), true)
})
