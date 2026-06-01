// Tests personal info preview layout decisions through the public layout module.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const {
  getCenteredPersonalInfoLayout,
  getEmeraldPersonalInfoLayout,
  getFormalPersonalInfoLayout,
} = await import('./personalInfoLayout.ts')

test('getFormalPersonalInfoLayout keeps a formal photo out of document flow', () => {
  const layout = getFormalPersonalInfoLayout(true)

  assert.match(layout.photoWrapClassName, /\babsolute\b/)
  assert.match(layout.photoWrapClassName, /\bright-0\b/)
  assert.match(layout.textClassName, /(^|\s)pr-\[96px\](\s|$)/)
  assert.match(layout.contactClassName, /(^|\s)pr-\[96px\](\s|$)/)
})

test('getFormalPersonalInfoLayout does not reserve photo space when no photo exists', () => {
  const layout = getFormalPersonalInfoLayout(false)

  assert.equal(layout.photoWrapClassName, '')
  assert.doesNotMatch(layout.textClassName, /(^|\s)pr-\[96px\](\s|$)/)
  assert.doesNotMatch(layout.contactClassName, /(^|\s)pr-\[96px\](\s|$)/)
})

test('getCenteredPersonalInfoLayout keeps a default template photo out of document flow', () => {
  const layout = getCenteredPersonalInfoLayout(true)

  assert.equal(layout.headerStyle.minHeight, undefined)
  assert.match(layout.photoWrapClassName, /\babsolute\b/)
  assert.match(layout.photoWrapClassName, /\bright-0\b/)
  assert.match(layout.textClassName, /(^|\s)px-\[96px\](\s|$)/)
  assert.match(layout.contactClassName, /(^|\s)px-\[96px\](\s|$)/)
})

test('getEmeraldPersonalInfoLayout keeps an emerald photo out of document flow', () => {
  const layout = getEmeraldPersonalInfoLayout(true)

  assert.match(layout.photoWrapClassName, /\babsolute\b/)
  assert.match(layout.photoWrapClassName, /\bright-0\b/)
  assert.match(layout.photoWrapClassName, /\btop-0\b/)
  assert.match(layout.textClassName, /(^|\s)pr-\[96px\](\s|$)/)
  assert.match(layout.contactClassName, /(^|\s)pr-\[96px\](\s|$)/)
})
