// Tests smart-fit behavior through exported hook helpers.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { registerHooks } from 'node:module'

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === '../../../lib/resumeSpacingScale') {
      return {
        shortCircuit: true,
        url: new URL('../../../lib/resumeSpacingScale.ts', import.meta.url).href,
      }
    }
    return nextResolve(specifier, context)
  },
})

const { MIN_SPACING_SCALE, MAX_SPACING_SCALE, applyTooMuchContentFallback } = await import('./smartFitCore.ts')
const { MAX_RESUME_SPACING_SCALE } = await import('../../../lib/resumeSpacingScale.ts')

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

test('smart-fit max spacing matches the professional resume spacing cap', () => {
  assert.equal(MAX_SPACING_SCALE, MAX_RESUME_SPACING_SCALE)
})
