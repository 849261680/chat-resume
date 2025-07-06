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
    return (
      <div
        ref={ref}
        className={`resume-page relative bg-white shadow-lg border border-gray-200 mx-auto mb-6 ${className}`}
        style={{
          width: `${A4_WIDTH}px`,
          minHeight: '1056px', // A4高度
          maxWidth: '100%',
          margin: '0 auto 24px auto',
          padding: `${PAGE_PADDING}px`,
          boxSizing: 'border-box'
        }}
      >
        {/* 页面内容 */}
        <div className="relative z-10 h-full">
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