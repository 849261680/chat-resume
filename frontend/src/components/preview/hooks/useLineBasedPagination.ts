import { useState, useEffect, useCallback, useRef } from 'react'

// A4纸张尺寸常量。
export const A4_WIDTH = 794
export const A4_HEIGHT = Math.floor(A4_WIDTH * 297 / 210)
export const PAGE_PADDING = 40
export const SAFETY_MARGIN = 20 // 容错余量，防止累计误差导致内容被切

const LINE_BOX_TOLERANCE = 2
const MIN_VISIBLE_RECT_SIZE = 0.5

// 可渲染的视觉行元素类型
export interface RenderableLine {
  id: string
  sectionType: string
  lineIndex: number
  visualIndex: number
  top: number
  bottom: number
  height: number
  element: HTMLElement
}

// 页面内容结构
export interface PageContent {
  lines: RenderableLine[]
  height: number
  startOffset: number
  endOffset: number
}

interface VisualLineBox {
  top: number
  bottom: number
}

// 用于合并同一视觉行上的多个文本矩形。
function mergeLineBox(boxes: VisualLineBox[], top: number, bottom: number) {
  const existing = boxes.find(box => Math.abs(box.top - top) <= LINE_BOX_TOLERANCE)
  if (!existing) {
    boxes.push({ top, bottom })
    return
  }

  existing.top = Math.min(existing.top, top)
  existing.bottom = Math.max(existing.bottom, bottom)
}

// 用于读取元素内每一条真实换行后的视觉文本行。
function measureElementLineBoxes(element: HTMLElement, contentTop: number): VisualLineBox[] {
  const boxes: VisualLineBox[] = []
  const range = document.createRange()
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT)
  const elementRect = element.getBoundingClientRect()
  let node = walker.nextNode()

  while (node) {
    const text = node.textContent?.trim()
    if (text) {
      range.selectNodeContents(node)
      Array.from(range.getClientRects()).forEach((rect) => {
        if (rect.width > MIN_VISIBLE_RECT_SIZE && rect.height > MIN_VISIBLE_RECT_SIZE) {
          mergeLineBox(boxes, rect.top - contentTop, rect.bottom - contentTop)
        }
      })
    }
    node = walker.nextNode()
  }

  range.detach()
  if (boxes.length === 0) {
    return [{ top: elementRect.top - contentTop, bottom: elementRect.bottom - contentTop }]
  }

  boxes.sort((a, b) => a.top - b.top)
  boxes[0].top = Math.min(boxes[0].top, elementRect.top - contentTop)
  boxes[boxes.length - 1].bottom = Math.max(boxes[boxes.length - 1].bottom, elementRect.bottom - contentTop)
  return boxes
}

// 用于测量真实视觉行，长项目不会再被当成不可拆分的大块。
export function measureRenderableLines(contentElement: HTMLElement | null): RenderableLine[] {
  if (!contentElement) return []

  const contentTop = contentElement.getBoundingClientRect().top
  const measuredLines: RenderableLine[] = []
  const lineElements = contentElement.querySelectorAll('[data-line-index]')

  lineElements.forEach((lineElement, lineElementIndex) => {
    const element = lineElement as HTMLElement
    const section = element.closest('[data-section-id]') as HTMLElement | null
    const sectionType = section?.getAttribute('data-section-id') || `section-${lineElementIndex}`
    const lineIndex = parseInt(element.getAttribute('data-line-index') || '0', 10)
    const elementRect = element.getBoundingClientRect()
    if (elementRect.width <= MIN_VISIBLE_RECT_SIZE || elementRect.height <= MIN_VISIBLE_RECT_SIZE) {
      return
    }


    measureElementLineBoxes(element, contentTop).forEach((box, visualIndex) => {
      measuredLines.push({
        id: `${sectionType}-line-${lineIndex}-${visualIndex}`,
        sectionType,
        lineIndex,
        visualIndex,
        top: box.top,
        bottom: box.bottom,
        height: box.bottom - box.top,
        element,
      })
    })
  })

  measuredLines.sort((a, b) => a.top - b.top)
  return measuredLines.map((line, index) => {
    const nextLine = measuredLines[index + 1]
    const end = nextLine?.top ?? Math.max(line.bottom, contentElement.scrollHeight)
    return { ...line, height: Math.max(end - line.top, line.bottom - line.top) }
  })
}

interface LineBasedPaginationOptions {
  containerRef: React.RefObject<HTMLElement>
  contentRef: React.RefObject<HTMLElement>
  pageHeight?: number
  fullBleed?: boolean
}

