// 用于提供 components/preview/ResumePage.tsx 模块。
import React, { forwardRef } from 'react'
import { A4_HEIGHT, A4_WIDTH, PAGE_PADDING } from './hooks/useLineBasedPagination'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'

interface ResumePageProps {
  pageNumber: number
  totalPages: number
  children: React.ReactNode
  className?: string
  templateStyle?: ResumeTemplateStyle
}

const ResumePage = forwardRef<HTMLDivElement, ResumePageProps>(
  ({ pageNumber, totalPages, children, className = '', templateStyle = 'classic' }, ref) => {
    const pageRatio = A4_WIDTH / A4_HEIGHT
    
    return (
      <div
        ref={ref}
        className={`resume-page resume-template-${templateStyle} relative bg-white border border-gray-200 mx-auto mb-6 ${className}`}
        style={{
          width: `${A4_WIDTH}px`, // 基础宽度，会被transform scale缩放
          aspectRatio: `${pageRatio}`,
          paddingTop: `calc(var(--spacing-scale, 1) * ${PAGE_PADDING}px)`,
          paddingBottom: `calc(var(--spacing-scale, 1) * ${PAGE_PADDING}px)`,
          paddingLeft: `${PAGE_PADDING}px`,
          paddingRight: `${PAGE_PADDING}px`,
          boxSizing: 'border-box'
        }}
      >
        {/* 页面内容 */}
        <div className="relative z-10 h-full overflow-hidden">
          {children}
        </div>

        {/* 页码水印 */}
        {totalPages > 1 && (
          <div className="absolute bottom-3 right-4 text-xs text-gray-400 font-medium print:opacity-50">
            {pageNumber} / {totalPages}
          </div>
        )}

        {/* 分页线已移除 - 不再显示页面间的分隔线 */}
      </div>
    )
  }
)

ResumePage.displayName = 'ResumePage'

export default ResumePage
