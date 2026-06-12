// Tests line-based pagination sizing helpers.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const {
  A4_HEIGHT,
  PAGE_PADDING,
  SAFETY_MARGIN,
  getPageContentHeight,
} = await import('./useLineBasedPagination.ts')

test('getPageContentHeight uses fixed page margins', () => {
  assert.equal(getPageContentHeight(), A4_HEIGHT - PAGE_PADDING * 2 - SAFETY_MARGIN)
  assert.equal(getPageContentHeight({ pageHeight: 720 }), 720)
})

test('getPageContentHeight gives full-bleed templates the full page height', () => {
  assert.equal(
    getPageContentHeight({ fullBleed: true }),
    A4_HEIGHT - SAFETY_MARGIN,
  )
})
