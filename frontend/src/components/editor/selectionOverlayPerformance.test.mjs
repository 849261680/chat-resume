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

  assert.match(overlaySource, /ESTIMATED_SELECTION_TOOLBAR_WIDTH_BY_SOURCE/)
  assert.match(overlaySource, /selectionCenter = rangeRect\.left - panelRect\.left \+ rangeRect\.width \/ 2/)
  assert.match(overlaySource, /action\.anchorCenter - overlayWidth \/ 2/)
  assert.match(overlaySource, /clampOverlayLeft/)
  assert.doesNotMatch(overlaySource, /Math\.min\(560/)
  assert.doesNotMatch(overlaySource, /rangeRect\.right - panelRect\.left \+ 8/)
})

test('selection toolbar uses measured size and avoids covering nearby text when possible', async () => {
  const { overlaySource } = await readSelectionOverlaySources()

  assert.match(overlaySource, /useLayoutEffect/)
  assert.match(overlaySource, /toolbarRef/)
  assert.match(overlaySource, /toolbar\.offsetWidth/)
  assert.match(overlaySource, /toolbar\.offsetHeight/)
  assert.match(overlaySource, /selectionTop - overlayHeight - SELECTION_OVERLAY_GAP/)
  assert.match(overlaySource, /selectionBottom \+ SELECTION_OVERLAY_GAP/)
  assert.doesNotMatch(overlaySource, /selectionTop - 40/)
})

test('selection toolbar buttons use compact padding', async () => {
  const { overlaySource } = await readSelectionOverlaySources()
  const previewToolbarSource = overlaySource.slice(
    overlaySource.indexOf("selectionAction?.source === 'preview' && selectionAction.mode === 'toolbar'"),
    overlaySource.indexOf("selectionAction?.source === 'preview' && selectionAction.mode === 'quick_edit'")
  )
  const chatToolbarSource = overlaySource.slice(
    overlaySource.indexOf("selectionAction?.source === 'chat' && selectionAction.mode === 'toolbar'"),
    overlaySource.indexOf("messagesPanel && selectionAction?.source === 'chat'")
  )

  assert.match(previewToolbarSource, /px-1 py-0\.5/)
  assert.match(previewToolbarSource, /h-4 w-px/)
  assert.doesNotMatch(previewToolbarSource, /px-2 py-0\.5/)
  assert.doesNotMatch(previewToolbarSource, /px-2\.5 py-1/)
  assert.doesNotMatch(previewToolbarSource, /h-5 w-px/)
  assert.match(chatToolbarSource, /px-1 py-0\.5/)
  assert.doesNotMatch(chatToolbarSource, /px-2 py-0\.5/)
})
