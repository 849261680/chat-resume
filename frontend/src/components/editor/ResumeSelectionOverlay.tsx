'use client'
// 用于把简历/聊天选区工具条隔离到独立渲染层。

import { forwardRef, useCallback, useImperativeHandle, useLayoutEffect, useRef, useState } from 'react'
import type {
  ClipboardEvent as ReactClipboardEvent,
  PointerEvent as ReactPointerEvent,
  RefObject,
} from 'react'
import { createPortal } from 'react-dom'
import QuickEditPopover from './QuickEditPopover'

type ResumeSelectionSource = 'preview' | 'chat'

const ESTIMATED_SELECTION_TOOLBAR_WIDTH_BY_SOURCE: Record<ResumeSelectionSource, number> = {
  preview: 336,
  chat: 168,
}
const ESTIMATED_SELECTION_TOOLBAR_HEIGHT = 34
const QUICK_EDIT_POPOVER_WIDTH = 360
const QUICK_EDIT_POPOVER_HEIGHT = 64
const SELECTION_OVERLAY_GAP = 8

interface ResumeSelectionAction {
  source: ResumeSelectionSource
  text: string
  top: number
  quickEditTop: number
  left: number
  quickEditLeft: number
  anchorCenter: number
  selectionTop: number
  selectionBottom: number
  panelWidth: number
  panelHeight: number
  highlightRects: Array<{
    top: number
    left: number
    width: number
    height: number
  }>
  mode: 'toolbar' | 'quick_edit'
}

export interface ResumeSelectionOverlayHandle {
  updateSelectionAction: () => void
  handleMainCopy: (event: ReactClipboardEvent<HTMLElement>) => void
  handleMainPointerDown: (event: ReactPointerEvent<HTMLElement>) => void
}

interface ResumeSelectionOverlayProps {
  previewPanelRef: RefObject<HTMLDivElement>
  agentPanelRef: RefObject<HTMLDivElement>
  messagesContainerRef: RefObject<HTMLDivElement>
  pasteLabel: string
  isSending: boolean
  isStreaming: boolean
  appendToInputMessage: (text: string) => void
  sendMessageWithContext: (selectedText: string, userPrompt: string) => Promise<void>
}

/** 将浮层左侧位置限制在容器可视范围内。 */
function clampOverlayLeft(anchorLeft: number, panelWidth: number, overlayWidth: number): number {
  const safeOverlayWidth = Math.min(overlayWidth, panelWidth - 16)
  const maxLeft = Math.max(8, panelWidth - safeOverlayWidth - 8)
  return Math.min(Math.max(anchorLeft, 8), maxLeft)
}

/** 将浮层顶部位置限制在容器可视范围内。 */
function clampOverlayTop(anchorTop: number, panelHeight: number, overlayHeight: number): number {
  const safeOverlayHeight = Math.min(overlayHeight, panelHeight - 16)
  const maxTop = Math.max(8, panelHeight - safeOverlayHeight - 8)
  return Math.min(Math.max(anchorTop, 8), maxTop)
}

/** 按选区中心计算浮层位置，优先贴近选区上方，空间不足则放到下方。 */
function getSelectionOverlayPosition(
  action: Pick<ResumeSelectionAction, 'anchorCenter' | 'selectionTop' | 'selectionBottom' | 'panelWidth' | 'panelHeight'>,
  overlayWidth: number,
  overlayHeight: number
) {
  const left = clampOverlayLeft(action.anchorCenter - overlayWidth / 2, action.panelWidth, overlayWidth)
  const topAbove = action.selectionTop - overlayHeight - SELECTION_OVERLAY_GAP
  if (topAbove >= 8) return { left, top: topAbove }

  return {
    left,
    top: clampOverlayTop(action.selectionBottom + SELECTION_OVERLAY_GAP, action.panelHeight, overlayHeight),
  }
}

/** 从当前浏览器选区里读取所属元素。 */
function getSelectionElement(range: Range): Element | null {
  const rangeNode = range.commonAncestorContainer
  return rangeNode.nodeType === Node.ELEMENT_NODE
    ? rangeNode as Element
    : rangeNode.parentElement
}

/** 清理浏览器原生选区。自绘高亮由 React 状态卸载。 */
function clearResumeSelectionVisuals() {
  window.getSelection()?.removeAllRanges()
}

/** 多次清理选区视觉，覆盖浏览器在 pointerup/click 后恢复旧选区的时序。 */
function clearResumeSelectionVisualsAfterEvents() {
  clearResumeSelectionVisuals()
  window.requestAnimationFrame(() => {
    clearResumeSelectionVisuals()
    window.requestAnimationFrame(clearResumeSelectionVisuals)
  })
  window.setTimeout(clearResumeSelectionVisuals, 40)
  window.setTimeout(clearResumeSelectionVisuals, 250)
}

