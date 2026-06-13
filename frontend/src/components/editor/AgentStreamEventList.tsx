// 用于提供组件化的 Resume Agent stream event 渲染。
'use client'

import { CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { useTranslations } from 'next-intl'
import { useRef } from 'react'

import { AgentToolActivity } from '@/components/editor/AgentToolActivity'
import { DiffGroupCards } from '@/components/editor/DiffReviewCard'
import SectionVisibilityConfirmCard from '@/components/editor/SectionVisibilityConfirmCard'
import MarkdownMessage from '@/components/ui/MarkdownMessage'
import StreamingMessage from '@/components/ui/StreamingMessage'
import type { StreamEvent } from '@/hooks/useStreamingChat'

type ToolDecisionEvent = Extract<StreamEvent, { type: 'tool_pending' | 'tool_confirmed' | 'tool_rejected' }>

interface AgentStreamEventListProps {
  events: StreamEvent[]
  mode: 'history' | 'live'
  latestPendingCallId?: string | null
  onConfirmTool?: (callId: string, confirmed: boolean, source: string) => void
  onRetryToolWithFeedback?: (callId: string, feedback: string) => void
}

// 用于渲染历史或实时 Resume Agent stream event。
export function AgentStreamEventList({
  events,
  mode,
  latestPendingCallId,
  onConfirmTool,
  onRetryToolWithFeedback,
}: AgentStreamEventListProps) {
  const t = useTranslations('resume.editor')
  return events.map((event, index) => {
    if (event.type === 'tool_pending') {
      return renderPendingEvent({
        event,
        events,
        index,
        mode,
        latestPendingCallId,
        onConfirmTool,
        onRetryToolWithFeedback,
        labels: {
          acceptChange: t('acceptChange'),
          cancel: t('cancel'),
          confirm: t('confirm'),
          expired: t('expired'),
          reject: t('reject'),
          retryWithFeedback: t('retryWithFeedback'),
          toolFeedbackPlaceholder: t('toolFeedbackPlaceholder'),
        },
      })
    }
    if (event.type === 'tool_confirmed' || event.type === 'tool_rejected') {
      return renderDecisionEvent(event, events, index)
    }
    if (event.type === 'tool_call' || event.type === 'tool_result' || event.type === 'tool_failed') {
      return <AgentToolActivity key={index} event={event} live={mode === 'live'} />
    }
    if (event.type === 'user_input_request') return null
    return renderTextEvent(event, index, mode, events.length)
  })
}

// 用于压缩编辑页工具事件渲染状态。
export function summarizeRenderedToolEvents(events: StreamEvent[]): string[] {
  return events
    .filter((event) =>
      event.type === 'tool_call' ||
      event.type === 'tool_result' ||
      event.type === 'tool_failed' ||
      event.type === 'tool_pending' ||
      event.type === 'tool_confirmed' ||
      event.type === 'tool_rejected'
    )
    .map((event, index) => `${index}:${event.type}:${'callId' in event ? event.callId : 'none'}:${'toolName' in event ? event.toolName : ''}`)
}

// 用于识别记忆工具，避免把记忆写入当成简历 diff 确认卡展示。
function isMemoryToolEvent(event: StreamEvent): boolean {
  if (!('toolName' in event)) return false
  const toolName = event.toolName || ''
  return toolName === 'update_memory' || toolName === '更新记忆'
}

// 用于识别显隐板块工具：纯开关操作没有可重写内容。
function isVisibilityToolEvent(event: StreamEvent): boolean {
  if (!('toolName' in event)) return false
  const toolName = event.toolName || ''
  return ['show_section', 'hide_section', '显示板块', '隐藏板块'].includes(toolName)
}

// 用于判断同一工具调用是否已有上方状态行可展示。
function hasToolActivityForCall(events: StreamEvent[], callId: string): boolean {
  return events.some((event) =>
    (event.type === 'tool_call' || event.type === 'tool_result' || event.type === 'tool_failed') &&
    event.callId === callId
  )
}

// 用于把记忆确认事件降级成工具状态行。
function renderMemoryToolDecisionActivity(
  event: ToolDecisionEvent,
  events: StreamEvent[],
  key: number,
) {
  if (!isMemoryToolEvent(event)) return undefined
  if (hasToolActivityForCall(events, event.callId)) return null
  return (
    <AgentToolActivity
      key={key}
      event={{
        type: event.type === 'tool_rejected' ? 'tool_failed' : 'tool_result',
        callId: event.callId,
        toolName: event.toolName,
      }}
    />
  )
}

// 用于渲染工具待确认事件。
function renderPendingEvent({
  event,
  events,
  index,
  mode,
  latestPendingCallId,
  onConfirmTool,
  onRetryToolWithFeedback,
  labels,
}: {
  event: Extract<StreamEvent, { type: 'tool_pending' }>
  events: StreamEvent[]
  index: number
  mode: 'history' | 'live'
  latestPendingCallId?: string | null
  onConfirmTool?: (callId: string, confirmed: boolean, source: string) => void
  onRetryToolWithFeedback?: (callId: string, feedback: string) => void
  labels: Record<string, string>
}) {
  if (mode === 'history') return null
  const memoryActivity = renderMemoryToolDecisionActivity(event, events, index)
  if (memoryActivity !== undefined) return memoryActivity
  const isActivePending = event.callId === latestPendingCallId
  if (isVisibilityToolEvent(event)) {
    return (
      <SectionVisibilityConfirmCard
        key={index}
        isActivePending={isActivePending}
        confirmLabel={labels.confirm}
        cancelLabel={labels.cancel}
        onConfirm={() => onConfirmTool?.(event.callId, true, 'resume_edit_accept_button')}
        onReject={() => onConfirmTool?.(event.callId, false, 'resume_edit_reject_button')}
      />
    )
  }
  return (
    <ToolPendingDiffCard
      key={index}
      event={event}
      isActivePending={isActivePending}
      labels={labels}
      onConfirmTool={onConfirmTool}
      onRetryToolWithFeedback={onRetryToolWithFeedback}
    />
  )
}

// 用于渲染工具确认或拒绝后的 diff。
function renderDecisionEvent(event: ToolDecisionEvent, events: StreamEvent[], index: number) {
  const memoryActivity = renderMemoryToolDecisionActivity(event, events, index)
  if (memoryActivity !== undefined) return memoryActivity
  if (isVisibilityToolEvent(event)) return null
  return (
    <ToolDecisionDiffCard
      key={index}
      event={event}
      isConfirmed={event.type === 'tool_confirmed'}
    />
  )
}

// 用于按历史或实时模式渲染文本事件。
function renderTextEvent(
  event: Extract<StreamEvent, { type: 'text' }>,
  index: number,
  mode: 'history' | 'live',
  eventCount: number,
) {
  if (mode === 'history') {
    return (
      <div key={index}>
        <MarkdownMessage content={event.content} />
      </div>
    )
  }
  return (
    <div key={index} className={index > 0 ? 'mt-2' : ''}>
      <StreamingMessage content={event.content} isComplete={index !== eventCount - 1} />
    </div>
  )
}

// 用于渲染待确认 diff 及确认操作。
function ToolPendingDiffCard({
  event,
  isActivePending,
  labels,
  onConfirmTool,
  onRetryToolWithFeedback,
}: {
  event: Extract<StreamEvent, { type: 'tool_pending' }>
  isActivePending: boolean
  labels: Record<string, string>
  onConfirmTool?: (callId: string, confirmed: boolean, source: string) => void
  onRetryToolWithFeedback?: (callId: string, feedback: string) => void
}) {
  const feedbackRef = useRef<HTMLTextAreaElement>(null)

  // 用于读取非受控反馈框内容，避免每个按键触发编辑页重渲染。
  const submitRetryFeedback = () => {
    onRetryToolWithFeedback?.(event.callId, feedbackRef.current?.value || '')
    if (feedbackRef.current) feedbackRef.current.value = ''
  }

  return (
    <div className="mb-2 rounded-2xl border border-gray-200 bg-white overflow-hidden text-xs shadow-sm">
      <div className="px-4 py-3 bg-white flex items-center gap-2 border-b border-gray-200">
        <span className="font-medium text-gray-900">{event.toolName}</span>
        <span className="ml-auto" />
        {isActivePending ? (
          <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
        ) : (
          <span className="text-[11px] text-gray-400">{labels.expired}</span>
        )}
      </div>
      <DiffGroupCards
        diffSummary={event.diffSummary}
        diffItems={event.diffItems}
        isConfirmed={true}
      />
      <div className="px-4 py-3 bg-white border-t border-gray-100">
        <textarea
          ref={feedbackRef}
          disabled={!isActivePending}
          rows={1}
          placeholder={labels.toolFeedbackPlaceholder}
          className="hide-scrollbar h-9 w-full resize-none rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs leading-5 text-gray-900 outline-none transition-colors placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>
      <div className="px-4 py-3 bg-white border-t border-gray-200 flex gap-2">
        <ToolActionButton
          disabled={!isActivePending}
          label={labels.acceptChange}
          variant="primary"
          onClick={() => onConfirmTool?.(event.callId, true, 'resume_edit_accept_button')}
        />
        <ToolActionButton
          disabled={!isActivePending}
          label={labels.reject}
          variant="secondary"
          onClick={() => onConfirmTool?.(event.callId, false, 'resume_edit_reject_button')}
        />
        <ToolActionButton
          disabled={!isActivePending}
          label={labels.retryWithFeedback}
          variant="retry"
          onClick={submitRetryFeedback}
        />
      </div>
    </div>
  )
}

// 用于渲染确认或拒绝后的 diff 卡片。
function ToolDecisionDiffCard({
  event,
  isConfirmed,
}: {
  event: ToolDecisionEvent
  isConfirmed: boolean
}) {
  return (
    <div className="mb-2 rounded-2xl border border-gray-200 bg-white overflow-hidden text-xs shadow-sm">
      <div className="px-4 py-3 flex items-center gap-2 bg-white border-b border-gray-200">
        <span className="font-medium text-gray-900">{event.toolName}</span>
        <span className="ml-auto" />
        {isConfirmed ? (
          <CheckIcon className="h-3.5 w-3.5 flex-shrink-0 text-green-500" />
        ) : (
          <XMarkIcon className="h-3.5 w-3.5 flex-shrink-0 text-red-500" />
        )}
      </div>
      <DiffGroupCards
        diffSummary={event.diffSummary}
        diffItems={event.diffItems}
        isConfirmed={isConfirmed}
      />
    </div>
  )
}

// 用于渲染工具确认区域按钮。
function ToolActionButton({
  disabled,
  label,
  variant,
  onClick,
}: {
  disabled: boolean
  label: string
  variant: 'primary' | 'secondary' | 'retry'
  onClick: () => void
}) {
  const styleByVariant = {
    primary: {
      borderRadius: '56px',
      backgroundColor: disabled ? '#94a3b8' : '#0052ff',
      color: '#ffffff',
    },
    secondary: {
      borderRadius: '56px',
      border: '1px solid rgba(91,97,110,0.2)',
      backgroundColor: '#ffffff',
      color: '#0a0b0d',
    },
    retry: {
      borderRadius: '56px',
      border: '1px solid rgba(0,82,255,0.22)',
      backgroundColor: '#eef4ff',
      color: '#0052ff',
    },
  }
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="flex-1 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50"
      style={styleByVariant[variant]}
    >
      {label}
    </button>
  )
}
