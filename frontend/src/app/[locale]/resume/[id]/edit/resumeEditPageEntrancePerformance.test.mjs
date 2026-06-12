// Tests that the primary editor panels do not wait on decorative entrance delays.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const editPageUrl = new URL('./page.tsx', import.meta.url)

// 读取编辑页源码，验证首屏主面板不会被慢入场动画延迟。
async function readEditPageSource() {
  return readFile(editPageUrl, 'utf8')
}

test('preview and chat panels render without delayed entrance animations', async () => {
  const source = await readEditPageSource()
  const previewPanelSource = source.slice(
    source.indexOf('{/* Middle Panel - Preview */}'),
    source.indexOf('{/* 拖拽分隔条 */}')
  )
  const chatPanelSource = source.slice(
    source.indexOf('{/* Right Panel - AI Chat */}'),
    source.indexOf('{firstRunPhase ===')
  )

  assert.match(previewPanelSource, /initial=\{false\}/)
  assert.match(chatPanelSource, /initial=\{false\}/)
  assert.doesNotMatch(previewPanelSource, /delay: 0\.[0-9]/)
  assert.doesNotMatch(chatPanelSource, /delay: 0\.[0-9]/)
  assert.doesNotMatch(previewPanelSource, /duration: 0\.8/)
  assert.doesNotMatch(chatPanelSource, /duration: 0\.8/)
})
