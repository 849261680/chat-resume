'use client'
// 用于提供 components/preview/ResumePreview.tsx 模块。

import { useEffect } from 'react'
import React from 'react'
import PaginatedResumePreview from './PaginatedResumePreview'
import type { ResumeContent } from '@/types/resume'
import type { ModuleConfig, ResumeTemplateStyle } from '@/types/resumeLayout'

interface ResumePreviewProps {
  content: ResumeContent
  moduleOrder?: ModuleConfig[]
  spacingScale?: number
  templateStyle?: ResumeTemplateStyle
  onSpacingScaleChange?: (scale: number) => void
  onTotalPagesChange?: (n: number) => void
  onRenderReady?: (ready: boolean) => void
  smartFitTriggerRef?: React.MutableRefObject<any>
  isContainerResizing?: boolean
}

// 用于渲染 ResumePreview 组件。
export default function ResumePreview({ content, moduleOrder, spacingScale, templateStyle = 'classic', onSpacingScaleChange, onTotalPagesChange, onRenderReady, smartFitTriggerRef, isContainerResizing = false }: ResumePreviewProps) {
  // 加载打印样式
  useEffect(() => {
    // 动态加载打印样式
    const loadPrintStyles = () => {
      if (typeof document !== 'undefined') {
        const existingLink = document.getElementById('resume-print-styles')
        if (!existingLink) {
          const link = document.createElement('link')
          link.id = 'resume-print-styles'
          link.rel = 'stylesheet'
          link.href = '/styles/resume-print.css'
          document.head.appendChild(link)
        }
      }
    }

    loadPrintStyles()
  }, [])

  return (
    <div className="h-full overflow-hidden bg-gray-50 p-1 print:h-auto print:p-0 print:bg-white">
      <PaginatedResumePreview
        content={content}
        moduleOrder={moduleOrder}
        spacingScale={spacingScale}
        templateStyle={templateStyle}
        onSpacingScaleChange={onSpacingScaleChange}
        onTotalPagesChange={onTotalPagesChange}
        onRenderReady={onRenderReady}
        smartFitTriggerRef={smartFitTriggerRef}
        isContainerResizing={isContainerResizing}
      />
    </div>
  )
}
