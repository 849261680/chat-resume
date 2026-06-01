// Tests resume highlight text filtering through the public helper.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { visibleHighlightTexts } = await import('./resumeHighlights.ts')

test('visibleHighlightTexts drops blank highlight text', () => {
  const highlights = [
    { id: 'empty', text: '   ' },
    { id: 'filled', text: '985高校、主要课程' },
  ]

  assert.deepEqual(visibleHighlightTexts(highlights), ['985高校、主要课程'])
})
