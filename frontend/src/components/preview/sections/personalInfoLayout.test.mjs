// Tests personal info preview layout decisions through the public layout module.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { getFormalPersonalInfoLayout } = await import('./personalInfoLayout.ts')

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
