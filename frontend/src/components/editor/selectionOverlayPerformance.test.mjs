// Tests that selection toolbar state stays out of the resume edit page render tree.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const editorRoot = new URL('./', import.meta.url)
const editPageUrl = new URL('../../app/[locale]/resume/[id]/edit/page.tsx', import.meta.url)

// 读取选区浮层和编辑页源码，验证选区动作只在局部组件内更新。
async function readSelectionOverlaySources() {
  const overlaySource = await readFile(new URL('./ResumeSelectionOverlay.tsx', editorRoot), 'utf8')
  const editPageSource = await readFile(editPageUrl, 'utf8')
  return { overlaySource, editPageSource }
}

test('resume selection toolbar is isolated from the edit page root state', async () => {
  const { overlaySource, editPageSource } = await readSelectionOverlaySources()

  assert.match(editPageSource, /<ResumeSelectionOverlay/)
  assert.match(editPageSource, /selectionOverlayRef\.current\?\.updateSelectionAction\(\)/)
  assert.match(editPageSource, /selectionOverlayRef\.current\?\.handleMainPointerDown\(event\)/)
  assert.match(editPageSource, /selectionOverlayRef\.current\?\.handleMainCopy\(event\)/)
  assert.doesNotMatch(editPageSource, /useState<ResumeSelectionAction \| null>/)
  assert.doesNotMatch(editPageSource, /setResumeSelectionAction/)
  assert.doesNotMatch(editPageSource, /buildSelectionAction/)
  assert.doesNotMatch(editPageSource, /pasteResumeSelectionToChat/)
  assert.doesNotMatch(editPageSource, /quickEditResumeSelection/)
  assert.match(overlaySource, /useState<ResumeSelectionAction \| null>/)
  assert.match(overlaySource, /createPortal/)
  assert.match(overlaySource, /<QuickEditPopover/)
})

test('selection toolbar is centered near the selected text before clamping', async () => {
  const { overlaySource } = await readSelectionOverlaySources()

  assert.match(overlaySource, /SELECTION_TOOLBAR_WIDTH_BY_SOURCE/)
  assert.match(overlaySource, /selectionCenter = rangeRect\.left - panelRect\.left \+ rangeRect\.width \/ 2/)
  assert.match(overlaySource, /selectionCenter - actionWidth \/ 2/)
  assert.match(overlaySource, /clampOverlayLeft/)
  assert.doesNotMatch(overlaySource, /Math\.min\(560/)
  assert.doesNotMatch(overlaySource, /rangeRect\.right - panelRect\.left \+ 8/)
})
