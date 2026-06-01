// Tests resume photo value handling through the public module interface.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { normalizeResumePhotoUrl } = await import('./resumePhoto.ts')

test('normalizeResumePhotoUrl accepts http image urls and image data urls', () => {
  assert.equal(
    normalizeResumePhotoUrl(' https://example.com/avatar.jpg '),
    'https://example.com/avatar.jpg',
  )
  assert.equal(
    normalizeResumePhotoUrl('data:image/png;base64,abc123'),
    'data:image/png;base64,abc123',
  )
})

test('normalizeResumePhotoUrl rejects unsafe or non-image values', () => {
  assert.equal(normalizeResumePhotoUrl('javascript:alert(1)'), '')
  assert.equal(normalizeResumePhotoUrl('data:text/html;base64,abc123'), '')
  assert.equal(normalizeResumePhotoUrl(42), '')
})
