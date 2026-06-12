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
const COMPACT_HEADING_GAP_STYLE = 'calc(6px + var(--spacing-scale, 1) * 2px)'

// 用于渲染个人简介预览模块。
export default function SummaryPreview({ data, renderLines, templateStyle = 'classic' }: SummaryPreviewProps) {
  const t = useTranslations('resume.layout.modules')
  const text = data?.text?.trim()

  const shouldRenderLine = (lineIndex: number) => !renderLines || renderLines.includes(lineIndex)
  const isEmerald = templateStyle === 'emerald'
  const isFormal = templateStyle === 'formal'

  return (
    <div>
      {shouldRenderLine(0) && (
        <h2
          data-line-index={0}
          className="text-lg font-bold text-gray-900 pb-1 border-b border-gray-200"
          style={{ marginBottom: COMPACT_HEADING_GAP_STYLE }}
        >
          {isEmerald ? <span className="resume-emerald-heading-label">{t('summary')}</span> : t('summary')}
        </h2>
      )}
      {text && shouldRenderLine(1) && isEmerald && (
        <ul data-line-index={1} className="resume-emerald-list text-sm">
          <li style={{ margin: 0 }}>{text}</li>
        </ul>
      )}
      {text && shouldRenderLine(1) && isFormal && (
        <ul data-line-index={1} className="list-disc text-sm text-gray-900" style={{ lineHeight: 'var(--resume-formal-line-height)', paddingLeft: 18, margin: 0 }}>
          <li>{text}</li>
        </ul>
      )}
      {text && shouldRenderLine(1) && !isEmerald && !isFormal && (
        <ul
          data-line-index={1}
          className="list-disc list-inside text-sm text-gray-900"
          style={{ lineHeight: 'var(--resume-body-line-height)', margin: 0 }}
        >
          <li>{text}</li>
        </ul>
      )}
    </div>
  )
}
