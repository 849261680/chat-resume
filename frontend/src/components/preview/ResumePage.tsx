import React, { forwardRef } from 'react'
import { A4_WIDTH, PAGE_MARGIN, PAGE_PADDING } from './hooks/useResumePagination'

interface ResumePageProps {
  pageNumber: number
  totalPages: number
  children: React.ReactNode
  className?: string
}

const ResumePage = forwardRef<HTMLDivElement, ResumePageProps>(
  ({ pageNumber, totalPages, children, className = '' }, ref) => {
    // A4纸张比例: 210mm x 297mm = 0.7070
    const A4_RATIO = 210 / 297
    
    return (
      <div
        ref={ref}
        className={`resume-page relative bg-white shadow-lg border border-gray-200 mx-auto mb-6 ${className}`}
        style={{
          width: `${A4_WIDTH}px`, // 基础宽度，会被transform scale缩放
          aspectRatio: `${A4_RATIO}`, // 保持A4比例
          margin: '0 auto 24px auto',
          padding: `${PAGE_PADDING}px`,
          boxSizing: 'border-box'
        }}
      >
        {/* 页面内容 */}
        <div className="relative z-10 h-full overflow-hidden">
          {children}
        </div>

        {/* 页码水印 */}
        {totalPages > 1 && (
          <div className="absolute bottom-4 right-6 text-xs text-gray-400 font-medium">
            {pageNumber} / {totalPages}
          </div>
        )}

        {/* 分页线 (除了最后一页) */}
        {pageNumber < totalPages && (
          <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 w-16 h-px bg-gradient-to-r from-transparent via-gray-300 to-transparent" />
        )}
      </div>
    )
  }
)

ResumePage.displayName = 'ResumePage'

export default ResumePage