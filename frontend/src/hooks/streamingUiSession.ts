// 用于收口流式 UI session 的锁、工具计时和确认状态。

import {
  normalizeDiffItems,
  summarizeToolEvents,
  type StreamEvent,
} from './streamingEventProtocol'

type PendingToolTiming = {
  receivedAt: number
  appendedAt: number
  streamStartedAt: number
  clientRequestId: string
}

type DebugLog = (message: string, payload?: Record<string, unknown>) => void

type WarningLog = (message: string, payload?: Record<string, unknown>) => void

type PaintScheduler = (callback: () => void) => void

export interface StreamingUiSessionOptions {
  nowMs?: () => number
  requestPaint?: PaintScheduler
  debugLog?: DebugLog
  warn?: WarningLog
}

export interface RestorePendingClient {
  restorePendingConfirmation(resumeId: number): Promise<{
    sessionId: string
    action: {
      call_id?: string
      tool_name?: string
      tool_id?: string
      diff_summary?: string
      diff_items?: unknown
    }
  } | null>
}

export interface ConfirmToolClient {
  confirmTool(params: {
    sessionId: string
    callId: string
    confirmed: boolean
    source: string
    feedback?: string
  }): Promise<{ ok?: boolean; resumable?: boolean; duplicate?: boolean }>
  resumePausedSession(sessionId: string): Promise<Record<string, unknown> | null>
}

export interface PendingToolRecord {
  callId: string
  toolName: string
  diffItemCount: number
  streamStartedAt: number
  clientRequestId: string
  previousEvents: StreamEvent[]
  eventsAfter: StreamEvent[]
}

export interface RestoredPendingConfirmation {
  sessionId: string
  event: StreamEvent
}

export type ToolConfirmationResult =
  | { status: 'no_session' }
  | { status: 'duplicate_in_flight' }
  | { status: 'duplicate_response' }
  | { status: 'ok' }
  | { status: 'resumable'; resumeContent: Record<string, unknown> | null }

// 用于创建一次可复用的 streaming UI session 状态容器。
export function createStreamingUiSession(options: StreamingUiSessionOptions = {}) {
  return new StreamingUiSession(options)
}

// 用于保存 React 外的 streaming UI session 可变状态。
export class StreamingUiSession {
  private locked = false
  private currentSessionId: string | null = null
  private pendingToolTimings: Record<string, PendingToolTiming> = {}
  private readonly confirmingToolCalls = new Set<string>()
  private readonly nowMs: () => number
  private readonly requestPaint: PaintScheduler
  private readonly debugLog: DebugLog
  private readonly warn: WarningLog

  constructor(options: StreamingUiSessionOptions = {}) {
    this.nowMs = options.nowMs || defaultNowMs
    this.requestPaint = options.requestPaint || defaultRequestPaint
    this.debugLog = options.debugLog || (() => undefined)
    this.warn = options.warn || defaultWarn
  }

  // 用于尝试进入 streaming 状态并防止重复发送。
  beginStreaming(): boolean {
    if (this.locked) return false
    this.locked = true
    return true
  }

  // 用于读取当前是否已有活跃 streaming 请求。
  isStreamingLocked(): boolean {
    return this.locked
  }

  // 用于记录后端返回的活跃 session id。
  setSessionId(sessionId: string) {
    this.currentSessionId = sessionId
  }

  // 用于读取当前活跃 session id。
  sessionId(): string | null {
    return this.currentSessionId
  }

  // 用于清理 streaming 完成或停止后的 session 状态。
  reset() {
    this.clearPendingToolState()
    this.locked = false
    this.currentSessionId = null
  }

  // 用于清理待确认工具的本地交互状态。
  clearPendingToolState() {
    this.pendingToolTimings = {}
    this.confirmingToolCalls.clear()
  }

  // 用于记录 tool_pending 到达、追加和渲染的诊断计时。
  recordPendingTool(record: PendingToolRecord) {
    const receivedAt = this.nowMs()
    this.debugLog('[useStreamingChat] tool_pending received', {
      callId: record.callId,
      toolName: record.toolName,
      diffItemCount: record.diffItemCount,
      elapsedSinceStreamStartMs: roundMs(receivedAt - record.streamStartedAt),
      eventsBefore: summarizeToolEvents(record.previousEvents),
    })
    const appendedAt = this.nowMs()
    this.pendingToolTimings[record.callId] = {
      receivedAt,
      appendedAt,
      streamStartedAt: record.streamStartedAt,
      clientRequestId: record.clientRequestId,
    }
    this.debugLog('[useStreamingChat] tool_pending appended', {
      callId: record.callId,
      elapsedSinceReceivedMs: roundMs(appendedAt - receivedAt),
      eventsAfter: summarizeToolEvents(record.eventsAfter),
    })
    this.requestPaint(() => this.logPendingToolRendered(record.callId))
  }

