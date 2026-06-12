// Tests line-based pagination sizing helpers.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const {
  A4_HEIGHT,
  PAGE_PADDING,
  SAFETY_MARGIN,
  getPageLineEndOffset,
  getPageContentHeight,
} = await import('./useLineBasedPagination.ts')

test('page padding uses 38px resume margins', () => {
  assert.equal(PAGE_PADDING, 38)
})

test('getPageContentHeight uses fixed page margins', () => {
  assert.equal(getPageContentHeight(), A4_HEIGHT - PAGE_PADDING * 2 - SAFETY_MARGIN)
  assert.equal(getPageContentHeight({ pageHeight: 720 }), 720)
})

test('getPageContentHeight keeps a fixed bottom margin for full-bleed templates', () => {
  assert.equal(
    getPageContentHeight({ fullBleed: true }),
    A4_HEIGHT - PAGE_PADDING - SAFETY_MARGIN,
  )
})

test('getPageLineEndOffset preserves trailing space only on the final content line', () => {
  const line = { top: 100, bottom: 140, height: 72 }

  assert.equal(getPageLineEndOffset(line, false), 140)
  assert.equal(getPageLineEndOffset(line, true), 172)
})
