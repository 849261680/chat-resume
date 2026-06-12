/**
 * 编辑页三栏布局 Hook
 *
 * 用于集中管理左中右面板的宽度、折叠状态和拖拽逻辑。
 */

'use client'

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'

interface PanelFlexState {
  editorFlex: number
  agentFlex: number
}

/**
 * 提供编辑页三栏布局状态和拖拽处理函数。
 */
// 用于封装面板布局相关状态和行为。
export function usePanelLayout() {
  const [editorOpen, setEditorOpen] = useState(true)
  const [editorFlex, setEditorFlex] = useState(30)
  const [agentFlex, setAgentFlex] = useState(30)
  const [isResizingPanels, setIsResizingPanels] = useState(false)
  const mainPanelsRef = useRef<HTMLDivElement>(null)
  const resizeFrameRef = useRef<number | null>(null)
  const pendingPanelFlexRef = useRef<PanelFlexState | null>(null)
  const displayedPanelFlexRef = useRef<PanelFlexState>({ editorFlex: 30, agentFlex: 30 })

  const previewFlex = 100 - editorFlex - agentFlex
  const collapsedAgentFlex = 100 - previewFlex
  const editorAnimateWidth = useMemo(
    () => (editorOpen ? 'var(--editor-panel-width)' : '48px'),
    [editorOpen],
  )
  const panelLayoutStyle = useMemo(() => ({
    ['--editor-panel-width' as string]: editorOpen ? `calc(${editorFlex}% - 8px)` : '48px',
    ['--preview-panel-width' as string]: `calc(${previewFlex}% - 16px)`,
    ['--agent-panel-width' as string]: `calc(${editorOpen ? agentFlex : collapsedAgentFlex}% - 8px)`,
  }) as CSSProperties, [agentFlex, collapsedAgentFlex, editorFlex, editorOpen, previewFlex])

  // 用于把面板宽度写入 CSS 变量，不触发 React 重渲染。
  const applyPanelWidthVariables = useCallback((nextFlex: PanelFlexState) => {
    const panel = mainPanelsRef.current
    if (!panel) return

    const nextPreviewFlex = 100 - nextFlex.editorFlex - nextFlex.agentFlex
    const nextAgentPanelFlex = editorOpen ? nextFlex.agentFlex : 100 - nextPreviewFlex
    panel.style.setProperty('--editor-panel-width', editorOpen ? `calc(${nextFlex.editorFlex}% - 8px)` : '48px')
    panel.style.setProperty('--preview-panel-width', `calc(${nextPreviewFlex}% - 16px)`)
    panel.style.setProperty('--agent-panel-width', `calc(${nextAgentPanelFlex}% - 8px)`)
    displayedPanelFlexRef.current = nextFlex
  }, [editorOpen])

  // 用于把高频拖拽 DOM 写入合并到浏览器下一帧。
  const schedulePanelWidthApply = useCallback((nextFlex: PanelFlexState) => {
    pendingPanelFlexRef.current = nextFlex
    if (resizeFrameRef.current !== null) return

    resizeFrameRef.current = requestAnimationFrame(() => {
      resizeFrameRef.current = null
      const pendingFlex = pendingPanelFlexRef.current
      pendingPanelFlexRef.current = null
      if (pendingFlex) {
        applyPanelWidthVariables(pendingFlex)
      }
    })
  }, [applyPanelWidthVariables])

  // 用于在拖拽结束或卸载时执行最后一次 DOM 宽度更新。
  const flushPanelWidthApply = useCallback(() => {
    if (resizeFrameRef.current !== null) {
      cancelAnimationFrame(resizeFrameRef.current)
      resizeFrameRef.current = null
    }
    const pendingFlex = pendingPanelFlexRef.current
    pendingPanelFlexRef.current = null
    if (pendingFlex) {
      applyPanelWidthVariables(pendingFlex)
    }
  }, [applyPanelWidthVariables])

  // 用于恢复拖拽期间覆盖的全局鼠标样式。
  const resetResizeCursor = useCallback(() => {
    document.body.style.userSelect = ''
    document.body.style.cursor = ''
  }, [])

  // 用于清理拖拽留下的全局状态。
  const finishPanelResize = useCallback((shouldCommit: boolean) => {
    flushPanelWidthApply()
    if (shouldCommit) {
      const nextFlex = displayedPanelFlexRef.current
      setEditorFlex(nextFlex.editorFlex)
      setAgentFlex(nextFlex.agentFlex)
    }
    setIsResizingPanels(false)
    resetResizeCursor()
  }, [flushPanelWidthApply, resetResizeCursor])

  useEffect(() => {
    applyPanelWidthVariables({ editorFlex, agentFlex })
  }, [agentFlex, applyPanelWidthVariables, editorFlex])

  useEffect(() => {
    return () => {
      flushPanelWidthApply()
      resetResizeCursor()
    }
  }, [flushPanelWidthApply, resetResizeCursor])

  /**
   * 处理左侧编辑栏拖拽，保证中间预览区域保留最小宽度。
   */
  const handleEditorDividerPointerDown = useCallback((event: React.PointerEvent) => {
    event.preventDefault()
    const startX = event.clientX
    const startFlex = editorFlex
    setIsResizingPanels(true)
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'

    // 用于处理onpointermove。
    const onPointerMove = (moveEvent: PointerEvent) => {
      if (!mainPanelsRef.current) return
      const containerWidth = mainPanelsRef.current.offsetWidth
      const delta = moveEvent.clientX - startX
      const deltaFlex = (delta / containerWidth) * 100
      const nextEditorFlex = Math.min(45, Math.max(18, startFlex + deltaFlex))
      const previewFlex = 100 - nextEditorFlex - agentFlex
      if (previewFlex >= 25) {
        schedulePanelWidthApply({ editorFlex: nextEditorFlex, agentFlex })
      }
    }

    // 用于处理onpointerup。
    const onPointerUp = () => {
      finishPanelResize(true)
      document.removeEventListener('pointermove', onPointerMove)
      document.removeEventListener('pointerup', onPointerUp)
    }

    document.addEventListener('pointermove', onPointerMove)
    document.addEventListener('pointerup', onPointerUp)
  }, [agentFlex, editorFlex, finishPanelResize, schedulePanelWidthApply])

  /**
   * 处理右侧 Agent 栏拖拽，保证中间预览区域保留最小宽度。
   */
  const handleAgentDividerPointerDown = useCallback((event: React.PointerEvent) => {
    event.preventDefault()
    const startX = event.clientX
    const startFlex = agentFlex
    setIsResizingPanels(true)
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'

    // 用于处理onpointermove。
    const onPointerMove = (moveEvent: PointerEvent) => {
      if (!mainPanelsRef.current) return
      const containerWidth = mainPanelsRef.current.offsetWidth
      const delta = startX - moveEvent.clientX
      const deltaFlex = (delta / containerWidth) * 100
      const nextAgentFlex = Math.min(45, Math.max(18, startFlex + deltaFlex))
      const previewFlex = 100 - editorFlex - nextAgentFlex
      if (previewFlex >= 25) {
        schedulePanelWidthApply({ editorFlex, agentFlex: nextAgentFlex })
      }
    }

    // 用于处理onpointerup。
    const onPointerUp = () => {
      finishPanelResize(true)
      document.removeEventListener('pointermove', onPointerMove)
      document.removeEventListener('pointerup', onPointerUp)
    }

    document.addEventListener('pointermove', onPointerMove)
    document.addEventListener('pointerup', onPointerUp)
  }, [agentFlex, editorFlex, finishPanelResize, schedulePanelWidthApply])

  return {
    editorOpen,
    setEditorOpen,
    editorFlex,
    agentFlex,
    previewFlex,
    collapsedAgentFlex,
    editorAnimateWidth,
    isResizingPanels,
    panelLayoutStyle,
    mainPanelsRef,
    handleEditorDividerPointerDown,
    handleAgentDividerPointerDown,
  }
}
