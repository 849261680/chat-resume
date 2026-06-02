'use client'
// 用于提供 components/preview/sections/SummaryPreview.tsx 模块。

import { useTranslations } from 'next-intl'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'

type SummaryData = { text?: string }

interface SummaryPreviewProps {
  data?: SummaryData
  renderLines?: number[]
  templateStyle?: ResumeTemplateStyle
}

// 用于渲染个人简介预览模块。
export default function SummaryPreview({ data, renderLines, templateStyle = 'classic' }: SummaryPreviewProps) {
  const t = useTranslations('resume.layout.modules')
  const text = data?.text?.trim()
  if (!text) return null

  const shouldRenderLine = (lineIndex: number) => !renderLines || renderLines.includes(lineIndex)
  const isEmerald = templateStyle === 'emerald'
  const isFormal = templateStyle === 'formal'

  return (
    <div style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 20px)' }}>
      {shouldRenderLine(0) && (
        <h2
          data-line-index={0}
          className="text-lg font-bold text-gray-900 pb-1 border-b border-gray-200"
          style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)' }}
        >
          {isEmerald ? <span className="resume-emerald-heading-label">{t('summary')}</span> : t('summary')}
        </h2>
      )}
      {shouldRenderLine(1) && (
        <p
          data-line-index={1}
          className={isFormal || isEmerald ? 'text-sm text-gray-900' : 'text-sm text-gray-700'}
          style={{ lineHeight: isEmerald ? 'var(--resume-emerald-line-height)' : '1.72', margin: 0 }}
        >
          {text}
        </p>
      )}
    </div>
  )
}