/** 将原生选区转换成相对容器定位的浮层状态。 */
function buildSelectionAction(
  range: Range,
  panel: HTMLElement,
  text: string,
  source: ResumeSelectionSource,
  highlightPanel: HTMLElement = panel
): ResumeSelectionAction {
  const rangeRect = range.getBoundingClientRect()
  const panelRect = panel.getBoundingClientRect()
  const highlightPanelRect = highlightPanel.getBoundingClientRect()
  const highlightRects = Array.from(range.getClientRects())
    .filter((rect) => rect.width > 0 && rect.height > 0)
    .map((rect) => ({
      top: rect.top - highlightPanelRect.top + highlightPanel.scrollTop,
      left: rect.left - highlightPanelRect.left + highlightPanel.scrollLeft,
      width: rect.width,
      height: rect.height,
    }))
  const selectionTop = rangeRect.top - panelRect.top
  const selectionBottom = rangeRect.bottom - panelRect.top
  const selectionCenter = rangeRect.left - panelRect.left + rangeRect.width / 2
  const basePosition = {
    anchorCenter: selectionCenter,
    selectionTop,
    selectionBottom,
    panelWidth: panelRect.width,
    panelHeight: panelRect.height,
  }
  const toolbarPosition = getSelectionOverlayPosition(
    basePosition,
    ESTIMATED_SELECTION_TOOLBAR_WIDTH_BY_SOURCE[source],
    ESTIMATED_SELECTION_TOOLBAR_HEIGHT
  )
  const quickEditPosition = getSelectionOverlayPosition(
    basePosition,
    QUICK_EDIT_POPOVER_WIDTH,
    QUICK_EDIT_POPOVER_HEIGHT
  )
  return {
    source,
    text,
    top: toolbarPosition.top,
    quickEditTop: quickEditPosition.top,
    left: toolbarPosition.left,
    quickEditLeft: quickEditPosition.left,
    ...basePosition,
    highlightRects,
    mode: 'toolbar',
  }
}