  // 用于记录工具确认或拒绝事件结束并清理 pending 计时。
  recordToolDecision(callId: string, eventType: string, previousEvents: StreamEvent[], eventsAfter: StreamEvent[]) {
    delete this.pendingToolTimings[callId]
    this.debugLog('[useStreamingChat] tool decision handling end', {
      callId,
      newType: eventType,
      eventsBefore: summarizeToolEvents(previousEvents),
      eventsAfter: summarizeToolEvents(eventsAfter),
    })
  }

  // 用于记录工具完成事件结束。
  recordToolCompletion(callId: string, eventType: string, previousEvents: StreamEvent[], eventsAfter: StreamEvent[]) {
    this.debugLog('[useStreamingChat] tool completion handling end', {
      callId,
      newType: eventType,
      eventsBefore: summarizeToolEvents(previousEvents),
      eventsAfter: summarizeToolEvents(eventsAfter),
    })
  }

  // 用于从后端恢复持久化的待确认工具 diff。
  async restorePendingConfirmation(
    client: RestorePendingClient,
    resumeId: number,
  ): Promise<RestoredPendingConfirmation | null> {
    if (this.locked) return null
    const pending = await client.restorePendingConfirmation(resumeId)
    const action = pending?.action
    if (!pending?.sessionId || !action?.call_id) return null
    this.currentSessionId = pending.sessionId
    this.locked = true
    return {
      sessionId: pending.sessionId,
      event: {
        type: 'tool_pending',
        callId: action.call_id,
        toolName: action.tool_name || '',
        toolId: action.tool_id,
        diffSummary: action.diff_summary || '',
        diffItems: normalizeDiffItems(action.diff_items),
      },
    }
  }

  // 用于提交工具确认并处理重复点击与可恢复 session。
  async confirmTool(
    client: ConfirmToolClient,
    params: {
      callId: string
      confirmed: boolean
      source: string
      feedback?: string
    },
  ): Promise<ToolConfirmationResult> {
    const clickedAt = this.nowMs()
    const timing = this.pendingToolTimings[params.callId]
    const sid = this.currentSessionId
    const cleanFeedback = params.feedback?.trim()
    if (!sid) return this.handleNoSession(params, timing, clickedAt, cleanFeedback)
    if (this.confirmingToolCalls.has(params.callId)) {
      return this.handleDuplicateConfirmation(params, sid)
    }
    this.confirmingToolCalls.add(params.callId)
    this.logConfirmationClick(params, timing, clickedAt, sid, cleanFeedback)
    const fetchStartedAt = this.nowMs()
    this.logConfirmationFetchStart(params, fetchStartedAt, clickedAt, sid, cleanFeedback)
    const body = await client.confirmTool({
      sessionId: sid,
      callId: params.callId,
      confirmed: params.confirmed,
      source: params.source,
      feedback: cleanFeedback,
    })
    if (body.duplicate) return this.handleDuplicateResponse(params, fetchStartedAt)
    this.logConfirmationResponse(params, body, fetchStartedAt, clickedAt, cleanFeedback)
    if (body?.resumable === true) {
      const resumeContent = await client.resumePausedSession(sid)
      return { status: 'resumable', resumeContent }
    }
    return { status: 'ok' }
  }

  // 用于输出 pending 工具首帧渲染后的计时。
  private logPendingToolRendered(callId: string) {
    const timing = this.pendingToolTimings[callId]
    if (!timing) return
    this.debugLog('[useStreamingChat] tool_pending rendered', {
      callId,
      clientRequestId: timing.clientRequestId,
      elapsedSinceStreamStartMs: roundMs(this.nowMs() - timing.streamStartedAt),
      elapsedSinceReceivedMs: roundMs(this.nowMs() - timing.receivedAt),
      elapsedSinceAppendedMs: roundMs(this.nowMs() - timing.appendedAt),
    })
  }

