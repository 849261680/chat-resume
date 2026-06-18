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
    if (specifier === './resumeSpacingScale') {
      return {
        shortCircuit: true,
        url: new URL('./resumeSpacingScale.ts', import.meta.url).href,
      }
    }
    return nextResolve(specifier, context)
  },
})

const {
  buildResumeEditorSections,
  deserializeLayoutConfig,
  isLayoutConfigDirty,
  loadLayoutConfig,
  moveResumeModule,
  saveLayoutConfig,
  setResumeLayoutDensity,
  setResumeTemplateStyle,
  toggleResumeModuleVisibility,
} = await import('./resumeLayoutConfig.ts')
const { MAX_RESUME_SPACING_SCALE } = await import('./resumeSpacingScale.ts')

const layoutModules = ['personal', 'summary', 'education', 'work', 'projects', 'open_source', 'skills']

// 提供最小 localStorage mock，供布局缓存测试使用。
function installLocalStorageMock() {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => { store.set(key, String(value)) },
    removeItem: (key) => { store.delete(key) },
    clear: () => { store.clear() },
  }
}

// 读取 locale 文件，验证布局模块 id 与翻译 key 保持一致。
async function readResumeMessages(locale) {
  const url = new URL(`../../locales/${locale}/resume.json`, import.meta.url)
  return JSON.parse(await readFile(url, 'utf8'))
}

test('resume spacing scale allows up to 1.80', () => {
  assert.equal(MAX_RESUME_SPACING_SCALE, 1.8)
})

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

test('deserializeLayoutConfig clamps old overly loose spacing values', () => {
  const config = deserializeLayoutConfig({
    density: 'custom',
    moduleOrder: ['personal', 'summary', 'work'],
    visibleModules: ['personal', 'summary', 'work'],
    spacingScale: 3.05,
    templateStyle: 'classic',
  })

  assert.equal(config.spacingScale, MAX_RESUME_SPACING_SCALE)
})

test('layout config cache tracks dirty local density changes', () => {
  installLocalStorageMock()
  const config = deserializeLayoutConfig({
    density: 'custom',
    moduleOrder: ['personal', 'summary', 'work'],
    visibleModules: ['personal', 'summary', 'work'],
    spacingScale: 1.72,
    templateStyle: 'emerald',
  })

  saveLayoutConfig(101, config, { dirty: true })
  assert.equal(isLayoutConfigDirty(101), true)
  assert.equal(loadLayoutConfig(101).spacingScale, 1.72)

  saveLayoutConfig(101, config, { dirty: false })
  assert.equal(isLayoutConfigDirty(101), false)
})

test('layout actions update one setting while preserving the rest of the config', () => {
  const config = deserializeLayoutConfig({
    density: 'normal',
    moduleOrder: ['personal', 'projects', 'work', 'skills'],
    visibleModules: ['personal', 'projects', 'work'],
    spacingScale: 1,
    templateStyle: 'classic',
  })

  const compact = setResumeLayoutDensity(config, 'compact')
  assert.equal(compact.spacingScale, 0.7)
  assert.deepEqual(compact.moduleOrder, config.moduleOrder)
  assert.deepEqual(Array.from(compact.visibleModules), Array.from(config.visibleModules))

  const emerald = setResumeTemplateStyle(compact, 'emerald')
  assert.equal(emerald.templateStyle, 'emerald')
  assert.equal(emerald.spacingScale, 0.7)
})

test('layout module owns resume module visibility and ordering actions', () => {
  const config = deserializeLayoutConfig({
    moduleOrder: ['personal', 'projects', 'work', 'skills'],
    visibleModules: ['personal', 'projects', 'work'],
  })

  const hiddenProjects = toggleResumeModuleVisibility(config, 'projects')
  assert.equal(hiddenProjects.visibleModules.has('projects'), false)

  const movedWork = moveResumeModule(config, 'work', 'up')
  assert.deepEqual(movedWork.moduleOrder.slice(0, 3), ['personal', 'work', 'projects'])
})

test('editor sections follow resume module order after the job section', () => {
  const config = deserializeLayoutConfig({
    moduleOrder: ['personal', 'projects', 'work', 'skills', 'summary', 'education', 'open_source'],
    visibleModules: ['personal', 'projects', 'work', 'skills'],
  })
  const sections = buildResumeEditorSections(config, (key) => key)

  assert.deepEqual(
    sections.map((section) => section.key),
    ['job_application', 'personal', 'projects', 'work', 'skills'],
  )
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
