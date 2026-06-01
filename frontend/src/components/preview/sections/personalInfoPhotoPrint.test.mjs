// Tests print stylesheet keeps resume photos visually consistent with preview.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

test('print stylesheet preserves emerald resume photo border color', async () => {
  const css = await readFile(new URL('../../../../public/styles/resume-print.css', import.meta.url), 'utf8')

  assert.match(css, /\.resume-template-emerald\s+\.resume-photo/)
  assert.match(css, /border-color:\s*rgba\(255,\s*255,\s*255,\s*0\.4\)\s*!important/)
})