  // 用于处理无活跃 session 的确认请求。
  private handleNoSession(
    params: { callId: string; confirmed: boolean; source: string },
    timing: PendingToolTiming | undefined,
    clickedAt: number,
    cleanFeedback: string | undefined,
  ): ToolConfirmationResult {
    this.warn('[confirmTool] 没有活跃 session', params)
    this.debugLog('[confirmTool] no active session', {
      callId: params.callId,
      confirmed: params.confirmed,
      source: params.source,
      hasFeedback: Boolean(cleanFeedback),
      elapsedSincePendingReceivedMs: timing ? roundMs(clickedAt - timing.receivedAt) : null,
    })
    return { status: 'no_session' }
  }

  // 用于处理确认中的重复点击。
  private handleDuplicateConfirmation(
    params: { callId: string; confirmed: boolean; source: string },
    sessionId: string,
  ): ToolConfirmationResult {
    this.warn('[confirmTool] 正在确认中，忽略重复点击', params)
    this.debugLog('[confirmTool] duplicate click ignored', {
      callId: params.callId,
      confirmed: params.confirmed,
      source: params.source,
      sessionIdShort: sessionId.slice(0, 8),
    })
    return { status: 'duplicate_in_flight' }
  }

  // 用于记录确认点击本地阶段。
  private logConfirmationClick(
    params: { callId: string; confirmed: boolean; source: string },
    timing: PendingToolTiming | undefined,
    clickedAt: number,
    sessionId: string,
    cleanFeedback: string | undefined,
  ) {
    this.debugLog('[confirmTool] click', {
      callId: params.callId,
      confirmed: params.confirmed,
      source: params.source,
      hasFeedback: Boolean(cleanFeedback),
      sessionIdShort: sessionId.slice(0, 8),
      elapsedSincePendingReceivedMs: timing ? roundMs(clickedAt - timing.receivedAt) : null,
      elapsedSincePendingRenderedEstimateMs: timing ? roundMs(clickedAt - timing.appendedAt) : null,
    })
  }

  // 用于记录确认请求发出阶段。
  private logConfirmationFetchStart(
    params: { callId: string; confirmed: boolean; source: string },
    fetchStartedAt: number,
    clickedAt: number,
    sessionId: string,
    cleanFeedback: string | undefined,
  ) {
    this.debugLog('[confirmTool] fetch start', {
      callId: params.callId,
      confirmed: params.confirmed,
      source: params.source,
      hasFeedback: Boolean(cleanFeedback),
      sessionIdShort: sessionId.slice(0, 8),
      elapsedSinceClickMs: roundMs(fetchStartedAt - clickedAt),
    })
  }

  // 用于处理后端重复确认响应。
  private handleDuplicateResponse(
    params: { callId: string; confirmed: boolean; source: string },
    fetchStartedAt: number,
  ): ToolConfirmationResult {
    this.warn('[confirmTool] 工具确认状态已变化，忽略重复确认', params)
    this.debugLog('[confirmTool] conflict response', {
      callId: params.callId,
      confirmed: params.confirmed,
      source: params.source,
      elapsedSinceFetchStartMs: roundMs(this.nowMs() - fetchStartedAt),
    })
    return { status: 'duplicate_response' }
  }

  // 用于记录确认响应阶段。
  private logConfirmationResponse(
    params: { callId: string; confirmed: boolean; source: string },
    body: { ok?: boolean; resumable?: boolean; duplicate?: boolean },
    fetchStartedAt: number,
    clickedAt: number,
    cleanFeedback: string | undefined,
  ) {
    this.debugLog('[confirmTool] response', {
      callId: params.callId,
      confirmed: params.confirmed,
      source: params.source,
      hasFeedback: Boolean(cleanFeedback),
      ok: Boolean(body?.ok),
      resumable: Boolean(body?.resumable),
      duplicate: Boolean(body?.duplicate),
      elapsedSinceFetchStartMs: roundMs(this.nowMs() - fetchStartedAt),
      elapsedSinceClickMs: roundMs(this.nowMs() - clickedAt),
    })
  }
}

// 用于读取浏览器单调时钟。
function defaultNowMs(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}

// 用于等待下一帧渲染后执行诊断回调。
function defaultRequestPaint(callback: () => void) {
  if (typeof window === 'undefined') return
  window.requestAnimationFrame(callback)
}

// 用于输出默认 warning 日志。
function defaultWarn(message: string, payload?: Record<string, unknown>) {
  console.warn(message, payload)
}

// 用于把耗时压缩为稳定的两位小数。
function roundMs(value: number): number {
  return Math.round(value * 100) / 100
}
