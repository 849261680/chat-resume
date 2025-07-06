import { useState, useEffect, useCallback } from 'react'

// A4纸张尺寸常量 (96 DPI)
export const A4_HEIGHT = 1056 // A4高度像素值
export const A4_WIDTH = 816   // A4宽度像素值
export const PAGE_MARGIN = 40  // 页边距
export const PAGE_PADDING = 32 // 内容区域内边距

interface ContentSection {
  id: string
  element: HTMLElement
  height: number
  canBreak: boolean // 是否可以在此处分页
}

interface PageContent {
  sections: ContentSection[]
  height: number
}

interface ResumePaginationOptions {
  containerRef: React.RefObject<HTMLElement>
  contentRef: React.RefObject<HTMLElement>
  pageHeight?: number
}

export function useResumePagination({
  containerRef,
  contentRef,
  pageHeight = A4_HEIGHT - PAGE_MARGIN * 2 - PAGE_PADDING * 2
}: ResumePaginationOptions) {
  const [pages, setPages] = useState<PageContent[]>([])
  const [totalPages, setTotalPages] = useState(1)
  const [isCalculating, setIsCalculating] = useState(false)

  // 测量内容区域各section的高度
  const measureSections = useCallback((): ContentSection[] => {
    if (!contentRef.current) return []

    const sections: ContentSection[] = []
    const children = contentRef.current.children

    for (let i = 0; i < children.length; i++) {
      const element = children[i] as HTMLElement
      const id = element.id || `section-${i}`
      
      // 确保元素已渲染并可测量
      if (element.offsetHeight > 0) {
        sections.push({
          id,
          element,
          height: element.offsetHeight,
          canBreak: true // 默认在每个section后可以分页
        })
      }
    }

    return sections
  }, [contentRef])

  // 分页算法
  const calculatePages = useCallback((sections: ContentSection[]): PageContent[] => {
    if (sections.length === 0) {
      return [{ sections: [], height: 0 }]
    }

    const pages: PageContent[] = []
    let currentPage: PageContent = { sections: [], height: 0 }

    for (const section of sections) {
      // 检查当前页是否能容纳这个section
      const projectedHeight = currentPage.height + section.height

      if (projectedHeight <= pageHeight || currentPage.sections.length === 0) {
        // 可以容纳在当前页
        currentPage.sections.push(section)
        currentPage.height = projectedHeight
      } else {
        // 需要新页面
        if (currentPage.sections.length > 0) {
          pages.push(currentPage)
        }
        
        // 开始新页面
        currentPage = {
          sections: [section],
          height: section.height
        }
      }
    }

    // 添加最后一页
    if (currentPage.sections.length > 0) {
      pages.push(currentPage)
    }

    return pages.length > 0 ? pages : [{ sections: [], height: 0 }]
  }, [pageHeight])

  // 重新计算分页
  const recalculatePagination = useCallback(async () => {
    if (!containerRef.current || !contentRef.current) return

    setIsCalculating(true)

    try {
      // 等待DOM更新完成
      await new Promise(resolve => setTimeout(resolve, 100))

      const sections = measureSections()
      const calculatedPages = calculatePages(sections)
      
      setPages(calculatedPages)
      setTotalPages(calculatedPages.length)
    } catch (error) {
      console.error('Error calculating pagination:', error)
      // 出错时显示单页
      setPages([{ sections: [], height: 0 }])
      setTotalPages(1)
    } finally {
      setIsCalculating(false)
    }
  }, [containerRef, contentRef, measureSections, calculatePages])

  // 监听内容变化
  useEffect(() => {
    if (!contentRef.current) return

    const resizeObserver = new ResizeObserver(() => {
      recalculatePagination()
    })

    // 观察内容容器的尺寸变化
    resizeObserver.observe(contentRef.current)

    // 观察所有子元素的变化
    const children = contentRef.current.children
    for (let i = 0; i < children.length; i++) {
      resizeObserver.observe(children[i])
    }

    // 初始计算
    recalculatePagination()

    return () => {
      resizeObserver.disconnect()
    }
  }, [recalculatePagination])

  // 监听窗口大小变化
  useEffect(() => {
    const handleResize = () => {
      recalculatePagination()
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [recalculatePagination])

  return {
    pages,
    totalPages,
    isCalculating,
    recalculatePagination,
    pageHeight,
    A4_WIDTH,
    PAGE_MARGIN,
    PAGE_PADDING
  }
}