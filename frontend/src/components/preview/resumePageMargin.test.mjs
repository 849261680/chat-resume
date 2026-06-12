// Tests that page top/bottom margins stay fixed while density changes content spacing.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const previewRoot = new URL('./', import.meta.url)
const hooksRoot = new URL('./hooks/', import.meta.url)

// 用于读取预览源码文件。
async function readPreviewSource(relativePath) {
  return readFile(new URL(relativePath, previewRoot), 'utf8')
}

test('resume page vertical margins do not scale with spacingScale', async () => {
  const resumePage = await readPreviewSource('ResumePage.tsx')
  const paginatedPreview = await readPreviewSource('PaginatedResumePreview.tsx')
  const paginationHook = await readFile(new URL('useLineBasedPagination.ts', hooksRoot), 'utf8')
  const smartFitHook = await readFile(new URL('useSmartFit.ts', hooksRoot), 'utf8')

  assert.doesNotMatch(resumePage, /paddingTop:\s*`calc\(var\(--spacing-scale/)
  assert.doesNotMatch(resumePage, /paddingBottom:\s*`calc\(var\(--spacing-scale/)
  assert.doesNotMatch(paginatedPreview, /paddingTop:\s*`calc\(var\(--spacing-scale/)
  assert.doesNotMatch(paginatedPreview, /paddingBottom:\s*`calc\(var\(--spacing-scale/)
  assert.doesNotMatch(paginationHook, /PAGE_PADDING \* 2 \* spacingScale/)
  assert.doesNotMatch(smartFitHook, /PAGE_PADDING \* 2 \* scale/)
})

test('emerald keeps a fixed bottom page margin', async () => {
  const globalsCss = await readFile(new URL('../../app/globals.css', import.meta.url), 'utf8')
  const paginatedPreview = await readPreviewSource('PaginatedResumePreview.tsx')
  const paginationHook = await readFile(new URL('useLineBasedPagination.ts', hooksRoot), 'utf8')

  assert.match(globalsCss, /\.resume-page\.resume-template-emerald\s*\{[\s\S]*padding-bottom:\s*38px !important;/)
  assert.match(paginatedPreview, /paddingBottom:\s*`\$\{PAGE_PADDING\}px`/)
  assert.match(paginationHook, /options\.fullBleed \? PAGE_PADDING : PAGE_PADDING \* 2/)
})
