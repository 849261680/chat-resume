'use client'
// 用于提供 app/[locale]/resume/[id]/edit/page.tsx 模块。

import { motion, AnimatePresence } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  ClipboardEvent as ReactClipboardEvent,
  PointerEvent as ReactPointerEvent,
} from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import { useRouter } from '@/i18n/navigation'
import { useAuth } from '@/lib/auth'
import { resumeApi, type Resume } from '@/lib/api'
import { formatApiErrorMessage } from '@/lib/apiErrors'
import { Link } from '@/i18n/navigation'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import {
  ArrowLeftIcon,
  ArrowUpIcon,
  ArrowDownTrayIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  PlayCircleIcon,
  TrashIcon,
  XMarkIcon
} from '@heroicons/react/24/outline'
import JobApplicationEditor from '@/components/editor/JobApplicationEditor'
import {
  AgentStreamEventList,
  summarizeRenderedToolEvents,
} from '@/components/editor/AgentStreamEventList'
import PersonalInfoEditor from '@/components/editor/PersonalInfoEditor'
import SummaryEditor from '@/components/editor/SummaryEditor'
import EducationEditor from '@/components/editor/EducationEditor'
import WorkExperienceEditor from '@/components/editor/WorkExperienceEditor'
import SkillsEditor from '@/components/editor/SkillsEditor'
import ProjectsEditor from '@/components/editor/ProjectsEditor'
import ResumePreview from '@/components/preview/ResumePreview'
import ResumeLayoutControls from '@/components/preview/ResumeLayoutControls'
import MarkdownMessage from '@/components/ui/MarkdownMessage'
import type { ChatMessage, StreamEvent } from '@/hooks/useStreamingChat'
import { usePanelLayout } from '@/hooks/usePanelLayout'
import { useResumeChatPanel } from '@/hooks/useResumeChatPanel'
import { useResumeEditor } from '@/hooks/useResumeEditor'
import ChatInputBox from '@/components/editor/ChatInputBox'
import UserInputRequestCard from '@/components/editor/UserInputRequestCard'
import { useLocale, useTranslations } from 'next-intl'
import { toInterviewLanguage, type AppLocale } from '@/i18n/routing'
import toast from 'react-hot-toast'

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

/** 从当前浏览器选区里读取所属元素。 */
function getSelectionElement(range: Range): Element | null {
  const rangeNode = range.commonAncestorContainer
  return rangeNode.nodeType === Node.ELEMENT_NODE
    ? rangeNode as Element
    : rangeNode.parentElement
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

/** 从 Next 路由参数中读取单个简历 ID。 */
function getResumeIdParam(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) {
    return value[0]
  }
  return value
}

/** 判断路由简历 ID 是否能安全传给后端整数路径参数。 */
function isValidResumeIdParam(value: string | undefined): value is string {
  return Boolean(value && /^\d+$/.test(value))
}

/** 清理浏览器原生选区，避免关闭快速优化后预览里残留蓝色选中态。 */
function clearNativeSelection() {
  window.getSelection()?.removeAllRanges()
}

