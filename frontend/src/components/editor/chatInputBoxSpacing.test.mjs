// Tests that selected resume context in the chat input stays compact.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const editorRoot = new URL('./', import.meta.url)

// 读取聊天输入框源码，验证引用 chip 的内边距不会过大。
async function readChatInputBoxSource() {
  return readFile(new URL('./ChatInputBox.tsx', editorRoot), 'utf8')
}

test('selected resume context chip uses compact spacing', async () => {
  const source = await readChatInputBoxSource()

  assert.match(source, /data-testid="selected-resume-context"/)
  assert.match(source, /px-1\.5 py-0\.5/)
  assert.match(source, /leading-snug/)
  assert.doesNotMatch(source, /selected-resume-context"[\s\S]*px-2 py-1/)
  assert.doesNotMatch(source, /selected-resume-context"[\s\S]*leading-relaxed/)
})
