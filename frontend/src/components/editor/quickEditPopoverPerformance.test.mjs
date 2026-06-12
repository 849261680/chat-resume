// Tests that quick edit typing stays isolated from the resume edit page render tree.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const editorRoot = new URL('./', import.meta.url)
const editPageUrl = new URL('../../app/[locale]/resume/[id]/edit/page.tsx', import.meta.url)

// 读取快速编辑浮层、选区浮层和编辑页源码，验证输入状态没有放在页面顶层。
async function readQuickEditSources() {
  const popoverSource = await readFile(new URL('./QuickEditPopover.tsx', editorRoot), 'utf8')
  const overlaySource = await readFile(new URL('./ResumeSelectionOverlay.tsx', editorRoot), 'utf8')
  const editPageSource = await readFile(editPageUrl, 'utf8')
  return { popoverSource, overlaySource, editPageSource }
}

test('quick edit prompt input is isolated in QuickEditPopover', async () => {
  const { popoverSource, overlaySource, editPageSource } = await readQuickEditSources()

  assert.match(editPageSource, /<ResumeSelectionOverlay/)
  assert.doesNotMatch(editPageSource, /<QuickEditPopover/)
  assert.doesNotMatch(editPageSource, /quickEditPrompt/)
  assert.doesNotMatch(editPageSource, /setQuickEditPrompt/)
  assert.doesNotMatch(editPageSource, /value=\{quickEditPrompt\}/)
  assert.match(overlaySource, /<QuickEditPopover/)
  assert.match(popoverSource, /function QuickEditPopover/)
  assert.match(popoverSource, /textareaRef/)
  assert.match(popoverSource, /defaultValue/)
  assert.doesNotMatch(popoverSource, /useState/)
  assert.doesNotMatch(popoverSource, /value=\{/)
})
