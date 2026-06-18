// 用于把 streaming client reduction 转成 React hook 可消费的 UI patch。

import {
  shouldYieldBeforePendingEvent,
  type StreamEvent,
  type StreamProtocolState,
  type UserInputRequest,
} from './streamingEventProtocol'

export interface StreamingViewReduction {
  data: Record<string, unknown>
  state: StreamProtocolState
  previousEvents: StreamEvent[]
  protocolEvent: StreamEvent | null
  ignoredAskUserToolEvent: boolean
  nextCursor?: string | null
  pendingToolCallId?: string
  decisionToolCallId?: string
  completedToolCallId?: string
  replayAttempted: boolean
}

export interface StreamingDoneMessage {
  content: string
  streamEvents?: StreamEvent[]
  resumeContent?: Record<string, unknown>
}

export interface StreamingViewStatePatch {
  nextCursor?: string
  error?: string
  sessionId?: string
  qrImages?: string[]
  resumeContent?: Record<string, unknown>
  doneMessage?: StreamingDoneMessage
  currentStreamingMessage?: string
  userInputRequest?: UserInputRequest | null
  streamEvents?: StreamEvent[]
  previousEventsBeforeYield?: StreamEvent[]
  yieldBeforeStreamEvents: boolean
  ignoredAskUserToolEvent: boolean
  pendingToolCallId?: string
  decisionToolCallId?: string
  completedToolCallId?: string
}

// 用于从 streaming reduction 中提取前端状态补丁。
export function buildStreamingViewStatePatch(
  reduction: StreamingViewReduction,
): StreamingViewStatePatch {
  const data = reduction.data
  const protocolEvent = reduction.protocolEvent
  const resumeContent = objectValue(data.resume_content)
  const streamEvents = protocolEvent ? [...reduction.state.events] : undefined
  const yieldBeforeStreamEvents = shouldYieldBeforePendingEvent(
    reduction.previousEvents,
    protocolEvent,
  )
  return {
    nextCursor: typeof reduction.nextCursor === 'string' ? reduction.nextCursor : undefined,
    error: data.error ? String(data.error) : undefined,
    sessionId: data.session_id ? String(data.session_id) : undefined,
    qrImages: stringList(data.qr_images),
    resumeContent,
    doneMessage: data.done ? {
      content: reduction.state.content,
      streamEvents: reduction.state.events.length > 0 ? [...reduction.state.events] : undefined,
      resumeContent,
    } : undefined,
    currentStreamingMessage: protocolEvent?.type === 'text'
      ? reduction.state.content
      : undefined,
    userInputRequest: protocolEvent?.type === 'user_input_request'
      ? reduction.state.userInputRequest
      : undefined,
    streamEvents,
    previousEventsBeforeYield: yieldBeforeStreamEvents ? [...reduction.previousEvents] : undefined,
    yieldBeforeStreamEvents,
    ignoredAskUserToolEvent: reduction.ignoredAskUserToolEvent,
    pendingToolCallId: reduction.pendingToolCallId,
    decisionToolCallId: reduction.decisionToolCallId,
    completedToolCallId: reduction.completedToolCallId,
  }
}

// 用于把未知值收窄成对象。
function objectValue(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object'
    ? value as Record<string, unknown>
    : undefined
}

// 用于把未知值收窄成字符串列表。
function stringList(value: unknown): string[] | undefined {
  if (!Array.isArray(value) || value.length === 0) return undefined
  const items = value.filter((item): item is string => typeof item === 'string')
  return items.length > 0 ? items : undefined
}
