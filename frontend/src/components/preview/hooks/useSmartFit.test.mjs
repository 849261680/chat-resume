// Tests smart-fit behavior through exported hook helpers.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { MIN_SPACING_SCALE, applyTooMuchContentFallback } = await import('./smartFitCore.ts')

test('applyTooMuchContentFallback applies the tightest spacing before reporting overflow', () => {
  const appliedScales = []

  const result = applyTooMuchContentFallback(3, (scale) => {
    appliedScales.push(scale)
  })

  assert.deepEqual(appliedScales, [MIN_SPACING_SCALE])
  assert.deepEqual(result, {
    status: 'too_much_content',
    pages: 3,
    appliedScale: MIN_SPACING_SCALE,
  })
})
