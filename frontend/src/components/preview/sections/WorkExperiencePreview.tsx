'use client'
// 用于提供 components/preview/sections/WorkExperiencePreview.tsx 模块。

import type { WorkExperience } from '@/types/resume'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'
import { useTranslations } from 'next-intl'
import BulletLeadText from './BulletLeadText'

interface WorkExperiencePreviewProps {
  data: WorkExperience[]
  renderLines?: number[] // 指定渲染哪些行
  templateStyle?: ResumeTemplateStyle
}

// 单个工作经验项组件
function WorkExperienceItem({ work, lineIndex, templateStyle = 'classic' }: { work: WorkExperience; lineIndex: number; templateStyle?: ResumeTemplateStyle }) {
  const highlights = work.highlights && work.highlights.length > 0
    ? work.highlights.map(item => item.text)
    : []
  const isFormal = templateStyle === 'formal'
  const isEmerald = templateStyle === 'emerald'

  if (isEmerald) {
    return (
      <div data-line-index={lineIndex} className="relative print:break-inside-avoid resume-emerald-item" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 18px)' }}>
        <div className="flex items-baseline justify-between gap-4 text-sm font-semibold" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)' }}>
          <div className="min-w-0 flex flex-wrap items-baseline gap-x-2 gap-y-1">
            {work.company && <span className="resume-emerald-strong">{work.company}</span>}
            {work.company && work.position && <span className="resume-emerald-subtle">·</span>}
            {work.position && <span>{work.position}</span>}
          </div>
          {work.duration && <span className="resume-emerald-subtle shrink-0 font-normal">{work.duration}</span>}
        </div>

        {highlights.length > 0 && (
          <ul className="resume-emerald-list text-sm">
            {highlights.map((line, itemIndex) => (
              <li key={itemIndex} style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 6px)' }}><BulletLeadText text={line} /></li>
            ))}
          </ul>
        )}
      </div>
    )
  }

  if (isFormal) {
    return (
      <div data-line-index={lineIndex} className="relative print:break-inside-avoid resume-formal-item" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 16px)' }}>
        <div className="flex items-baseline justify-between gap-4 text-sm text-gray-900 font-semibold" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)' }}>
          <span className="min-w-0">{[work.company, work.position].filter(Boolean).join(' | ')}</span>
          {work.duration && <span className="shrink-0 font-normal">{work.duration}</span>}
        </div>

        {highlights.length > 0 && (
          <ul className="list-disc text-sm text-gray-900" style={{ lineHeight: '1.72', paddingLeft: 18 }}>
            {highlights.map((line, itemIndex) => (
              <li key={itemIndex} style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 6px)' }}><BulletLeadText text={line} /></li>
            ))}
          </ul>
        )}
      </div>
    )
  }

  return (
    <div data-line-index={lineIndex} className="relative print:break-inside-avoid" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 16px)' }}>
      <div className="flex justify-between items-start" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 6px)' }}>
        <div className="flex-1 flex flex-wrap items-center gap-2">
          {work.company && (
            <h3 className="font-semibold text-gray-900 text-base">
              {work.company}
            </h3>
          )}
          {work.position && (
            <>
              <span className="w-px h-4 bg-gray-300" />
              <span className="text-sm text-gray-700 font-medium">
                {work.position}
              </span>
            </>
          )}
        </div>
        <div className="text-sm text-gray-600 ml-4 whitespace-nowrap">
          {work.duration}
        </div>
      </div>

      {highlights.length > 0 && (
        <div
          className="text-sm text-gray-600"
          style={{
            marginTop: 'calc(var(--spacing-scale, 1) * 8px)',
            lineHeight: 'calc(1.35 + var(--spacing-scale, 1) * 0.25)'
          }}
        >
          <ul className="list-disc list-inside">
            {highlights.map((line, itemIndex) => (
              <li key={itemIndex} style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 2px)' }}><BulletLeadText text={line} /></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// 用于渲染 WorkExperiencePreview 组件。
export default function WorkExperiencePreview({
  data,
  renderLines,
  templateStyle = 'classic',
}: WorkExperiencePreviewProps) {
  const t = useTranslations('resume.layout.modules')
  if (!data || !Array.isArray(data) || data.length === 0) {
    return null
  }

  // 用于处理shouldrender行。
  const shouldRenderLine = (lineIndex: number) => {
    return !renderLines || renderLines.includes(lineIndex)
  }

  return (
    <div style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 20px)' }}>
      {/* 标题作为第0行 */}
      {shouldRenderLine(0) && (
        <h2 data-line-index={0} className="text-lg font-bold text-gray-900 pb-1.5 border-b border-gray-300" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 12px)' }}>
          {templateStyle === 'emerald' ? (
            <span className="resume-emerald-heading-label">{t('work')}</span>
          ) : t('work')}
        </h2>
      )}

      {/* 每个工作项作为独立的行 */}
      {data.map((work, index) => {
        const lineIndex = index + 1
        return shouldRenderLine(lineIndex) ? (
          <WorkExperienceItem key={work.id || index} work={work} lineIndex={lineIndex} templateStyle={templateStyle} />
        ) : null
      })}
    </div>
  )
}
