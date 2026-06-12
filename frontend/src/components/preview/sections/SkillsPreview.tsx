'use client'
// 用于提供 components/preview/sections/SkillsPreview.tsx 模块。

import type { Skill } from '@/types/resume'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'
import { useTranslations } from 'next-intl'

interface SkillsPreviewProps {
  data: Skill[]
  renderLines?: number[] // 指定渲染哪些行
  templateStyle?: ResumeTemplateStyle
}

// 用于渲染 SkillsPreview 组件。
export default function SkillsPreview({ data, renderLines, templateStyle = 'classic' }: SkillsPreviewProps) {
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
        <h2
          data-line-index={0}
          className="text-lg font-bold text-gray-900 pb-1 border-b border-gray-200"
          style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)' }}
        >
          {templateStyle === 'emerald' ? (
            <span className="resume-emerald-heading-label">{t('skills')}</span>
          ) : t('skills')}
        </h2>
      )}

      {/* 每个技能类别作为独立的行 */}
      {data.map((group, categoryIndex) => {
        const lineIndex = categoryIndex + 1
        const isFormal = templateStyle === 'formal'
        const isEmerald = templateStyle === 'emerald'
        return shouldRenderLine(lineIndex) ? (
          isFormal || isEmerald ? (
            <ul
              key={group.id || `${group.category}-${categoryIndex}`}
              data-line-index={lineIndex}
              className={isEmerald ? 'resume-emerald-list text-sm' : 'list-disc text-sm text-gray-900'}
              style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)', paddingLeft: 18, lineHeight: isEmerald ? 'var(--resume-emerald-line-height)' : 'var(--resume-formal-line-height)' }}
            >
              <li>
                <span className="font-semibold">{group.category}：</span>
                {(group.items || []).join(isEmerald ? '、 ' : '、')}
              </li>
            </ul>
          ) : (
            <div
              key={group.id || `${group.category}-${categoryIndex}`}
              data-line-index={lineIndex}
              className="flex flex-wrap items-center gap-2 text-sm text-gray-700"
              style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 6px)' }}
            >
              <span className="font-semibold text-gray-800 flex-shrink-0">
                {group.category}
              </span>
              <div className="flex flex-wrap items-center gap-1.5">
                {(group.items || []).map((skill, index) => (
                  <span
                    key={`${group.id || group.category}-${index}-${skill}`}
                    className="text-xs text-gray-800 bg-gray-50 rounded-full px-2.5 py-0.5"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )
        ) : null
      })}
    </div>
  )
}
