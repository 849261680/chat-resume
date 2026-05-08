'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import type { Resume } from '@/lib/api'
import Link from 'next/link'
import {
  ArrowLeftIcon,
  ArrowUpIcon,
  ArrowDownTrayIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  StopCircleIcon,
  TrashIcon
} from '@heroicons/react/24/outline'
import JobApplicationEditor from '@/components/editor/JobApplicationEditor'
import { DiffGroupCards } from '@/components/editor/DiffReviewCard'
import PersonalInfoEditor from '@/components/editor/PersonalInfoEditor'
import EducationEditor from '@/components/editor/EducationEditor'
import WorkExperienceEditor from '@/components/editor/WorkExperienceEditor'
import SkillsEditor from '@/components/editor/SkillsEditor'
import ProjectsEditor from '@/components/editor/ProjectsEditor'
import ResumePreview from '@/components/preview/ResumePreview'
import ResumeLayoutControls from '@/components/preview/ResumeLayoutControls'
import MarkdownMessage from '@/components/ui/MarkdownMessage'
import StreamingMessage from '@/components/ui/StreamingMessage'
import type { ChatMessage, StreamEvent } from '@/hooks/useStreamingChat'
import { usePanelLayout } from '@/hooks/usePanelLayout'
import { AutoSaveStatus } from '@/hooks/useResumeAutoSave'
import { useResumeChatPanel } from '@/hooks/useResumeChatPanel'
import { useResumeEditor } from '@/hooks/useResumeEditor'

const AUTO_SAVE_STATUS_MESSAGE: Record<
  AutoSaveStatus,
  { text: string; className: string }
> = {
  idle: { text: '', className: 'text-gray-400' },
  pending: { text: '有未保存的更改…', className: 'text-amber-500' },
  saving: { text: '自动保存中…', className: 'text-primary-600' },
  success: { text: '已自动保存', className: 'text-green-600' },
  error: { text: '自动保存失败，请检查网络或手动保存', className: 'text-red-600' }
}

const JD_MATCH_ANALYSIS_PROMPT = [
  '请基于我当前简历和已填写的 JD，做一份 JD 匹配度分析。',
  '请按以下结构输出：1. 总体匹配判断；2. 已覆盖的 JD 要求；3. 关键缺口与风险；4. 建议补强的关键词和经历表达。',
  '如果你判断有值得直接优化的内容，请先说明原因，再按需发起工具修改。',
].join('\n')

