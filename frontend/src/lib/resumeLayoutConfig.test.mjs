// Tests resume layout config behavior through the public module interface.
import assert from 'node:assert/strict'
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
