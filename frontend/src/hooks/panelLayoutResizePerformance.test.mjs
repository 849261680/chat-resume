// Tests that panel resizing avoids heavy per-pointer layout work.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const hooksRoot = new URL('./', import.meta.url)
const editPageUrl = new URL('../app/[locale]/resume/[id]/edit/page.tsx', import.meta.url)
const paginatedPreviewUrl = new URL('../components/preview/PaginatedResumePreview.tsx', import.meta.url)

// 读取面板布局和编辑页源码，验证拖拽性能保护仍存在。
async function readPanelResizeSources() {
  const hookSource = await readFile(new URL('./usePanelLayout.ts', hooksRoot), 'utf8')
  const editPageSource = await readFile(editPageUrl, 'utf8')
  const paginatedPreviewSource = await readFile(paginatedPreviewUrl, 'utf8')
  return { hookSource, editPageSource, paginatedPreviewSource }
}

test('panel resizing uses CSS variables during drag and commits state on release', async () => {
  const { hookSource, editPageSource, paginatedPreviewSource } = await readPanelResizeSources()

  assert.match(hookSource, /requestAnimationFrame/)
  assert.match(hookSource, /isResizingPanels/)
  assert.match(hookSource, /setIsResizingPanels\(true\)/)
  assert.match(hookSource, /setIsResizingPanels\(false\)/)
  assert.match(hookSource, /style\.setProperty\('--editor-panel-width'/)
  assert.match(hookSource, /style\.setProperty\('--preview-panel-width'/)
  assert.match(hookSource, /style\.setProperty\('--agent-panel-width'/)
  assert.match(hookSource, /setEditorFlex\(nextFlex\.editorFlex\)/)
  assert.match(hookSource, /setAgentFlex\(nextFlex\.agentFlex\)/)
  assert.doesNotMatch(hookSource, /setEditorFlex\(nextEditorFlex\)/)
  assert.doesNotMatch(hookSource, /setAgentFlex\(nextAgentFlex\)/)
  assert.doesNotMatch(hookSource, /schedulePanelWidthApply\(\(\) => set/)
  assert.match(editPageSource, /style=\{panelLayoutStyle\}/)
  assert.match(editPageSource, /flex: '0 0 var\(--preview-panel-width\)'/)
  assert.match(editPageSource, /flex: '0 0 var\(--agent-panel-width\)'/)
  assert.match(editPageSource, /layout=\{!isResizingPanels\}/)
  assert.match(editPageSource, /isContainerResizing=\{isResizingPanels\}/)
  assert.match(paginatedPreviewSource, /isContainerResizing\?: boolean/)
  assert.match(paginatedPreviewSource, /if \(isContainerResizing\) return/)
  assert.match(paginatedPreviewSource, /scheduleScaleCalculation/)
  assert.match(paginatedPreviewSource, /new ResizeObserver\(scheduleScaleCalculation\)/)
})
