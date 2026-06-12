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
    if (specifier === './useLineBasedPagination') {
      return {
        shortCircuit: true,
        url: new URL('./useLineBasedPagination.ts', import.meta.url).href,
      }
    }
    return nextResolve(specifier, context)
  },
})

const {
  MIN_SPACING_SCALE,
  MAX_SPACING_SCALE,
  applyTooMuchContentFallback,
  calculateSmartFitScale,
  getSmartFitPageBottom,
} = await import('./smartFitCore.ts')
const { MAX_RESUME_SPACING_SCALE, RESUME_SPACING_SCALE_STEP } = await import('../../../lib/resumeSpacingScale.ts')
const { A4_HEIGHT, PAGE_PADDING, SAFETY_MARGIN } = await import('./useLineBasedPagination.ts')

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

test('smart-fit bottom limits match normal and full-bleed page boxes', () => {
  assert.equal(getSmartFitPageBottom(false), A4_HEIGHT - PAGE_PADDING * 2 - SAFETY_MARGIN)
  assert.equal(getSmartFitPageBottom(true), A4_HEIGHT - PAGE_PADDING - SAFETY_MARGIN)
})

test('calculateSmartFitScale loosens short content up to the max spacing', async () => {
  const pageBottom = getSmartFitPageBottom(false)
  const result = await calculateSmartFitScale({
    currentScale: 1,
    measureContentBottom: async (scale) => pageBottom - 120 + scale * 40,
  })

  assert.equal(result.status, 'success')
  assert.equal(result.newScale, MAX_SPACING_SCALE)
})

test('calculateSmartFitScale uses the largest fitting spacing step on one page', async () => {
  const pageBottom = getSmartFitPageBottom(false)
  const result = await calculateSmartFitScale({
    currentScale: 1,
    measureContentBottom: async (scale) => pageBottom + (scale - 1.2) * 1000,
  })

  assert.equal(result.status, 'success')
  assert.equal(result.newScale, 1.2)
})

test('calculateSmartFitScale compresses overflowing content to fit one page', async () => {
  const pageBottom = getSmartFitPageBottom(false)
  const result = await calculateSmartFitScale({
    currentScale: MAX_SPACING_SCALE,
    measureContentBottom: async (scale) => pageBottom - 70 + scale * 100,
  })

  assert.equal(result.status, 'success')
  assert.ok(result.newScale < MAX_SPACING_SCALE)
  assert.ok(result.newScale >= MIN_SPACING_SCALE)
  assert.equal(Math.round(result.newScale / RESUME_SPACING_SCALE_STEP), result.newScale / RESUME_SPACING_SCALE_STEP)
})

test('calculateSmartFitScale reports too much content when minimum spacing still overflows', async () => {
  const pageBottom = getSmartFitPageBottom(false)
  const result = await calculateSmartFitScale({
    currentScale: MAX_SPACING_SCALE,
    measureContentBottom: async () => pageBottom + 100,
  })

  assert.deepEqual(result, {
    status: 'too_much_content',
    pages: 2,
    appliedScale: MIN_SPACING_SCALE,
    finalMeasureScale: MIN_SPACING_SCALE,
  })
})
