// Tests that resume layout density changes are flushed before page refresh.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const hooksRoot = new URL('./', import.meta.url)
const libRoot = new URL('../lib/', import.meta.url)

// 读取简历编辑 Hook 和布局保存模块，验证刷新前不会丢掉防抖中的密度设置。
async function readLayoutPersistenceSources() {
  const editorSource = await readFile(new URL('./useResumeEditor.ts', hooksRoot), 'utf8')
  const layoutConfigSource = await readFile(new URL('./resumeLayoutConfig.ts', libRoot), 'utf8')
  return { editorSource, layoutConfigSource }
}

test('layout config save is flushed on pagehide and component unmount', async () => {
  const { editorSource, layoutConfigSource } = await readLayoutPersistenceSources()

  assert.match(editorSource, /pendingLayoutSaveRef/)
  assert.match(editorSource, /isLayoutConfigDirty\(id\)/)
  assert.match(editorSource, /const cachedConfig = loadLayoutConfig\(id\)/)
  assert.match(editorSource, /setLayoutConfig\(cachedConfig\)/)
  assert.match(editorSource, /saveLayoutConfigToServer\(id, cachedConfig\)/)
  assert.match(editorSource, /saveLayoutConfig\(id, newConfig, \{ dirty: true \}\)/)
  assert.match(editorSource, /window\.addEventListener\('pagehide', flushPendingLayoutSave\)/)
  assert.match(editorSource, /window\.removeEventListener\('pagehide', flushPendingLayoutSave\)/)
  assert.match(editorSource, /flushPendingLayoutSave\(\)/)
  assert.match(editorSource, /saveLayoutConfigToServer\(pending\.id, pending\.config, \{ keepalive: true \}\)/)
  assert.match(layoutConfigSource, /options: \{ keepalive\?: boolean \} = \{\}/)
  assert.match(layoutConfigSource, /keepalive: options\.keepalive/)
})

test('resume export callback refreshes when density spacing changes', async () => {
  const { editorSource } = await readLayoutPersistenceSources()
  const exportCallbackMatch = editorSource.match(
    /const handleExportPDF = useCallback\(async \(\) => \{[\s\S]*?\n  \}, \[(.*?)\]\)/,
  )
  const dependencies = (exportCallbackMatch?.[1] ?? '').split(',').map((item) => item.trim())

  assert.ok(exportCallbackMatch, 'handleExportPDF useCallback was not found')
  assert.ok(dependencies.includes('layoutConfig'), 'handleExportPDF must refresh for spacingScale changes')
})