// 用于渲染选区工具条和高亮层，并向父页面暴露事件入口。
const ResumeSelectionOverlay = forwardRef<ResumeSelectionOverlayHandle, ResumeSelectionOverlayProps>(function ResumeSelectionOverlay({
  previewPanelRef,
  agentPanelRef,
  messagesContainerRef,
  pasteLabel,
  isSending,
  isStreaming,
  appendToInputMessage,
  sendMessageWithContext,
}, ref) {
  const [selectionAction, setSelectionAction] = useState<ResumeSelectionAction | null>(null)
  const toolbarRef = useRef<HTMLDivElement | null>(null)

  useLayoutEffect(() => {
    const toolbar = toolbarRef.current
    if (!toolbar || selectionAction?.mode !== 'toolbar') return

    const measuredPosition = getSelectionOverlayPosition(
      selectionAction,
      toolbar.offsetWidth,
      toolbar.offsetHeight
    )
    if (Math.abs(measuredPosition.left - selectionAction.left) < 1 &&
      Math.abs(measuredPosition.top - selectionAction.top) < 1
    ) return

    setSelectionAction({ ...selectionAction, ...measuredPosition })
  }, [selectionAction])

  const clearSelectionAction = useCallback(() => {
    clearResumeSelectionVisualsAfterEvents()
    setSelectionAction(null)
  }, [])

  const pasteSelectionToChat = useCallback(() => {
    if (!selectionAction) return
    appendToInputMessage(selectionAction.text)
    clearSelectionAction()
  }, [appendToInputMessage, clearSelectionAction, selectionAction])

  const quickEditSelection = useCallback(() => {
    if (!selectionAction) return
    setSelectionAction({ ...selectionAction, mode: 'quick_edit' })
  }, [selectionAction])

  const submitQuickEditSelection = useCallback(async (selectedText: string, userPrompt: string) => {
    if (!selectedText.trim() || !userPrompt.trim()) return
    clearSelectionAction()
    await sendMessageWithContext(selectedText, userPrompt)
  }, [clearSelectionAction, sendMessageWithContext])

  const updateSelectionAction = useCallback(() => {
    const previewPanel = previewPanelRef.current
    const agentPanel = agentPanelRef.current
    const messagesPanel = messagesContainerRef.current
    const selection = window.getSelection()
    if (!previewPanel || !agentPanel || !messagesPanel || !selection || selection.rangeCount === 0) {
      setSelectionAction(null)
      return
    }

    const selectedText = selection.toString().trim()
    const range = selection.getRangeAt(0)
    const selectedElement = getSelectionElement(range)
    if (!selectedText || !selectedElement) {
      setSelectionAction(null)
      return
    }

    if (previewPanel.contains(selectedElement)) {
      setSelectionAction(buildSelectionAction(range, previewPanel, selectedText, 'preview'))
      return
    }
    if (messagesPanel.contains(selectedElement)) {
      setSelectionAction(buildSelectionAction(range, agentPanel, selectedText, 'chat', messagesPanel))
      return
    }
    setSelectionAction(null)
  }, [agentPanelRef, messagesContainerRef, previewPanelRef])

  const handleMainPointerDown = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    const target = event.target
    if (!(target instanceof Element)) return
    if (target.closest('[data-resume-selection-action="true"]')) return
    if (!selectionAction && !window.getSelection()?.toString()) return
    const isSelectionPanel = Boolean(
      previewPanelRef.current?.contains(target) ||
      messagesContainerRef.current?.contains(target)
    )
    if (isSelectionPanel) {
      setSelectionAction(null)
      return
    }
    clearSelectionAction()
  }, [clearSelectionAction, messagesContainerRef, previewPanelRef, selectionAction])

  const handleMainCopy = useCallback((event: ReactClipboardEvent<HTMLElement>) => {
    if (selectionAction?.mode !== 'toolbar') return
    if (!selectionAction.text.trim()) return
    const target = event.target
    if (target instanceof Element && target.closest('[data-resume-selection-action="true"]')) return
    event.clipboardData.setData('text/plain', selectionAction.text)
    event.preventDefault()
  }, [selectionAction])

  useImperativeHandle(ref, () => ({
    updateSelectionAction,
    handleMainCopy,
    handleMainPointerDown,
  }), [handleMainCopy, handleMainPointerDown, updateSelectionAction])

  const previewPanel = previewPanelRef.current
  const agentPanel = agentPanelRef.current
  const messagesPanel = messagesContainerRef.current

  return (
    <>
      {previewPanel && selectionAction?.source === 'preview' && selectionAction.mode === 'toolbar' && createPortal(
        <div
          ref={toolbarRef}
          data-resume-selection-action="true"
          className="absolute z-30 inline-flex items-center overflow-hidden whitespace-nowrap text-sm font-normal shadow-sm print:hidden"
          style={{
            top: selectionAction.top,
            left: selectionAction.left,
            borderRadius: '2px',
            backgroundColor: '#0052ff',
            border: '1px solid #0052ff',
            color: '#ffffff',
          }}
          onPointerDown={(event) => event.stopPropagation()}
          onMouseDown={(event) => event.preventDefault()}
          onMouseUp={(event) => event.stopPropagation()}
        >
          <button
            type="button"
            className="inline-flex items-center gap-1 px-1 py-0.5 transition-colors"
            onClick={pasteSelectionToChat}
          >
            <span>{pasteLabel}</span>
          </button>
          <div className="h-4 w-px" style={{ backgroundColor: 'rgba(255,255,255,0.35)' }} />
          <button
            type="button"
            className="inline-flex items-center px-1 py-0.5 transition-colors"
            onClick={quickEditSelection}
          >
            <span>快速优化</span>
          </button>
        </div>,
        previewPanel
      )}

      {previewPanel && selectionAction?.source === 'preview' && selectionAction.mode === 'quick_edit' && createPortal(
        <>
          {selectionAction.highlightRects.map((rect, index) => (
            <div
              key={`${rect.top}-${rect.left}-${index}`}
              data-testid="resume-selection-highlight"
              className="pointer-events-none absolute z-20 rounded-[2px] print:hidden"
              style={{
                top: rect.top,
                left: rect.left,
                width: rect.width,
                height: rect.height,
                backgroundColor: 'rgba(0,82,255,0.22)',
              }}
            />
          ))}
          <QuickEditPopover
            selectedText={selectionAction.text}
            top={selectionAction.quickEditTop}
            left={selectionAction.quickEditLeft}
            disabled={isSending || isStreaming}
            onClose={clearSelectionAction}
            onSubmit={(selectedText, prompt) => void submitQuickEditSelection(selectedText, prompt)}
          />
        </>,
        previewPanel
      )}

      {agentPanel && selectionAction?.source === 'chat' && selectionAction.mode === 'toolbar' && createPortal(
        <div
          ref={toolbarRef}
          data-resume-selection-action="true"
          className="absolute z-30 inline-flex items-center overflow-hidden whitespace-nowrap text-sm font-normal shadow-sm"
          style={{
            top: selectionAction.top,
            left: selectionAction.left,
            borderRadius: '2px',
            backgroundColor: '#0052ff',
            border: '1px solid #0052ff',
            color: '#ffffff',
          }}
          onPointerDown={(event) => event.stopPropagation()}
          onMouseDown={(event) => event.preventDefault()}
          onMouseUp={(event) => event.stopPropagation()}
        >
          <button
            type="button"
            className="inline-flex items-center gap-1 px-1 py-0.5 transition-colors"
            onClick={pasteSelectionToChat}
          >
            <span>{pasteLabel}</span>
          </button>
        </div>,
        agentPanel
      )}

      {messagesPanel && selectionAction?.source === 'chat' && selectionAction.mode === 'toolbar' && createPortal(
        <>
          {selectionAction.highlightRects.map((rect, index) => (
            <div
              key={`${rect.top}-${rect.left}-${index}`}
              data-testid="chat-selection-highlight"
              className="pointer-events-none absolute z-20 rounded-[2px]"
              style={{
                top: rect.top,
                left: rect.left,
                width: rect.width,
                height: rect.height,
                backgroundColor: 'rgba(0,82,255,0.22)',
              }}
            />
          ))}
        </>,
        messagesPanel
      )}
    </>
  )
})

export default ResumeSelectionOverlay
