// Tests that resume section gaps respond gently to density changes.
import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import { join } from 'node:path'
import { test } from 'node:test'

const previewRoot = new URL('./', import.meta.url)
const sectionsRoot = new URL('./sections/', import.meta.url)

// 用于列出所有 section 源码文件。
async function listSectionSources() {
  const entries = await readdir(sectionsRoot, { withFileTypes: true })
  return entries
    .filter((entry) => entry.isFile() && entry.name.endsWith('.tsx'))
    .map((entry) => join(sectionsRoot.pathname, entry.name))
}

test('resume section gaps use a weak spacingScale response', async () => {
  const previewSource = await readFile(new URL('./PaginatedResumePreview.tsx', previewRoot), 'utf8')

  assert.match(previewSource, /SECTION_GAP_STYLE = 'calc\(12px \+ var\(--spacing-scale, 1\) \* 5px\)'/)
  assert.doesNotMatch(previewSource, /marginBottom:\s*'calc\(var\(--spacing-scale, 1\) \* 24px\)'/)
})

test('resume section component roots do not add a second section gap', async () => {
  const sources = await Promise.all((await listSectionSources()).map((file) => readFile(file, 'utf8')))

  sources.forEach((source) => {
    assert.doesNotMatch(source, /<div style=\{\{ marginBottom: 'calc\(var\(--spacing-scale, 1\) \* 20px\)' \}\}>/)
  })
})

test('resume header and heading content gaps use compact spacingScale responses', async () => {
  const personalSource = await readFile(new URL('./PersonalInfoPreview.tsx', sectionsRoot), 'utf8')
  const educationSource = await readFile(new URL('./EducationPreview.tsx', sectionsRoot), 'utf8')
  const workSource = await readFile(new URL('./WorkExperiencePreview.tsx', sectionsRoot), 'utf8')
  const projectSource = await readFile(new URL('./ProjectsPreview.tsx', sectionsRoot), 'utf8')
  const skillSource = await readFile(new URL('./SkillsPreview.tsx', sectionsRoot), 'utf8')
  const summarySource = await readFile(new URL('./SummaryPreview.tsx', sectionsRoot), 'utf8')

  assert.match(personalSource, /PERSONAL_BLOCK_GAP_STYLE = 'calc\(12px \+ var\(--spacing-scale, 1\) \* 4px\)'/)
  assert.match(personalSource, /PERSONAL_HEADER_GAP_STYLE = 'calc\(8px \+ var\(--spacing-scale, 1\) \* 2px\)'/)
  ;[educationSource, workSource, projectSource].forEach((source) => {
    assert.match(source, /HEADING_CONTENT_GAP_STYLE = 'calc\(8px \+ var\(--spacing-scale, 1\) \* 3px\)'/)
    assert.doesNotMatch(source, /h2[\s\S]{0,180}marginBottom:\s*'calc\(var\(--spacing-scale, 1\) \* 12px\)'/)
  })
  ;[skillSource, summarySource].forEach((source) => {
    assert.match(source, /COMPACT_HEADING_GAP_STYLE = 'calc\(6px \+ var\(--spacing-scale, 1\) \* 2px\)'/)
    assert.doesNotMatch(source, /h2[\s\S]{0,180}marginBottom:\s*'calc\(var\(--spacing-scale, 1\) \* 8px\)'/)
  })
})
