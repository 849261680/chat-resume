// Tests resume preview typography tokens by scanning source files.
import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import { join } from 'node:path'
import { test } from 'node:test'

const previewRoot = new URL('./', import.meta.url)
const sectionsRoot = new URL('./sections/', import.meta.url)
const globalsCssUrl = new URL('../../app/globals.css', import.meta.url)

// 用于递归列出预览源码文件。
async function listFiles(rootUrl) {
  const rootPath = rootUrl.pathname
  const entries = await readdir(rootPath, { withFileTypes: true })
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(rootPath, entry.name)
    if (entry.isDirectory()) {
      return listFiles(new URL(`${entry.name}/`, rootUrl))
    }
    return entry.name.endsWith('.tsx') || entry.name.endsWith('.css') ? [path] : []
  }))
  return files.flat()
}

test('resume preview body line-height uses the shared spacingScale token', async () => {
  const globalsCss = await readFile(globalsCssUrl, 'utf8')
  assert.match(globalsCss, /--resume-body-line-height:/)
  assert.match(globalsCss, /--resume-formal-line-height:\s*var\(--resume-body-line-height\)/)
  assert.match(globalsCss, /--resume-emerald-line-height:\s*var\(--resume-body-line-height\)/)

  const files = await listFiles(sectionsRoot)
  for (const file of files) {
    const source = await readFile(file, 'utf8')
    assert.doesNotMatch(source, /lineHeight:\s*['"]1\.(6[0-9]|7[0-9])['"]/)
    assert.doesNotMatch(source, /lineHeight:\s*['"]calc\(1\.35 \+ var\(--spacing-scale/)
  }

  const previewSource = await readFile(new URL('./PaginatedResumePreview.tsx', previewRoot), 'utf8')
  assert.match(previewSource, /--spacing-scale/)
})