interface PageContentHeightOptions {
  pageHeight?: number
  fullBleed?: boolean
}

// 用于计算固定页边距下的页面可用内容高度。
export function getPageContentHeight(options: PageContentHeightOptions = {}): number {
  if (typeof options.pageHeight === 'number') return options.pageHeight
  const verticalPadding = options.fullBleed ? 0 : PAGE_PADDING * 2
  return A4_HEIGHT - verticalPadding - SAFETY_MARGIN
}

// 用于封装行based分页相关状态和行为。
export function useLineBasedPagination({
  containerRef,
  contentRef,
  pageHeight,
  fullBleed = false
}: LineBasedPaginationOptions) {
  const effectivePageHeight = getPageContentHeight({ pageHeight, fullBleed })
  const [pages, setPages] = useState<PageContent[]>([])
  const [totalPages, setTotalPages] = useState(1)
  const [contentHeight, setContentHeight] = useState(0)
  const [isCalculating, setIsCalculating] = useState(false)
  const calculationTimeoutRef = useRef<NodeJS.Timeout>()

  // 测量所有可分页的视觉行元素。
  const measureLines = useCallback((): RenderableLine[] => {
    return measureRenderableLines(contentRef.current)
  }, [contentRef])

  // 按视觉行坐标分页，断点始终落在下一行开始处。
  const calculatePages = useCallback((lines: RenderableLine[]): PageContent[] => {
    if (lines.length === 0) {
      return [{ lines: [], height: 0, startOffset: 0, endOffset: 0 }]
    }

    const pages: PageContent[] = []
    let startIndex = 0

    while (startIndex < lines.length) {
      const pageStart = lines[startIndex].top
      const pageLimit = pageStart + effectivePageHeight
      let endIndex = startIndex

      while (endIndex + 1 < lines.length && lines[endIndex + 1].bottom <= pageLimit) {
        endIndex += 1
      }

      const pageLines = lines.slice(startIndex, endIndex + 1)
      const lastLine = pageLines[pageLines.length - 1]
      pages.push({
        lines: pageLines,
        height: Math.max(lastLine.bottom - pageStart, 0),
        startOffset: pageStart,
        endOffset: lastLine.bottom,
      })
      startIndex = endIndex + 1
    }

    return pages.length > 0 ? pages : [{ lines: [], height: 0, startOffset: 0, endOffset: 0 }]
  }, [effectivePageHeight])

  // 重新计算分页
  const recalculatePagination = useCallback(async () => {
    if (!containerRef.current || !contentRef.current) return

    // 清除之前的计算定时器
    if (calculationTimeoutRef.current) {
      clearTimeout(calculationTimeoutRef.current)
    }

    setIsCalculating(true)

    try {
      // 等待DOM更新完成
      await new Promise(resolve => {
        calculationTimeoutRef.current = setTimeout(resolve, 100)
      })

      const lines = measureLines()
      const calculatedPages = calculatePages(lines)
      const totalHeight = lines.reduce((sum: number, l: RenderableLine) => sum + l.height, 0)

      setPages(calculatedPages)
      setTotalPages(calculatedPages.length)
      setContentHeight(totalHeight)
    } catch (error) {
      console.error('Pagination calculation error:', error)
      setPages([{ lines: [], height: 0, startOffset: 0, endOffset: 0 }])
      setTotalPages(1)
    } finally {
      setIsCalculating(false)
    }
  }, [containerRef, contentRef, measureLines, calculatePages])

  // 监听内容变化
  useEffect(() => {
    if (!contentRef.current) return

    const resizeObserver = new ResizeObserver(() => {
      recalculatePagination()
    })

    // 观察内容容器
    resizeObserver.observe(contentRef.current)

    // 观察所有子元素
    const children = contentRef.current.children
    for (let i = 0; i < children.length; i++) {
      resizeObserver.observe(children[i])
    }

    // 初始计算
    recalculatePagination()

    return () => {
      resizeObserver.disconnect()
      if (calculationTimeoutRef.current) {
        clearTimeout(calculationTimeoutRef.current)
      }
    }
  }, [contentRef, recalculatePagination])

  // 监听窗口大小变化
  useEffect(() => {
    // 用于处理尺寸变化。
    const handleResize = () => {
      recalculatePagination()
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [recalculatePagination])

  return {
    pages,
    totalPages,
    contentHeight,
    isCalculating,
    recalculatePagination,
    measureLines,
    pageHeight: effectivePageHeight,
    A4_WIDTH,
    PAGE_PADDING
  }
}
