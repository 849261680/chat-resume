// Tests resume layout config behavior through the public module interface.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { registerHooks } from 'node:module'

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === '@/lib/httpClient') {
      return {
        shortCircuit: true,
        url: new URL('./httpClient.ts', import.meta.url).href,
      }
    }
    return nextResolve(specifier, context)
  },
})

const { deserializeLayoutConfig } = await import('./resumeLayoutConfig.ts')

const layoutModules = ['personal', 'summary', 'education', 'work', 'projects', 'open_source', 'skills']

// 读取 locale 文件，验证布局模块 id 与翻译 key 保持一致。
async function readResumeMessages(locale) {
  const url = new URL(`../../locales/${locale}/resume.json`, import.meta.url)
  return JSON.parse(await readFile(url, 'utf8'))
}

test('deserializeLayoutConfig keeps an explicitly hidden summary module hidden', () => {
  const config = deserializeLayoutConfig({
    density: 'normal',
    moduleOrder: ['personal', 'summary', 'work'],
    visibleModules: ['personal', 'work'],
    spacingScale: 1,
    templateStyle: 'classic',
  })

  assert.equal(config.visibleModules.has('summary'), false)
})

test('deserializeLayoutConfig appends the open source module to old layouts', () => {
  const config = deserializeLayoutConfig({
    density: 'normal',
    moduleOrder: ['personal', 'summary', 'projects', 'skills'],
    visibleModules: ['personal', 'summary', 'projects', 'skills'],
    spacingScale: 1,
    templateStyle: 'classic',
  })

  assert.equal(config.moduleOrder.includes('open_source'), true)
  assert.equal(config.visibleModules.has('open_source'), false)
})

test('resume layout module translations cover every module id', async () => {
  for (const locale of ['en', 'zh']) {
    const messages = await readResumeMessages(locale)
    const moduleMessages = messages.layout.modules

    for (const module of layoutModules) {
      assert.equal(
        typeof moduleMessages[module],
        'string',
        `${locale} resume.layout.modules.${module} is missing`,
      )
    }
  }
})