/** 清理浏览器原生选区。自绘高亮由 React 状态卸载。 */
function clearResumeSelectionVisuals() {
  clearNativeSelection()
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
/** 描述选区快捷优化消息中的引用内容和用户要求。 */
interface SelectedResumeUserMessage {
  selectedText: string
  userRequest: string
}

/** 拆出选区快捷优化消息，保留发送给 Agent 的原始文本协议。 */
function parseSelectedResumeUserMessage(content: string): SelectedResumeUserMessage | null {
  const selectedPrefix = '选中的简历内容：\n'
  if (!content.startsWith(selectedPrefix)) return null

  const separator = '\n\n用户要求：\n'
  const body = content.slice(selectedPrefix.length)
  const separatorIndex = body.indexOf(separator)
  if (separatorIndex === -1) {
    return { selectedText: body.trim(), userRequest: '' }
  }

  return {
    selectedText: body.slice(0, separatorIndex).trim(),
    userRequest: body.slice(separatorIndex + separator.length).trim(),
  }
}

/** 渲染用户消息，把选中简历内容降级为外置引用块，把用户要求作为主体。 */
function UserMessageContent({ content }: { content: string }) {
  const selectedMessage = parseSelectedResumeUserMessage(content)
  if (!selectedMessage) {
    return (
      <div
        className="rounded-[20px] px-4 py-3 text-[14px] leading-relaxed text-white"
        style={{ borderRadius: '20px 20px 6px 20px', backgroundColor: '#0052ff' }}
      >
        <span className="whitespace-pre-wrap break-words">{content}</span>
      </div>
    )
  }

  const isContextTruncated = selectedMessage.selectedText.length > 92
  const previewText = isContextTruncated
    ? `${selectedMessage.selectedText.slice(0, 92)}…`
    : selectedMessage.selectedText

  return (
    <div className="flex flex-col items-end gap-2 text-left">
      <details
        data-testid="selected-resume-message-context"
        className="group w-full rounded-2xl border border-[#e4e7f2] bg-[#f8f7ff] px-3 py-2 text-[#0a0b0d] shadow-sm"
      >
        <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
          <span className="flex items-center justify-between gap-3">
            <span className="text-[11px] font-semibold leading-none text-[#0052ff]">
              引用
            </span>
            {isContextTruncated && (
              <span className="shrink-0 text-[11px] font-medium text-[#5b616e]">
                <span className="group-open:hidden">展开全文</span>
                <span className="hidden group-open:inline">收起</span>
              </span>
            )}
          </span>
          <span className="mt-1.5 block whitespace-pre-wrap break-words text-xs leading-relaxed text-[#3f4652] group-open:hidden">
            {previewText}
          </span>
        </summary>
        <div className="mt-2 border-t border-gray-100 pt-2 text-xs leading-relaxed text-[#3f4652]">
          <p className="whitespace-pre-wrap break-words">{selectedMessage.selectedText}</p>
        </div>
      </details>
      {selectedMessage.userRequest && (
        <p
          data-testid="selected-resume-message-request"
          className="max-w-full whitespace-pre-wrap break-words px-4 py-3 text-[14px] font-medium leading-relaxed text-white"
          style={{ borderRadius: '20px 20px 6px 20px', backgroundColor: '#0052ff' }}
        >
          {selectedMessage.userRequest}
        </p>
      )}
    </div>
  )
}

/** 编辑页组件用于组装简历编辑、预览和 Agent 面板。 */
export default function ResumeEditPage() {
  const params = useParams()
  const router = useRouter()
  const { isAuthenticated, isLoading } = useAuth()
  const locale = useLocale() as AppLocale
  const [mounted, setMounted] = useState(false)
  const [isCreatingInterview, setIsCreatingInterview] = useState(false)
  const [resumeSelectionAction, setResumeSelectionAction] = useState<ResumeSelectionAction | null>(null)
  const [quickEditPrompt, setQuickEditPrompt] = useState('')
  const [toolFeedbackDrafts, setToolFeedbackDrafts] = useState<Record<string, string>>({})
  const quickEditInputRef = useRef<HTMLTextAreaElement>(null)
  const previewPanelRef = useRef<HTMLDivElement>(null)
  const agentPanelRef = useRef<HTMLDivElement>(null)
  const t = useTranslations('resume.editor')
  const common = useTranslations('common')

  const routeResumeId = getResumeIdParam(params?.id)
  const hasValidResumeId = isValidResumeIdParam(routeResumeId)
  const resumeId = hasValidResumeId ? routeResumeId : ''
  const searchParams = useSearchParams()
  const isFirstRun = searchParams?.get('firstRun') === '1'
  const [firstRunPhase, setFirstRunPhase] = useState<'jd_input' | 'analyzing' | 'done' | null>(null)
  const [firstRunTargetCompany, setFirstRunTargetCompany] = useState('')
  const [firstRunTargetTitle, setFirstRunTargetTitle] = useState('')
  const [firstRunJdText, setFirstRunJdText] = useState('')
  const firstRunTriggeredRef = useRef(false)
  const firstRunSentRef = useRef(false)
  const {
    editorOpen,
    setEditorOpen,
    agentFlex,
    previewFlex,
    collapsedAgentFlex,
    editorAnimateWidth,
    mainPanelsRef,
    handleEditorDividerPointerDown,
    handleAgentDividerPointerDown,
  } = usePanelLayout()

  const {
    resume,
    resumeLoading,
    exporting,
    activeSection,
    setActiveSection,
    layoutConfig,
    setPreviewTotalPages,
    isSmartFitting,
    smartFitTriggerRef,
    moduleOrder,
    editorSections,
    fetchResume,
    performAutoSave,
    handleLayoutConfigChange,
    handleSmartFitHeaderClick,
    handleExportPDF,
    recognizeJobDescriptionImage,
    updateResumeContent,
    applyAgentResumeContent,
  } = useResumeEditor({
    resumeId,
    isAuthenticated,
  })

  const {
    messages,
    selectedResumeContext,
    isSending,
    isClearingMessages,
    apiError,
    setApiError,
    messagesEndRef,
    messagesContainerRef,
    isStreaming,
    streamEvents,
    confirmTool,
    userInputRequest,
    restorePendingConfirmation,
    stopStreaming,
    setSelectedResumeContext,
    dispatchMessage,
    handleMessagesScroll,
    handleClearMessages,
    appendToInputMessage,
    sendMessageWithContext,
  } = useResumeChatPanel({
    resumeId,
    visibleModules: Array.from(layoutConfig.visibleModules),
    performAutoSave,
    // 用于处理on简历update。
    onResumeUpdate: (content) => applyAgentResumeContent(content as Resume['content']),
    enabled: mounted && isAuthenticated,
  })

  useEffect(() => {
    setMounted(true)
  }, [])

  // 用于记录待确认工具调用的用户反馈草稿。
  const updateToolFeedbackDraft = useCallback((callId: string, value: string) => {
    setToolFeedbackDrafts((drafts) => ({ ...drafts, [callId]: value }))
  }, [])

  // 用于把反馈作为拒绝原因交回 Agent，触发重新生成修改。
  const retryToolWithFeedback = useCallback((callId: string) => {
    const feedback = toolFeedbackDrafts[callId]?.trim() || t('rewriteFeedbackFallback')
    void confirmTool(callId, false, 'resume_edit_feedback_retry_button', feedback)
    setToolFeedbackDrafts((drafts) => {
      const next = { ...drafts }
      delete next[callId]
      return next
    })
  }, [confirmTool, t, toolFeedbackDrafts])

  // 用于把询问卡片的选择转换成下一轮用户消息。
  const submitUserInputRequest = useCallback((answer: string) => {
    if (!userInputRequest) return
    const message = `Q: ${userInputRequest.question}\nA: ${answer}`
    void dispatchMessage(message)
  }, [dispatchMessage, userInputRequest])

  useEffect(() => {
    if (!mounted || isLoading || !isAuthenticated || hasValidResumeId) return
    router.push('/dashboard')
  }, [hasValidResumeId, isAuthenticated, isLoading, mounted, router])

  useEffect(() => {
    setApiError(null)
    setEditorOpen(true)
  }, [setApiError, setEditorOpen])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [mounted, isLoading, isAuthenticated, router])

  useEffect(() => {
    if (mounted && isAuthenticated) {
      void fetchResume()
    }
  }, [fetchResume, mounted, isAuthenticated])

  useEffect(() => {
    if (!mounted || !isAuthenticated || !hasValidResumeId || isStreaming) return
    void restorePendingConfirmation()
  }, [hasValidResumeId, isAuthenticated, isStreaming, mounted, restorePendingConfirmation])

  useEffect(() => {
    if (!isFirstRun || !resume || firstRunTriggeredRef.current) return
    firstRunTriggeredRef.current = true
    const jd = resume.content.job_application
    if (jd?.jd_text?.trim()) {
      setFirstRunPhase('analyzing')
    } else {
      setFirstRunPhase('jd_input')
      setFirstRunTargetCompany(jd?.target_company || '')
      setFirstRunTargetTitle(jd?.target_title || '')
    }
  }, [isFirstRun, resume])

  useEffect(() => {
    if (firstRunPhase !== 'analyzing' || firstRunSentRef.current || isSending || isStreaming) return
    firstRunSentRef.current = true
    void sendMessageWithContext('', '请分析我的简历与目标岗位的匹配情况。列出3个最主要的岗位差距，然后针对最重要的一个差距，给出一条具体的修改建议并生成可供我确认的修改。')
  }, [firstRunPhase, isSending, isStreaming, sendMessageWithContext])

  useEffect(() => {
    if (firstRunPhase !== 'analyzing') return
    const hasConfirmed = streamEvents.some(e => e.type === 'tool_confirmed')
    if (hasConfirmed) setFirstRunPhase('done')
  }, [streamEvents, firstRunPhase])

  /**
   * 关闭选区动作浮层，并同步清掉所有选区视觉状态。
   */
  const clearResumeSelectionAction = useCallback(() => {
    setQuickEditPrompt('')
    clearResumeSelectionVisualsAfterEvents()
    setResumeSelectionAction(null)
  }, [])

  /**
   * 在用户按下非选区浮层区域时取消选区。
   * 预览区内点击说明用户在开始新的拖选，只清 toolbar 状态，不动原生 selection，
   * 否则 clearResumeSelectionVisualsAfterEvents 的定时器会在拖选途中把新选区清掉。
   */
  const handleMainPointerDown = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    const target = event.target
    if (!(target instanceof Element)) return
    if (target.closest('[data-resume-selection-action="true"]')) return
    if (!resumeSelectionAction && !window.getSelection()?.toString()) return
    const isSelectionPanel = Boolean(
      previewPanelRef.current?.contains(target) ||
      messagesContainerRef.current?.contains(target)
    )
    if (isSelectionPanel) {
      setQuickEditPrompt('')
      setResumeSelectionAction(null)
      return
    }
    clearResumeSelectionAction()
  }, [clearResumeSelectionAction, messagesContainerRef, resumeSelectionAction])

  /**
   * 复制自绘高亮对应的缓存文本，避免 React 重渲染后原生 Selection 被截断。
   */
  const handleMainCopy = useCallback((event: ReactClipboardEvent<HTMLElement>) => {
    if (resumeSelectionAction?.mode !== 'toolbar') return
    if (!resumeSelectionAction.text.trim()) return
    const target = event.target
    if (target instanceof Element && target.closest('[data-resume-selection-action="true"]')) return
    event.clipboardData.setData('text/plain', resumeSelectionAction.text)
    event.preventDefault()
  }, [resumeSelectionAction])

  const latestPendingCallId = streamEvents.reduce<string | null>(
    (latest, event) => (event.type === 'tool_pending' ? event.callId : latest),
    null
  )
  const lastStreamEvent = streamEvents[streamEvents.length - 1]
  const isToolInteractionEvent =
    lastStreamEvent?.type === 'tool_call' || lastStreamEvent?.type === 'tool_pending'
  const shouldShowStreamingThinking =
    isStreaming && streamEvents.length > 0 && lastStreamEvent?.type !== 'text' && !isToolInteractionEvent

  useEffect(() => {
    const toolEvents = streamEvents.filter((event) =>
      event.type === 'tool_call' ||
      event.type === 'tool_result' ||
      event.type === 'tool_failed' ||
      event.type === 'tool_pending' ||
      event.type === 'tool_confirmed' ||
      event.type === 'tool_rejected'
    )
    if (toolEvents.length === 0) return
    if (process.env.NEXT_PUBLIC_AI_STREAM_DEBUG !== 'true') return
    const callIds = Array.from(
      new Set(toolEvents.flatMap((event) => ('callId' in event ? [event.callId] : [])))
    )
    const simultaneousCalls = callIds.filter((callId) => {
      const types = toolEvents
        .filter((event) => 'callId' in event && event.callId === callId)
        .map((event) => event.type)
      return types.includes('tool_result') && (
        types.includes('tool_pending') ||
        types.includes('tool_confirmed') ||
        types.includes('tool_rejected')
      )
    })
    console.info('[ResumeEditPage] streamEvents render snapshot', {
      isStreaming,
      latestPendingCallId,
      events: summarizeRenderedToolEvents(streamEvents),
      simultaneousCalls,
    })
  }, [streamEvents, isStreaming, latestPendingCallId])

  /** 读取预览区或聊天内容区当前选中文本，并把浮动按钮定位到选区上方。 */
  const updateResumeSelectionAction = useCallback(() => {
    const previewPanel = previewPanelRef.current
    const agentPanel = agentPanelRef.current
    const messagesPanel = messagesContainerRef.current
    const selection = window.getSelection()
    if (!previewPanel || !agentPanel || !messagesPanel || !selection || selection.rangeCount === 0) {
      setResumeSelectionAction(null)
      return
    }

    const selectedText = selection.toString().trim()
    const range = selection.getRangeAt(0)
    const selectedElement = getSelectionElement(range)
    if (!selectedText || !selectedElement) {
      setResumeSelectionAction(null)
      return
    }

    if (previewPanel.contains(selectedElement)) {
      setResumeSelectionAction(buildSelectionAction(range, previewPanel, selectedText, 'preview'))
      return
    }
    if (messagesPanel.contains(selectedElement)) {
      setResumeSelectionAction(buildSelectionAction(range, agentPanel, selectedText, 'chat', messagesPanel))
      return
    }
    setResumeSelectionAction(null)
  }, [messagesContainerRef])

  /**
   * 把预览区选中文本放入聊天输入框，等待用户继续编辑或发送。
   */
  const pasteResumeSelectionToChat = useCallback(() => {
    if (!resumeSelectionAction) return
    appendToInputMessage(resumeSelectionAction.text)
    clearResumeSelectionAction()
  }, [appendToInputMessage, clearResumeSelectionAction, resumeSelectionAction])

  /**
   * 把选中文本作为快速编辑上下文，并预填明确的优化指令。
   */
  const quickEditResumeSelection = useCallback(() => {
    if (!resumeSelectionAction) return
    setQuickEditPrompt('')
    setResumeSelectionAction({ ...resumeSelectionAction, mode: 'quick_edit' })
    window.requestAnimationFrame(() => {
      quickEditInputRef.current?.focus()
    })
  }, [resumeSelectionAction])

  /**
   * 将选中文本和快速优化要求一起发送给右侧简历 Agent。
   */
  const submitQuickEditSelection = useCallback(async () => {
    if (!resumeSelectionAction || !quickEditPrompt.trim()) return
    const selectedText = resumeSelectionAction.text
    const userPrompt = quickEditPrompt
    clearResumeSelectionAction()
    await sendMessageWithContext(selectedText, userPrompt)
  }, [clearResumeSelectionAction, quickEditPrompt, resumeSelectionAction, sendMessageWithContext])

  const handleFirstRunJdSubmit = useCallback(async () => {
    if (!resume || !firstRunJdText.trim()) return
    updateResumeContent('job_application', {
      ...(resume.content.job_application || {}),
      target_company: firstRunTargetCompany.trim(),
      target_title: firstRunTargetTitle.trim(),
      jd_text: firstRunJdText.trim(),
    })
    setFirstRunPhase('analyzing')
  }, [firstRunJdText, firstRunTargetCompany, firstRunTargetTitle, resume, updateResumeContent])

  /** 从当前简历直接创建面试 session 并进入面试页。 */
  const handleStartInterview = useCallback(async () => {
    if (!resume || isCreatingInterview) return
    const jobApplication = resume.content.job_application || {}
    setIsCreatingInterview(true)
    try {
      const result = await resumeApi.createInterviewSession({
        resume_id: resume.id,
        target_company: jobApplication.target_company?.trim() || undefined,
        target_title: jobApplication.target_title?.trim() || undefined,
        jd_text: jobApplication.jd_text?.trim() || undefined,
        interview_type: 'general',
        difficulty: 'medium',
        language: toInterviewLanguage(locale),
        mode: 'practice',
      })
      router.push(`/resume/${resume.id}/interview?session=${result.session.id}`)
    } catch (error) {
      toast.error(formatApiErrorMessage(
        error,
        { activeSubscriptionRequired: common('errors.activeSubscriptionRequired') },
        t('startInterviewError'),
      ))
    } finally {
      setIsCreatingInterview(false)
    }
  }, [common, isCreatingInterview, locale, resume, router, t])

  // 预览区内容防抖：编辑器输入时只更新本地状态，停止输入 300ms 后才重渲染预览
  const previewContent = useDebouncedValue(resume?.content, 300)

  if (!mounted || isLoading || resumeLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#ffffff' }}>
        <div className="text-center">
          <div
            className="w-16 h-16 rounded-full border-2 border-transparent animate-spin mx-auto mb-4"
            style={{ borderTopColor: '#0052ff', borderRightColor: '#0052ff' }}
          />
          <p style={{ color: '#5b616e' }}>{t('loading')}</p>
        </div>
      </div>
    )
  }

  if (!resume) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#ffffff' }}>
        <div className="text-center">
          <p style={{ color: '#5b616e' }}>{t('missing')}</p>
          <Link href="/dashboard" className="btn-primary mt-4">
            {t('returnToCenter')}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#ffffff' }}>
      {/* Header — Coinbase 风格 */}
      <header className="bg-white print:hidden" style={{ borderBottom: '1px solid rgba(91,97,110,0.15)' }}>
        <div className="w-full px-6">
          <div className="flex justify-between items-center py-3">
            <div className="flex items-center gap-3 pr-8">
              <Link
                href="/dashboard"
                className="flex items-center p-2 transition-colors"
                style={{ borderRadius: '56px', color: '#0a0b0d' }}
                title={t('back')}
              >
                <ArrowLeftIcon className="w-5 h-5" />
              </Link>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleStartInterview}
                disabled={isCreatingInterview}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50"
                style={{
                  borderRadius: '56px',
                  backgroundColor: '#ffffff',
                  border: '1px solid rgba(91,97,110,0.25)',
                  color: '#0a0b0d',
                }}
              >
                {isCreatingInterview ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-transparent animate-spin" style={{ borderTopColor: '#0052ff' }} />
                    <span>{t('startingInterview')}</span>
                  </>
                ) : (
                  <>
                    <PlayCircleIcon className="w-4 h-4" />
                    <span>{t('startInterview')}</span>
                  </>
                )}
              </button>
              <ResumeLayoutControls
                config={layoutConfig}
                onConfigChange={handleLayoutConfigChange}
              />
              <button
                onClick={handleSmartFitHeaderClick}
                disabled={isSmartFitting}
                title={t('smartFit')}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50"
                style={{
                  borderRadius: '56px',
                  backgroundColor: '#ffffff',
                  border: '1px solid rgba(91,97,110,0.25)',
                  color: '#0a0b0d',
                  cursor: isSmartFitting ? 'wait' : 'pointer',
                }}
              >
                {isSmartFitting ? (
                  <>
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                    </svg>
                    {t('calculating')}
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    {t('smartFitShort')}
                  </>
                )}
              </button>
              <button
                onClick={handleExportPDF}
                disabled={exporting}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white transition-colors disabled:opacity-50"
                style={{
                  borderRadius: '56px',
                  backgroundColor: '#0052ff',
                  border: '1px solid #0052ff',
                }}
              >
                {exporting ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-transparent animate-spin" style={{ borderTopColor: '#fff' }} />
                    <span>{t('exporting')}</span>
                  </>
                ) : (
                  <>
                    <ArrowDownTrayIcon className="w-4 h-4" />
                    <span>{t('export')}</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content — 三栏布局 */}
      <main
        className="max-w-full mx-auto px-6 py-3"
        onPointerDown={handleMainPointerDown}
        onMouseUp={updateResumeSelectionAction}
        onKeyUp={updateResumeSelectionAction}
        onCopy={handleMainCopy}
      >
        <div
          ref={mainPanelsRef}
          className="flex gap-0 h-[calc(100vh-120px)]"
        >
          {/* Left Panel - Editor */}
          <AnimatePresence initial={false}>
          <motion.div
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: editorAnimateWidth }}
            exit={{ opacity: 0, width: 0 }}
            transition={{ duration: 0.35, ease: 'easeInOut' }}
            className="flex flex-col min-h-0 print:hidden overflow-hidden"
            style={{ flexShrink: 0, flexGrow: 0 }}
          >
            {!editorOpen ? (
              <div
                className="flex flex-col items-center justify-center h-full w-12 cursor-pointer transition-colors group"
                style={{ backgroundColor: '#eef0f3' }}
                onClick={() => setEditorOpen(true)}
                title={t('expandEditor')}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#dde0e8')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
              >
                <ChevronRightIcon className="w-5 h-5" style={{ color: '#5b616e' }} />
              </div>
            ) : (
            <div
              className="relative p-4 flex-1 min-h-0 overflow-hidden flex flex-col"
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid rgba(91,97,110,0.2)',
                borderRadius: '16px',
              }}
            >
              <div className="flex-1 flex flex-col min-h-0">
                {/* Section Tabs */}
                <div
                  className="flex items-center gap-1 mb-5 flex-shrink-0 pb-0"
                  style={{ borderBottom: '1px solid rgba(91,97,110,0.15)' }}
                >
                  {editorSections.map(section => (
                    <button
                      key={section.key}
                      onClick={() => setActiveSection(section.key)}
                      className="px-4 py-2.5 text-sm font-semibold transition-colors relative"
                      style={{
                        color: activeSection === section.key ? '#0052ff' : '#5b616e',
                      }}
                    >
                      <span>{section.label}</span>
                      {activeSection === section.key && (
                        <div
                          className="absolute bottom-0 left-0 right-0 h-0.5"
                          style={{ backgroundColor: '#0052ff', borderRadius: '2px 2px 0 0' }}
                        />
                      )}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setEditorOpen(false)}
                  className="absolute right-4 top-4 p-1.5 transition-colors"
                  style={{ borderRadius: '8px', color: '#9ca3af' }}
                  title={t('collapseEditor')}
                  onMouseEnter={e => { e.currentTarget.style.backgroundColor = '#eef0f3'; e.currentTarget.style.color = '#5b616e' }}
                  onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = '#9ca3af' }}
                >
                  <ChevronLeftIcon className="w-5 h-5" />
                </button>

                {/* Editor Content */}
                <div className="flex-1 overflow-y-auto min-h-0 hide-scrollbar px-1">
                  {activeSection === 'job_application' && (
                    <JobApplicationEditor
                      data={resume.content.job_application || {}}
                      onChange={(data) => updateResumeContent('job_application', data)}
                      onRecognizeJdImage={recognizeJobDescriptionImage}
                    />
                  )}

                  {activeSection === 'personal' && (
                    <PersonalInfoEditor
                      data={resume.content.personal_info || {}}
                      onChange={(data) => updateResumeContent('personal_info', data)}
                    />
                  )}

                  {activeSection === 'summary' && (
                    <SummaryEditor
                      data={resume.content.summary || {}}
                      onChange={(data) => updateResumeContent('summary', data)}
                    />
                  )}

                  {activeSection === 'education' && (
                    <EducationEditor
                      data={resume.content.education || []}
                      onChange={(data) => updateResumeContent('education', data)}
                    />
                  )}

                  {activeSection === 'work' && (
                    <WorkExperienceEditor
                      data={resume.content.work_experience || []}
                      onChange={(data) => updateResumeContent('work_experience', data)}
                    />
                  )}

                  {activeSection === 'skills' && (
                    <SkillsEditor
                      data={resume.content.skills || []}
                      onChange={(data) => updateResumeContent('skills', data)}
                    />
                  )}

                  {activeSection === 'projects' && (
                    <ProjectsEditor
                      data={resume.content.projects || []}
                      onChange={(data) => updateResumeContent('projects', data)}
                    />
                  )}

                  {activeSection === 'open_source' && (
                    <ProjectsEditor
                      data={resume.content.open_source || []}
                      onChange={(data) => updateResumeContent('open_source', data)}
                      variant="openSource"
                    />
                  )}
                </div>
              </div>
            </div>
            )}
          </motion.div>
          </AnimatePresence>

          {editorOpen && (
            <div
              className="w-2 flex-shrink-0 cursor-col-resize flex items-center justify-center group select-none print:hidden"
              onPointerDown={handleEditorDividerPointerDown}
            >
              <div
                className="w-0.5 h-full transition-colors rounded-full"
                style={{ backgroundColor: 'transparent' }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#578bfa')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              />
            </div>
          )}

          {/* Middle Panel - Preview */}
          <motion.div
            ref={previewPanelRef}
            layout
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ layout: { duration: 0.35, ease: 'easeInOut' }, opacity: { duration: 0.8, delay: 0.2 }, x: { duration: 0.8, delay: 0.2 } }}
            className="preview-panel relative flex flex-col min-h-0 min-w-0 print:w-full print:h-auto print:absolute print:top-0 print:left-0 print:m-0 print:p-0"
            style={{ flex: `0 0 calc(${previewFlex}% - 16px)` }}
          >
            {resumeSelectionAction?.source === 'preview' && resumeSelectionAction.mode === 'toolbar' && (
              <div
                data-resume-selection-action="true"
                className="absolute z-30 inline-flex items-center overflow-hidden whitespace-nowrap text-sm font-normal shadow-sm print:hidden"
                style={{
                  top: resumeSelectionAction.top,
                  left: resumeSelectionAction.left,
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
                  onClick={pasteResumeSelectionToChat}
                >
                  <span>{t('pasteSelectionToChat')}</span>
                </button>
                <div className="h-5 w-px" style={{ backgroundColor: 'rgba(255,255,255,0.35)' }} />
                <button
                  type="button"
                  className="inline-flex items-center px-2.5 py-1 transition-colors"
                  onClick={quickEditResumeSelection}
                >
                  <span>快速优化</span>
                </button>
              </div>
            )}
            {resumeSelectionAction?.source === 'preview' && resumeSelectionAction.mode === 'quick_edit' && resumeSelectionAction.highlightRects.map((rect, index) => (
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
            {resumeSelectionAction?.source === 'preview' && resumeSelectionAction.mode === 'quick_edit' && (
              <div
                data-resume-selection-action="true"
                className="absolute z-30 w-[min(360px,calc(100%-16px))] rounded-lg border bg-white px-2 py-1 shadow-lg print:hidden"
                style={{
                  top: resumeSelectionAction.quickEditTop,
                  left: resumeSelectionAction.left,
                  borderColor: 'rgba(91,97,110,0.25)',
                }}
                onMouseUp={(event) => event.stopPropagation()}
                onKeyUp={(event) => event.stopPropagation()}
                onPointerDown={(event) => event.stopPropagation()}
              >
                <button
                  type="button"
                  aria-label="关闭快速优化"
                  className="absolute right-2 top-1.5 inline-flex h-6 w-6 items-center justify-center rounded-full text-gray-400 transition-colors hover:text-gray-600"
                  onPointerDown={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    clearResumeSelectionAction()
                  }}
                  onClick={clearResumeSelectionAction}
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
                <textarea
                  ref={quickEditInputRef}
                  value={quickEditPrompt}
                  onChange={(event) => setQuickEditPrompt(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      void submitQuickEditSelection()
                    }
                  }}
                  placeholder="输入优化要求"
                  rows={1}
                  className="min-h-[30px] w-full resize-none bg-transparent py-1 pl-1 pr-8 text-sm leading-relaxed text-[#0a0b0d] placeholder:text-gray-400 focus:outline-none"
                />
                <div className="-mt-1 flex items-center justify-end">
                  <button
                    type="button"
                    aria-label="发送快速优化"
                    disabled={!quickEditPrompt.trim() || isSending || isStreaming}
                    className="inline-flex h-6 w-6 items-center justify-center rounded-full transition-colors disabled:cursor-not-allowed"
                    style={{
                      backgroundColor: quickEditPrompt.trim() ? '#0052ff' : '#eef0f3',
                      color: quickEditPrompt.trim() ? '#ffffff' : '#9ca3af',
                    }}
                    onClick={() => void submitQuickEditSelection()}
                  >
                    <ArrowUpIcon className="h-3 w-3" />
                  </button>
                </div>
              </div>
            )}
            <div className="flex-1 overflow-y-auto min-h-0 hide-scrollbar print:overflow-visible print:h-auto">
              <ResumePreview
                key={JSON.stringify(moduleOrder.map(m => `${m.type}-${m.order}-${m.visible}`))}
                content={previewContent ?? resume.content}
                moduleOrder={moduleOrder}
                spacingScale={layoutConfig.spacingScale}
                templateStyle={layoutConfig.templateStyle}
                onSpacingScaleChange={(scale) =>
                  handleLayoutConfigChange({ ...layoutConfig, spacingScale: scale, density: 'custom' })
                }
                onTotalPagesChange={setPreviewTotalPages}
                smartFitTriggerRef={smartFitTriggerRef}
              />
            </div>
          </motion.div>

          {/* 拖拽分隔条 */}
          <div
            className="w-2 flex-shrink-0 cursor-col-resize flex items-center justify-center group select-none print:hidden"
            onPointerDown={handleAgentDividerPointerDown}
          >
            <div className="w-0.5 h-full transition-colors rounded-full" style={{ backgroundColor: 'transparent' }} />
          </div>

          {/* Right Panel - AI Chat */}
          <motion.div
            layout
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ layout: { duration: 0.35, ease: 'easeInOut' }, opacity: { duration: 0.8, delay: 0.4 }, y: { duration: 0.8, delay: 0.4 } }}
            className="agent-panel flex flex-col min-h-0 min-w-0 print:hidden"
            style={{ flex: `0 0 calc(${editorOpen ? agentFlex : collapsedAgentFlex}% - 8px)` }}
          >
            <div
              ref={agentPanelRef}
              className="relative p-4 flex-1 overflow-hidden flex flex-col"
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid rgba(91,97,110,0.2)',
                borderRadius: '16px',
              }}
            >
              {resumeSelectionAction?.source === 'chat' && resumeSelectionAction.mode === 'toolbar' && (
                <div
                  data-resume-selection-action="true"
                  className="absolute z-30 inline-flex items-center overflow-hidden whitespace-nowrap text-sm font-normal shadow-sm"
                  style={{
                    top: resumeSelectionAction.top,
                    left: resumeSelectionAction.left,
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
                    onClick={pasteResumeSelectionToChat}
                  >
                    <span>{t('pasteSelectionToChat')}</span>
                  </button>
                </div>
              )}
              <div className="mb-3 flex-shrink-0 pr-12 text-lg font-semibold text-[#0a0b0d]">
                简历智能体
              </div>
              <button
                onClick={handleClearMessages}
                disabled={messages.length === 0 || isStreaming || isSending || isClearingMessages}
                aria-label={isClearingMessages ? t('clearingMessages') : t('clearMessages')}
                className="absolute right-2 top-3 z-20 inline-flex h-10 w-10 items-center justify-center transition-colors disabled:opacity-50"
                style={{
                  borderRadius: '12px',
                  border: '1px solid rgba(91,97,110,0.2)',
                  backgroundColor: '#ffffff',
                  color: '#5b616e',
                  boxShadow: '0 8px 20px rgba(15,23,42,0.08)',
                }}
              >
                <TrashIcon className="w-3.5 h-3.5" />
              </button>
              <AnimatePresence mode="wait">
              {/* ── 简历 AGENT 模式 ── */}
              <motion.div
                key="resume"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="flex-1 flex flex-col min-h-0"
              >
              {/* API错误提示 */}
              {apiError && (
                <div
                  className="mb-4 p-3 text-sm flex-shrink-0"
                  style={{
                    borderRadius: '12px',
                    backgroundColor: '#fef2f2',
                    border: '1px solid rgba(220,38,38,0.2)',
                    color: '#dc2626',
                  }}
                >
                  <div className="flex items-center gap-2">
                    <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    <span>{apiError}</span>
                  </div>
                </div>
              )}
              <div className="flex-1 flex flex-col min-h-0">
                {/* Messages Display Area */}
                <div
                  ref={messagesContainerRef}
                  data-testid="resume-chat-messages"
                  onScroll={handleMessagesScroll}
                  className="relative flex-1 overflow-y-auto mb-4 min-h-0 max-h-full hide-scrollbar"
                >
                  {resumeSelectionAction?.source === 'chat' && resumeSelectionAction.mode === 'toolbar' && resumeSelectionAction.highlightRects.map((rect, index) => (
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
                  <div className="space-y-3">
                  {messages.map((message: ChatMessage) => (
                    <div
                      key={message.id}
                      className={`flex w-full ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={message.type === 'user' ? 'max-w-[85%]' : 'max-w-[93%] px-4 py-3'}
                        style={message.type === 'user' ? undefined : { color: '#0a0b0d' }}
                      >
                        {message.type === 'ai' ? (
                          <>
                            {/* 有 streamEvents 时按事件顺序交错渲染；否则直接渲染完整文本 */}
                            {message.streamEvents && message.streamEvents.length > 0 ? (
                              <AgentStreamEventList
                                events={message.streamEvents}
                                mode="history"
                              />
                            ) : (
                              <MarkdownMessage content={message.content} />
                            )}
                          </>
                        ) : (
                          <UserMessageContent content={message.content} />
                        )}
                      </div>
                    </div>
                  ))}
                  {isStreaming && streamEvents.length > 0 && (
                    <div className="flex w-full justify-start">
                      <div className="max-w-[93%] px-4 py-3" style={{ color: '#0a0b0d' }}>
                        <AgentStreamEventList
                          events={streamEvents}
                          mode="live"
                          latestPendingCallId={latestPendingCallId}
                          toolFeedbackDrafts={toolFeedbackDrafts}
                          onFeedbackChange={updateToolFeedbackDraft}
                          onConfirmTool={(callId, confirmed, source) => {
                            void confirmTool(callId, confirmed, source)
                          }}
                          onRetryToolWithFeedback={(callId) => retryToolWithFeedback(callId)}
                        />
                        {shouldShowStreamingThinking && (
                          <div className="mt-2 px-4 py-3 text-sm" style={{ color: '#5b616e' }}>
                            <span className="inline-block thinking-shimmer">{t('thinking')}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {(isSending || isStreaming) && streamEvents.length === 0 && (
                    <div className="flex w-full justify-start">
                      <div className="max-w-[93%] px-4 py-3 text-sm" style={{ color: '#5b616e' }}>
                        <span className="inline-block thinking-shimmer">{t('thinking')}</span>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                  </div>
                </div>

                {/* Input Area */}
                {userInputRequest && (
                  <UserInputRequestCard
                    request={userInputRequest}
                    disabled={isSending || isStreaming}
                    onSubmit={submitUserInputRequest}
                  />
                )}
                <ChatInputBox
                  selectedResumeContext={selectedResumeContext}
                  onClearContext={() => setSelectedResumeContext('')}
                  onSend={(message) => { void dispatchMessage(message) }}
                  onStop={stopStreaming}
                  isSending={isSending}
                  isStreaming={isStreaming}
                  placeholder={t('messagePlaceholder')}
                />
              </div>
              </motion.div>
              </AnimatePresence>
            </div>
          </motion.div>
        </div>
      </main>

      {firstRunPhase === 'jd_input' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.2 }}
            className="w-full max-w-md mx-4 bg-white rounded-2xl p-6 shadow-2xl"
          >
            <h2 className="text-xl font-semibold mb-1" style={{ color: '#0a0b0d' }}>补充目标岗位</h2>
            <p className="text-sm mb-5" style={{ color: '#5b616e' }}>
              简历上传成功！填写目标岗位和 JD，让 Agent 分析最大的岗位差距。
            </p>
            <div className="space-y-3 mb-5">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={firstRunTargetCompany}
                  onChange={e => setFirstRunTargetCompany(e.target.value)}
                  placeholder="目标公司（选填）"
                  className="flex-1 px-3 py-2 text-sm rounded-lg focus:outline-none"
                  style={{ border: '1px solid rgba(91,97,110,0.25)' }}
                />
                <input
                  type="text"
                  value={firstRunTargetTitle}
                  onChange={e => setFirstRunTargetTitle(e.target.value)}
                  placeholder="目标岗位（选填）"
                  className="flex-1 px-3 py-2 text-sm rounded-lg focus:outline-none"
                  style={{ border: '1px solid rgba(91,97,110,0.25)' }}
                />
              </div>
              <textarea
                value={firstRunJdText}
                onChange={e => setFirstRunJdText(e.target.value)}
                placeholder="粘贴职位描述 (JD)..."
                rows={6}
                className="w-full px-3 py-2 text-sm rounded-lg focus:outline-none resize-none"
                style={{ border: '1px solid rgba(91,97,110,0.25)' }}
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => void handleFirstRunJdSubmit()}
                disabled={!firstRunJdText.trim()}
                className="flex-1 py-2.5 text-sm font-semibold text-white transition-colors disabled:opacity-40"
                style={{ borderRadius: '56px', backgroundColor: '#0052ff' }}
                onMouseEnter={e => { if (firstRunJdText.trim()) e.currentTarget.style.backgroundColor = '#578bfa' }}
                onMouseLeave={e => { e.currentTarget.style.backgroundColor = '#0052ff' }}
              >
                开始分析
              </button>
              <button
                onClick={() => setFirstRunPhase(null)}
                className="px-5 py-2.5 text-sm font-semibold transition-colors"
                style={{ borderRadius: '56px', border: '1px solid rgba(91,97,110,0.25)', color: '#5b616e' }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                先跳过
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {firstRunPhase === 'done' && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="fixed bottom-6 right-6 z-40 max-w-xs bg-white rounded-2xl p-4 shadow-xl"
          style={{ border: '1px solid rgba(91,97,110,0.15)' }}
        >
          <div className="flex items-start gap-3">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ backgroundColor: '#e8f5e9' }}
            >
              <svg className="w-4 h-4" style={{ color: '#16a34a' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold" style={{ color: '#0a0b0d' }}>第一轮岗位优化完成</p>
              <p className="text-xs mt-0.5" style={{ color: '#5b616e' }}>可继续和 Agent 对话，或导出简历。</p>
            </div>
            <button
              onClick={() => setFirstRunPhase(null)}
              className="flex-shrink-0 p-0.5 transition-colors"
              style={{ color: '#9ca3af' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#5b616e')}
              onMouseLeave={e => (e.currentTarget.style.color = '#9ca3af')}
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      )}

    </div>
  )
}
