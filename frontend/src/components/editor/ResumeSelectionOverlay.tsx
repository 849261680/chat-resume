'use client'
// 用于把简历/聊天选区工具条隔离到独立渲染层。

import { forwardRef, useCallback, useImperativeHandle, useState } from 'react'
import type {
  ClipboardEvent as ReactClipboardEvent,
  PointerEvent as ReactPointerEvent,
  RefObject,
} from 'react'
import { createPortal } from 'react-dom'
import QuickEditPopover from './QuickEditPopover'

type ResumeSelectionSource = 'preview' | 'chat'

interface ResumeSelectionAction {
  source: ResumeSelectionSource
  text: string
  top: number
  quickEditTop: number
  left: number
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
  const actionWidth = Math.min(560, Math.max(230, panelRect.width - 16))
  const maxLeft = Math.max(8, panelRect.width - actionWidth - 8)
  const selectionTop = rangeRect.top - panelRect.top
  const selectionBottom = rangeRect.bottom - panelRect.top
  const left = Math.min(
    Math.max(rangeRect.right - panelRect.left + 8, 8),
    maxLeft
  )
  const top = Math.max(selectionTop - 40, 8)
  const quickEditHeight = 64
  const quickEditGap = 8
  const quickEditTop = selectionTop > quickEditHeight + quickEditGap
    ? selectionTop - quickEditHeight - quickEditGap
    : selectionBottom + quickEditGap
  return { source, text, top, quickEditTop, left, highlightRects, mode: 'toolbar' }
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
            className="inline-flex items-center gap-1.5 px-2.5 py-1 transition-colors"
            onClick={pasteSelectionToChat}
          >
            <span>{pasteLabel}</span>
          </button>
          <div className="h-5 w-px" style={{ backgroundColor: 'rgba(255,255,255,0.35)' }} />
          <button
            type="button"
            className="inline-flex items-center px-2.5 py-1 transition-colors"
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
            left={selectionAction.left}
            disabled={isSending || isStreaming}
            onClose={clearSelectionAction}
            onSubmit={(selectedText, prompt) => void submitQuickEditSelection(selectedText, prompt)}
          />
        </>,
        previewPanel
      )}

      {agentPanel && selectionAction?.source === 'chat' && selectionAction.mode === 'toolbar' && createPortal(
        <div
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
            className="inline-flex items-center gap-1.5 px-2.5 py-1 transition-colors"
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
