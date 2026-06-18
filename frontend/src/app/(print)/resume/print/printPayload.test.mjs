// Tests print page readiness rules through pure helpers.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const {
  RESUME_PRINT_PAYLOAD_FIELDS,
  isResumePrintReady,
  materializePrintPayload,
} = await import('./printPayload.ts')

test('isResumePrintReady only becomes true after payload content and preview pages are rendered', () => {
  assert.equal(isResumePrintReady(null, true), false)
  assert.equal(isResumePrintReady({ content: null }, true), false)
  assert.equal(isResumePrintReady({ content: { personal_info: { name: '张三' } } }, false), false)
  assert.equal(isResumePrintReady({ content: { personal_info: { name: '张三' } } }, true), true)
})

test('materializePrintPayload keeps the backend print payload contract stable', () => {
  const payload = materializePrintPayload({
    content: { personal_info: { name: '张三' } },
    template: '',
    extra: 'ignored',
  })

  assert.deepEqual(Object.keys(payload), RESUME_PRINT_PAYLOAD_FIELDS)
  assert.deepEqual(payload.content.personal_info, { name: '张三' })
  assert.equal(payload.template, 'default')
  assert.equal(payload.layout_config, null)
})