/** 编辑页组件用于组装简历编辑、预览和 Agent 面板。 */
export default function ResumeEditPage() {
  const params = useParams()
  const router = useRouter()
  const { isAuthenticated, isLoading } = useAuth()
  const [mounted, setMounted] = useState(false)

  const resumeId = params?.id as string
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
    autoSaveStatus,
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
    inputMessage,
    setInputMessage,
    isSending,
    isClearingMessages,
    apiError,
    setApiError,
    messagesEndRef,
    messagesContainerRef,
    isStreaming,
    streamEvents,
    confirmTool,
    handleMessagesScroll,
    handleClearMessages,
    handleKeyPress,
    endConversation,
    sendMessage,
    sendPresetMessage,
  } = useResumeChatPanel({
    resumeId,
    visibleModules: Array.from(layoutConfig.visibleModules),
    performAutoSave,
    onResumeUpdate: (content) => applyAgentResumeContent(content as Resume['content']),
    enabled: mounted && isAuthenticated,
  })

  useEffect(() => {
    setMounted(true)
  }, [])

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

  const hasJobDescription = Boolean(resume?.content.job_application?.jd_text?.trim())

  if (!mounted || isLoading || resumeLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#ffffff' }}>
        <div className="text-center">
          <div
            className="w-16 h-16 rounded-full border-2 border-transparent animate-spin mx-auto mb-4"
            style={{ borderTopColor: '#0052ff', borderRightColor: '#0052ff' }}
          />
          <p style={{ color: '#5b616e' }}>正在加载简历...</p>
        </div>
      </div>
    )
  }

  if (!resume) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#ffffff' }}>
        <div className="text-center">
          <p style={{ color: '#5b616e' }}>简历不存在</p>
          <Link href="/dashboard" className="btn-primary mt-4">
            返回简历中心
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
            <div className="flex items-center gap-3">
              <Link
                href="/dashboard"
                className="flex items-center p-2 transition-colors"
                style={{ borderRadius: '56px', color: '#0a0b0d' }}
                title="返回仪表板"
              >
                <ArrowLeftIcon className="w-5 h-5" />
              </Link>
            </div>

            <div className="flex items-center gap-3">
              <ResumeLayoutControls
                config={layoutConfig}
                onConfigChange={handleLayoutConfigChange}
              />
              <button
                onClick={handleSmartFitHeaderClick}
                disabled={isSmartFitting}
                title="自动调整间距使简历恰好一页"
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
                    计算中...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    智能一页
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
                    <span>生成中...</span>
                  </>
                ) : (
                  <>
                    <ArrowDownTrayIcon className="w-4 h-4" />
                    <span>导出 PDF</span>
                  </>
                )}
              </button>
              {AUTO_SAVE_STATUS_MESSAGE[autoSaveStatus].text && (
                <div
                  className="text-xs px-3 py-1"
                  style={{
                    borderRadius: '100000px',
                    backgroundColor: autoSaveStatus === 'error' ? '#fef2f2' : autoSaveStatus === 'success' ? '#ecfdf5' : '#eef0f3',
                    color: autoSaveStatus === 'error' ? '#dc2626' : autoSaveStatus === 'success' ? '#059669' : '#5b616e',
                  }}
                >
                  {AUTO_SAVE_STATUS_MESSAGE[autoSaveStatus].text}
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content — 三栏布局 */}
      <main className="max-w-full mx-auto px-6 py-3">
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
                title="展开编辑区域"
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#dde0e8')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
              >
                <ChevronRightIcon className="w-5 h-5" style={{ color: '#5b616e' }} />
              </div>
            ) : (
            <div
              className="relative p-4 flex-1 overflow-hidden flex flex-col"
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
                  title="折叠编辑器"
                  onMouseEnter={e => { e.currentTarget.style.backgroundColor = '#eef0f3'; e.currentTarget.style.color = '#5b616e' }}
                  onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = '#9ca3af' }}
                >
                  <ChevronLeftIcon className="w-5 h-5" />
                </button>

                {/* Editor Content */}
                <div className="flex-1 overflow-y-auto min-h-0 hide-scrollbar">
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
            layout
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ layout: { duration: 0.35, ease: 'easeInOut' }, opacity: { duration: 0.8, delay: 0.2 }, x: { duration: 0.8, delay: 0.2 } }}
            className="preview-panel flex flex-col min-h-0 min-w-0 print:w-full print:h-auto print:absolute print:top-0 print:left-0 print:m-0 print:p-0"
            style={{ flex: `0 0 calc(${previewFlex}% - 16px)` }}
          >
            <div className="flex-1 overflow-y-auto min-h-0 hide-scrollbar print:overflow-visible print:h-auto">
              <ResumePreview
                key={JSON.stringify(moduleOrder.map(m => `${m.type}-${m.order}-${m.visible}`))}
                content={resume.content}
                moduleOrder={moduleOrder}
                spacingScale={layoutConfig.spacingScale}
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
              className="p-4 flex-1 overflow-hidden flex flex-col"
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid rgba(91,97,110,0.2)',
                borderRadius: '16px',
              }}
            >
              <div className="mb-3 flex items-center justify-between gap-3 flex-shrink-0">
                {(resume.content.job_application?.target_company || resume.content.job_application?.target_title) ? (
                  <button
                    onClick={() => { setEditorOpen(true); setActiveSection('job_application') }}
                    title="点击编辑目标岗位"
                    className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1 transition-colors truncate max-w-[60%]"
                    style={{
                      borderRadius: '100000px',
                      backgroundColor: '#eef0f3',
                      color: '#0052ff',
                      border: '1px solid rgba(0,82,255,0.15)',
                    }}
                  >
                    <svg className="w-3 h-3 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 14a6 6 0 110-12 6 6 0 010 12zm1-9a1 1 0 10-2 0v3.586l-1.707 1.707a1 1 0 101.414 1.414l2-2A1 1 0 0011 11V7z" clipRule="evenodd"/></svg>
                    <span className="truncate">
                      {[resume.content.job_application?.target_company, resume.content.job_application?.target_title].filter(Boolean).join(' · ')}
                    </span>
                  </button>
                ) : <div />}
                <button
                  onClick={handleClearMessages}
                  disabled={messages.length === 0 || isStreaming || isSending || isClearingMessages}
                  aria-label={isClearingMessages ? '清空中' : '清空消息'}
                  className="inline-flex items-center justify-center p-2 transition-colors disabled:opacity-50"
                  style={{
                    borderRadius: '8px',
                    border: '1px solid rgba(91,97,110,0.2)',
                    backgroundColor: '#ffffff',
                    color: '#5b616e',
                  }}
                >
                  <TrashIcon className="w-3.5 h-3.5" />
                </button>
              </div>
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
                  onScroll={handleMessagesScroll}
                  className="flex-1 overflow-y-auto mb-4 space-y-3 min-h-0 max-h-full hide-scrollbar"
                >
                  {messages.map((message: ChatMessage) => (
                    <div
                      key={message.id}
                      className={`flex w-full ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className="max-w-[85%] px-4 py-3"
                        style={{
                          borderRadius: message.type === 'user' ? '20px 20px 6px 20px' : '20px 20px 20px 6px',
                          backgroundColor: message.type === 'user' ? '#0052ff' : '#eef0f3',
                          color: message.type === 'user' ? '#ffffff' : '#0a0b0d',
                          border: message.type === 'user' ? 'none' : '1px solid rgba(91,97,110,0.15)',
                        }}
                      >
                        {message.type === 'ai' ? (
                          <>
                            {/* 有 streamEvents 时按事件顺序交错渲染；否则直接渲染完整文本 */}
                            {message.streamEvents && message.streamEvents.length > 0 ? (
                              message.streamEvents!.map((event: StreamEvent, idx: number) => {
                                if (event.type === 'tool_confirmed' || event.type === 'tool_rejected') {
                                  const isConfirmed = event.type === 'tool_confirmed'
                                  return (
                                    <div key={idx} className="mb-2 rounded-2xl border border-gray-200 bg-white overflow-hidden text-xs shadow-sm">
                                      <div className="px-4 py-3 flex items-center gap-2 bg-white border-b border-gray-200">
                                        <span className="font-medium text-gray-900">{event.toolName}</span>
                                        <span className="ml-auto" />
                                        {isConfirmed ? (
                                          <svg className="w-3.5 h-3.5 flex-shrink-0 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                        ) : (
                                          <svg className="w-3.5 h-3.5 flex-shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                                        )}
                                      </div>
                                      <DiffGroupCards diffSummary={event.diffSummary} isConfirmed={isConfirmed} />
                                    </div>
                                  )
                                }
                                if (event.type === 'text') return (
                                  <div key={idx}>
                                    <MarkdownMessage content={event.content} />
                                  </div>
                                )
                                return null
                              })
                            ) : (
                              <MarkdownMessage content={message.content} />
                            )}
                          </>
                        ) : (
                          <span className="text-[14px]">{message.content}</span>
                        )}
                      </div>
                    </div>
                  ))}
                  {isStreaming && streamEvents.length > 0 && (
                    <div className="flex w-full justify-start">
                      <div
                        className="max-w-[85%] px-4 py-3"
                        style={{
                          borderRadius: '20px 20px 20px 6px',
                          backgroundColor: '#eef0f3',
                          border: '1px solid rgba(91,97,110,0.15)',
                          color: '#0a0b0d',
                        }}
                      >
                        {streamEvents.map((event: StreamEvent, idx: number) => {
                          if (event.type === 'tool_pending') {
                            return (
                              <div key={idx} className="mb-2 rounded-2xl border border-gray-200 bg-white overflow-hidden text-xs shadow-sm">
                                {/* 标题栏 */}
                                <div className="px-4 py-3 bg-white flex items-center gap-2 border-b border-gray-200">
                                  <span className="font-medium text-gray-900">{event.toolName}</span>
                                  <span className="ml-auto" />
                                  <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
                                </div>
                                {/* diff 内容区 */}
                                <DiffGroupCards diffSummary={event.diffSummary} isConfirmed={true} />
                                {/* 操作按钮 */}
                                <div className="px-4 py-3 bg-white border-t border-gray-200 flex gap-2">
                                  <button
                                    onClick={() => confirmTool(event.callId, true)}
                                    className="flex-1 py-1.5 text-xs font-semibold text-white transition-colors"
                                    style={{ borderRadius: '56px', backgroundColor: '#0052ff' }}
                                  >
                                    确认修改
                                  </button>
                                  <button
                                    onClick={() => confirmTool(event.callId, false)}
                                    className="flex-1 py-1.5 text-xs font-semibold transition-colors"
                                    style={{
                                      borderRadius: '56px',
                                      border: '1px solid rgba(91,97,110,0.2)',
                                      backgroundColor: '#ffffff',
                                      color: '#0a0b0d',
                                    }}
                                  >
                                    拒绝
                                  </button>
                                </div>
                              </div>
                            )
                          }
                          if (event.type === 'tool_confirmed' || event.type === 'tool_rejected') {
                            const isConfirmed = event.type === 'tool_confirmed'
                            return (
                              <div key={idx} className="mb-2 rounded-2xl border border-gray-200 bg-white overflow-hidden text-xs shadow-sm">
                                {/* 标题栏 */}
                                <div className="px-4 py-3 flex items-center gap-2 bg-white border-b border-gray-200">
                                  <span className="font-medium text-gray-900">{event.toolName}</span>
                                  <span className="ml-auto" />
                                  {isConfirmed ? (
                                    <svg className="w-3.5 h-3.5 flex-shrink-0 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                  ) : (
                                    <svg className="w-3.5 h-3.5 flex-shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                                  )}
                                </div>
                                {/* diff 内容 */}
                                <DiffGroupCards diffSummary={event.diffSummary} isConfirmed={isConfirmed} />
                              </div>
                            )
                          }
                          if (event.type === 'tool') {
                            return (
                              <div key={idx} className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                                <div className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-pulse flex-shrink-0" />
                                <span>{event.name}</span>
                              </div>
                            )
                          }
                          // text event
                          const isLastEvent = idx === streamEvents.length - 1
                          return (
                            <div key={idx} className={idx > 0 ? 'mt-2' : ''}>
                              <StreamingMessage content={event.content} isComplete={!isLastEvent} />
                            </div>
                          )
                        })}
                        {!streamEvents.some((event) => event.type === 'text' && event.content.trim()) && (
                          <div className="mt-2 px-4 py-3 text-sm" style={{ color: '#5b616e' }}>
                            <span className="inline-block animate-pulse">思考中</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {(isSending || isStreaming) && streamEvents.length === 0 && (
                    <div className="flex w-full justify-start">
                      <div
                        className="max-w-[85%] px-4 py-3 text-sm"
                        style={{
                          borderRadius: '20px 20px 20px 6px',
                          backgroundColor: '#eef0f3',
                          border: '1px solid rgba(91,97,110,0.15)',
                          color: '#5b616e',
                        }}
                      >
                        <span className="inline-block animate-pulse">思考中</span>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="pt-3 flex-shrink-0">
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => void sendPresetMessage(JD_MATCH_ANALYSIS_PROMPT)}
                      disabled={!hasJobDescription || isSending || isStreaming}
                      title={hasJobDescription ? '让 Agent 直接分析当前简历与 JD 的匹配度' : '请先在岗位信息里填写 JD'}
                      className="inline-flex items-center gap-2 px-3 py-2 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                      style={{
                        borderRadius: '999px',
                        border: '1px solid rgba(0,82,255,0.18)',
                        backgroundColor: hasJobDescription ? '#eef4ff' : '#f8fafc',
                        color: hasJobDescription ? '#0052ff' : '#94a3b8',
                      }}
                    >
                      <svg className="w-3.5 h-3.5 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M10 2a.75.75 0 01.75.75v5.69l4.72-2.726a.75.75 0 11.75 1.3L11.5 9.75l4.72 2.725a.75.75 0 11-.75 1.3l-4.72-2.725v5.7a.75.75 0 01-1.5 0v-5.7l-4.72 2.725a.75.75 0 11-.75-1.3L8.5 9.75 3.78 7.014a.75.75 0 01.75-1.3L9.25 8.44V2.75A.75.75 0 0110 2z" clipRule="evenodd" />
                      </svg>
                      <span>JD 匹配度分析</span>
                    </button>
                    {!hasJobDescription && (
                      <button
                        type="button"
                        onClick={() => { setEditorOpen(true); setActiveSection('job_application') }}
                        className="text-xs font-medium transition-colors"
                        style={{ color: '#5b616e' }}
                      >
                        先补充 JD
                      </button>
                    )}
                  </div>
                  <div className="relative">
                    <textarea
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="输入消息..."
                      className="w-full p-3 pr-12 text-sm resize-none focus:outline-none"
                      style={{
                        border: '1px solid rgba(91,97,110,0.25)',
                        borderRadius: '12px',
                        color: '#0a0b0d',
                      }}
                      rows={2}
                      disabled={isSending || isStreaming}
                    />
                    <button
                      onClick={(isSending || isStreaming) ? endConversation : sendMessage}
                      disabled={!inputMessage.trim() && !isSending && !isStreaming}
                      aria-label={(isSending || isStreaming) ? '结束对话' : '发送消息'}
                      className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full transition-colors flex items-center justify-center disabled:cursor-not-allowed"
                      style={{
                        backgroundColor: (isSending || isStreaming)
                          ? '#dc2626'
                          : (inputMessage.trim() ? '#0052ff' : '#eef0f3'),
                        color: (isSending || isStreaming) || inputMessage.trim() ? '#ffffff' : '#9ca3af',
                      }}
                    >
                      {(isSending || isStreaming) ? (
                        <StopCircleIcon className="w-4 h-4" />
                      ) : (
                        <ArrowUpIcon className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
              </motion.div>
              </AnimatePresence>
            </div>
          </motion.div>
        </div>
      </main>

    </div>
  )
}
