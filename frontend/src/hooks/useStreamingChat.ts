// 用于提供 hooks/useStreamingChat.ts 模块。
import { useCallback, useRef, useState } from 'react'
import { API_BASE_URL, apiUrl } from '@/lib/httpClient'
import { useTranslations } from 'next-intl'

export type DiffItem = {
  before?: string
  after?: string
  reason?: string
}

export type JobMatchSummary = {
  matched_keywords: string[]
  missing_keywords: string[]
  resume_changes: string[]
  fact_gaps: string[]
  top_gaps: JobMatchTopGap[]
}

export type JobMatchTopGap = {
  gap: string
  priority_reason: string
  jd_evidence: string[]
  resume_anchor: string
  suggested_edit: string
  risk: 'can_improve' | 'needs_user_confirmation' | 'insufficient_evidence' | string
}

export type StreamEvent =
  | { type: 'tool'; name: string }
  | { type: 'text'; content: string }
  | { type: 'job_match_summary'; summary: JobMatchSummary }
  | {
      type: 'tool_call'
      callId: string
      toolName: string
      toolId?: string
      toolInput?: Record<string, unknown>
      displayMessage?: string
    }
  | {
      type: 'tool_result'
      callId?: string
      toolName: string
      toolId?: string
      displayMessage?: string
    }
  | {
      type: 'tool_failed'
      callId: string
      toolName: string
      toolId?: string
      displayMessage?: string
    }
  | {
      type: 'tool_pending'
      callId: string
      toolName: string
      toolId?: string
      toolInput?: Record<string, unknown>
      diffSummary: string
      diffItems?: DiffItem[]
    }
  | {
      type: 'tool_confirmed'
      callId: string
      toolName: string
      toolId?: string
      diffSummary: string
      diffItems?: DiffItem[]
    }
  | {
      type: 'tool_rejected'
      callId: string
      toolName: string
      toolId?: string
      diffSummary: string
      diffItems?: DiffItem[]
    }

type PendingConfirmationResponse = {
  session_id?: string | null
  status?: string
  pending_action?: {
    call_id?: string
    tool_name?: string
    tool_id?: string
    diff_summary?: string
    diff_items?: DiffItem[]
  } | null
}

export interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
  streamEvents?: StreamEvent[]
}

interface StreamingChatOptions {
  onMessage?: (message: ChatMessage) => void
  onError?: (error: string) => void
  apiBaseUrl?: string
  onQrImages?: (images: string[]) => void
  onResumeUpdate?: (resumeContent: Record<string, unknown>) => void
  visibleModules?: string[]
  agentType?: 'resume'
}

type PendingToolTiming = {
  receivedAt: number
  appendedAt: number
  streamStartedAt: number
  clientRequestId: string
}

// 用于标准化字符串列表。
function normalizeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => String(item || '').trim())
    .filter(Boolean)
}

// 用于标准化岗位匹配摘要。
function normalizeJobMatchSummary(value: unknown): JobMatchSummary | null {
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  const summary = {
    matched_keywords: normalizeStringList(record.matched_keywords),
    missing_keywords: normalizeStringList(record.missing_keywords),
    resume_changes: normalizeStringList(record.resume_changes),
    fact_gaps: normalizeStringList(record.fact_gaps),
    top_gaps: normalizeJobMatchTopGaps(record.top_gaps),
  }
  return Object.values(summary).some((items) => items.length > 0) ? summary : null
}

// 用于标准化岗位 Top gaps。
function normalizeJobMatchTopGaps(value: unknown): JobMatchTopGap[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const record = item as Record<string, unknown>
    const gap = String(record.gap || '').trim()
    if (!gap) return []
    return [{
      gap,
      priority_reason: String(record.priority_reason || '').trim(),
      jd_evidence: normalizeStringList(record.jd_evidence),
      resume_anchor: String(record.resume_anchor || '').trim(),
      suggested_edit: String(record.suggested_edit || '').trim(),
      risk: String(record.risk || '').trim(),
    }]
  }).slice(0, 3)
}

// 用于标准化差异条目。
function normalizeDiffItems(value: unknown): DiffItem[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const record = item as Record<string, unknown>
    const diffItem: DiffItem = {}
    if (record.before !== undefined && record.before !== null) {
      diffItem.before = String(record.before)
    }
    if (record.after !== undefined && record.after !== null) {
      diffItem.after = String(record.after)
    }
    if (record.reason !== undefined && record.reason !== null) {
      diffItem.reason = String(record.reason)
    }
    return Object.keys(diffItem).length > 0 ? [diffItem] : []
  })
}

const TOOL_NAME_ALIASES: Record<string, string> = {
  update_highlight: 'update_bullet',
  add_highlight: 'add_bullet',
  remove_highlight: 'remove_bullet',
}

// 用于判断是否开启 AI stream 详细调试日志。
function isAiStreamDebugEnabled(): boolean {
  if (process.env.NEXT_PUBLIC_AI_STREAM_DEBUG === 'true') return true
  if (typeof window === 'undefined') return false
  return window.localStorage.getItem('ai_stream_debug') === 'true'
}

// 用于把浏览器侧 AI stream 调试日志转发到本地 frontend.log。
function forwardStreamLogToFrontendFile(message: string, payload?: Record<string, unknown>) {
  if (typeof window === 'undefined') return
  try {
    const body = JSON.stringify({
      source: 'useStreamingChat',
      message,
      payload: payload ?? null,
      createdAt: new Date().toISOString(),
    })
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/client-log', new Blob([body], { type: 'application/json' }))
      return
    }
    void fetch('/api/client-log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => undefined)
  } catch {
    // 调试日志转发失败不能影响主链路。
  }
}

// 用于输出默认关闭的 AI stream 调试日志。
function debugStreamLog(message: string, payload?: Record<string, unknown>) {
  if (!isAiStreamDebugEnabled()) return
  if (payload === undefined) {
    console.info(message)
    forwardStreamLogToFrontendFile(message)
    return
  }
  console.info(message, payload)
  forwardStreamLogToFrontendFile(message, payload)
}

// 用于生成一次 AI stream 的前端关联 ID。
function createClientRequestId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `ai_${crypto.randomUUID()}`
  }
  return `ai_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
}

// 用于生成展示给用户的短错误 ID。
function shortClientRequestId(clientRequestId: string): string {
  return clientRequestId.replace(/^ai_/, '').slice(0, 8)
}

// 用于在 UI 错误中追加可排查的短 ID。
function formatStreamError(message: string, clientRequestId: string): string {
  return `${message} (错误ID: ${shortClientRequestId(clientRequestId)})`
}

// 用于记录流式请求关键阶段耗时，默认关闭。
function logStreamPhase(
  phase: string,
  startedAt: number,
  clientRequestId: string,
  payload: Record<string, unknown> = {},
) {
  const now = typeof performance !== 'undefined' ? performance.now() : Date.now()
  debugStreamLog(`[useStreamingChat] phase.${phase}`, {
    clientRequestId,
    elapsedMs: Math.round((now - startedAt) * 100) / 100,
    ...payload,
  })
}

// 用于读取浏览器单调时钟，方便排查确认链路延迟。
function nowMs(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}

// 用于把耗时压缩为稳定的两位小数。
function elapsedMsSince(startedAt: number): number {
  return Math.round((nowMs() - startedAt) * 100) / 100
}

// 用于标准化工具名称。
function normalizeToolName(name: string): string {
  return TOOL_NAME_ALIASES[name] || name
}

// 用于压缩工具流事件，便于诊断前端状态切换。
function summarizeToolEvents(events: StreamEvent[]): string[] {
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

// 用于解析工具 id。
function resolveToolId(data: Record<string, unknown>): string {
  if (data.tool_id) return normalizeToolName(String(data.tool_id))
  if (data.tool_name) return normalizeToolName(String(data.tool_name))
  const toolCall = data.tool_call
  if (toolCall && typeof toolCall === 'object') {
    const fn = (toolCall as { function?: unknown }).function
    if (fn && typeof fn === 'object' && 'name' in fn) {
      return normalizeToolName(String((fn as { name?: unknown }).name || ''))
    }
  }
  return ''
}

// 用于解析工具输入。
function resolveToolInput(data: Record<string, unknown>): Record<string, unknown> | undefined {
  if (data.tool_input && typeof data.tool_input === 'object') return data.tool_input as Record<string, unknown>
  const toolCall = data.tool_call
  if (!toolCall || typeof toolCall !== 'object') return undefined
  const fn = (toolCall as { function?: unknown }).function
  if (!fn || typeof fn !== 'object') return undefined
  const raw = (fn as { arguments?: unknown }).arguments
  if (raw && typeof raw === 'object') return raw as Record<string, unknown>
  if (typeof raw !== 'string') return undefined
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : undefined
  } catch {
    return undefined
  }
}

// 用于解析工具名称。
function resolveToolName(data: Record<string, unknown>, fallbackName: string): string {
  if (data.tool_display_name) return normalizeToolName(String(data.tool_display_name))
  if (data.tool_name) return normalizeToolName(String(data.tool_name))
  const calls = Array.isArray(data.tool_calls) ? data.tool_calls : []
  const lastCall = calls[calls.length - 1]
  if (lastCall && typeof lastCall === 'object' && 'name' in lastCall) {
    return normalizeToolName(String((lastCall as { name?: unknown }).name || ''))
  }
  return fallbackName
}

// 用于封装流式聊天相关状态和行为。
export function useStreamingChat(resumeId: number, options: StreamingChatOptions = {}) {
  const t = useTranslations('resume.editor')
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('')
  const [streamEvents, setStreamEvents] = useState<StreamEvent[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  // 使用 ref 作为立即生效的锁，因为 useState 更新是异步的
  const isStreamingLockRef = useRef(false)
  // 用 ref 跟踪当前 sessionId，以便在异步回调中读取最新值
  const sessionIdRef = useRef<string | null>(null)
  const lastEventIdRef = useRef<string | null>(null)
  const pendingToolTimingsRef = useRef<Record<string, PendingToolTiming>>({})
  const confirmingToolCallsRef = useRef<Set<string>>(new Set())
  const sseEventSequenceRef = useRef(0)

  const {
    onMessage,
    onError,
    apiBaseUrl = API_BASE_URL,
    onQrImages,
    onResumeUpdate,
    visibleModules = [],
    agentType = 'resume'
  } = options

  // 用于清理待确认工具的本地交互状态。
  const clearPendingToolState = () => {
    pendingToolTimingsRef.current = {}
    confirmingToolCallsRef.current.clear()
  }

  // 用于处理send流式消息。
  const sendStreamingMessage = async (message: string, chatHistory: ChatMessage[] = []) => {
    // 使用 ref 做立即检查，防止并发调用
    if (isStreamingLockRef.current) {
      debugStreamLog('[useStreamingChat] 已有流式请求进行中，跳过重复调用')
      return
    }
    // 立即加锁
    isStreamingLockRef.current = true

    setIsStreaming(true)
    setCurrentStreamingMessage('')
    lastEventIdRef.current = null

    // 创建中止控制器
    abortControllerRef.current = new AbortController()
    const clientRequestId = createClientRequestId()
    const streamStartedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()

    try {
      // 转换聊天记录格式为后端需要的 OpenAI 格式
      const historyToSend = chatHistory.map((msg) => ({
        role: msg.type === 'ai' ? 'assistant' : 'user',
        content: msg.content
      }))
      let replayAttempted = false
      let buffer = ''
      let streamingContent = ''
      let eventsBuffer: StreamEvent[] = []
      let pendingSseEventId: string | null = null
      let firstSseReceivedLogged = false
      let firstContentRenderedLogged = false

      while (true) {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          'X-Client-Request-ID': clientRequestId,
        }
        if (lastEventIdRef.current) {
          headers['Last-Event-ID'] = lastEventIdRef.current
        }

        logStreamPhase('fetch_start', streamStartedAt, clientRequestId, {
          replay: replayAttempted,
          hasLastEventId: Boolean(lastEventIdRef.current),
        })
        const response = await fetch(apiUrl('/api/ai/chat/stream', apiBaseUrl), {
          method: 'POST',
          credentials: 'include',
          headers,
          body: JSON.stringify({
            message,
            resume_id: resumeId,
            chat_history: historyToSend,
            visible_modules: visibleModules,
            agent_type: agentType,
          }),
          signal: abortControllerRef.current.signal
        })
        logStreamPhase('headers_received', streamStartedAt, clientRequestId, {
          replay: replayAttempted,
          status: response.status,
          ok: response.ok,
        })

        if (!response.ok) {
          if (response.status === 401) {
            throw new Error(t('authExpired'))
          }
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        if (!response.body) {
          throw new Error('Response body is null')
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        // 用于把工具调用卡片切换为最终状态。
        const completeToolCallEvent = (
          callId: string,
          toolName: string,
          displayMessage?: string,
          finalType: 'tool_result' | 'tool_failed' = 'tool_result',
        ) => {
          debugStreamLog('[useStreamingChat] completeToolCallEvent before', {
            callId,
            toolName,
            displayMessage,
            finalType,
            events: summarizeToolEvents(eventsBuffer),
          })
          let updated = false
          eventsBuffer = eventsBuffer.map((event) => {
            if (event.type === 'tool_call' && event.callId === callId) {
              updated = true
              return {
                type: finalType,
                callId,
                toolName: event.toolName || toolName,
                toolId: event.toolId,
                displayMessage,
              }
            }
            return event
          })
          if (!updated && !eventsBuffer.some((event) => event.type === finalType && event.callId === callId)) {
            eventsBuffer = [...eventsBuffer, {
              type: finalType,
              callId,
              toolName,
              displayMessage,
            }]
          }
          debugStreamLog('[useStreamingChat] completeToolCallEvent after', {
            callId,
            updatedToolCall: updated,
            events: summarizeToolEvents(eventsBuffer),
          })
        }

      try {
        while (true) {
          const { done, value } = await reader.read()

          if (done) break

          // 解码数据
          buffer += decoder.decode(value, { stream: true })

          // 处理完整的SSE消息
          const lines = buffer.split('\n')
          buffer = lines.pop() || '' // 保留不完整的行

          for (const line of lines) {
            if (line.startsWith('id: ')) {
              pendingSseEventId = line.slice(4).trim()
              continue
            }
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                if (!firstSseReceivedLogged) {
                  firstSseReceivedLogged = true
                  logStreamPhase('first_sse_received', streamStartedAt, clientRequestId, {
                    replay: replayAttempted,
                    eventType: typeof data.event_type === 'string' ? data.event_type : '',
                    hasContent: Boolean(data.content),
                    done: Boolean(data.done),
                  })
                }
                if (pendingSseEventId) {
                  lastEventIdRef.current = pendingSseEventId
                  pendingSseEventId = null
                }
                if (typeof data.event_id === 'string') {
                  lastEventIdRef.current = data.event_id
                }
                const eventType = typeof data.event_type === 'string' ? data.event_type : ''
                const isToolEvent =
                  eventType.startsWith('tool_') ||
                  Boolean(data.tool_pending || data.tool_confirmed || data.tool_rejected)
                if (isToolEvent) {
                  sseEventSequenceRef.current += 1
                  debugStreamLog('[useStreamingChat] tool SSE received', {
                    seq: sseEventSequenceRef.current,
                    eventType,
                    eventId: lastEventIdRef.current,
                    callId: data.call_id || '',
                    toolName: data.tool_display_name || data.tool_name || data.tool_id || '',
                    toolPending: Boolean(data.tool_pending),
                    toolConfirmed: Boolean(data.tool_confirmed),
                    toolRejected: Boolean(data.tool_rejected),
                    hasResult: Object.prototype.hasOwnProperty.call(data, 'result'),
                    diffItemCount: Array.isArray(data.diff_items) ? data.diff_items.length : 0,
                    eventsBefore: summarizeToolEvents(eventsBuffer),
                  })
                }

                if (data.error) {
                  onError?.(formatStreamError(data.error, clientRequestId))
                  return
                }

                if (data.done) {
                  logStreamPhase('done_received', streamStartedAt, clientRequestId, {
                    eventType: typeof data.event_type === 'string' ? data.event_type : '',
                    hadContent: Boolean(streamingContent),
                    streamEventCount: eventsBuffer.length,
                  })
                  // done 事件携带最终 resume_content 用于刷新预览
                  if (data.resume_content) {
                    debugStreamLog('[useStreamingChat] done 事件收到 resume_content', {
                      sections: Object.keys(data.resume_content),
                    })
                    onResumeUpdate?.(data.resume_content)
                  }
                  const jobMatchSummary = normalizeJobMatchSummary(data.job_match_summary)
                  if (jobMatchSummary) {
                    eventsBuffer = [...eventsBuffer, {
                      type: 'job_match_summary',
                      summary: jobMatchSummary,
                    }]
                  }
                  // 流式传输完成，创建完整的AI消息（携带工具事件快照，用于历史渲染）
                  const aiMessage: ChatMessage = {
                    id: Date.now().toString(),
                    type: 'ai',
                    content: streamingContent,
                    timestamp: new Date(),
                    streamEvents: eventsBuffer.length > 0 ? [...eventsBuffer] : undefined,
                  }
                  // 先清掉流式展示态，再把最终消息并入历史，避免同一条消息短暂重复渲染。
                  setIsStreaming(false)
                  setCurrentStreamingMessage('')
                  setStreamEvents([])
                  setTimeout(() => {
                    onMessage?.(aiMessage)
                  }, 0)
                  return
                }

                // 首个事件携带 session_id
                if (data.session_id) {
                  sessionIdRef.current = data.session_id
                  setSessionId(data.session_id)
                }

                if (data.qr_images && Array.isArray(data.qr_images) && data.qr_images.length > 0) {
                  onQrImages?.(data.qr_images)
                }

                if (data.event_type === 'tool_call' && data.call_id) {
                  const callId = data.call_id as string
                  eventsBuffer = [...eventsBuffer, {
                    type: 'tool_call',
                    callId,
                    toolName: resolveToolName(data, t('toolCall')),
                    toolId: resolveToolId(data),
                    toolInput: resolveToolInput(data),
                    displayMessage: data.display_message ? String(data.display_message) : undefined,
                  }]
                  debugStreamLog('[useStreamingChat] tool_call appended', {
                    callId,
                    events: summarizeToolEvents(eventsBuffer),
                  })
                  setStreamEvents([...eventsBuffer])
                }

                if (data.event_type === 'tool_result') {
                  const callId = data.call_id ? String(data.call_id) : ''
                  debugStreamLog('[useStreamingChat] tool_result handling start', {
                    callId,
                    eventsBefore: summarizeToolEvents(eventsBuffer),
                  })
                  if (callId) {
                    completeToolCallEvent(
                      callId,
                      resolveToolName(data, t('toolCall')),
                      data.display_message ? String(data.display_message) : undefined,
                    )
                  } else {
                    eventsBuffer = [...eventsBuffer, {
                      type: 'tool_result',
                      toolName: resolveToolName(data, t('toolCall')),
                      toolId: resolveToolId(data),
                      displayMessage: data.display_message ? String(data.display_message) : undefined,
                    }]
                  }
                  const jobMatchSummary = normalizeJobMatchSummary(
                    data.result && typeof data.result === 'object'
                      ? (data.result as Record<string, unknown>).job_match_summary
                      : null
                  )
                  if (jobMatchSummary) {
                    eventsBuffer = [...eventsBuffer, {
                      type: 'job_match_summary',
                      summary: jobMatchSummary,
                    }]
                  }
                  debugStreamLog('[useStreamingChat] tool_result handling end', {
                    callId,
                    eventsAfter: summarizeToolEvents(eventsBuffer),
                  })
                  setStreamEvents([...eventsBuffer])
                }

                if (data.event_type === 'tool_call_failed' && data.call_id) {
                  const callId = String(data.call_id)
                  debugStreamLog('[useStreamingChat] tool_call_failed handling start', {
                    callId,
                    eventsBefore: summarizeToolEvents(eventsBuffer),
                  })
                  completeToolCallEvent(
                    callId,
                    resolveToolName(data, t('toolCall')),
                    data.display_message ? String(data.display_message) : undefined,
                    'tool_failed',
                  )
                  debugStreamLog('[useStreamingChat] tool_call_failed handling end', {
                    callId,
                    eventsAfter: summarizeToolEvents(eventsBuffer),
                  })
                  setStreamEvents([...eventsBuffer])
                }

                // tool_pending: agent 暂停，等待用户确认
                if (data.tool_pending && data.call_id) {
                  const callId = data.call_id as string
                  const receivedAt = nowMs()
                  debugStreamLog('[useStreamingChat] tool_pending received', {
                    callId,
                    toolName: data.tool_display_name || data.tool_name || '',
                    diffItemCount: Array.isArray(data.diff_items) ? data.diff_items.length : 0,
                    elapsedSinceStreamStartMs: Math.round((receivedAt - streamStartedAt) * 100) / 100,
                    eventsBefore: summarizeToolEvents(eventsBuffer),
                  })
                  eventsBuffer = [
                    ...eventsBuffer,
                    {
                      type: 'tool_pending',
                      callId,
                      toolName: data.tool_display_name || data.tool_name || '',
                      toolId: resolveToolId(data),
                      toolInput: resolveToolInput(data),
                      diffSummary: data.diff_summary || '',
                      diffItems: normalizeDiffItems(data.diff_items),
                    },
                  ]
                  const appendedAt = nowMs()
                  pendingToolTimingsRef.current[callId] = {
                    receivedAt,
                    appendedAt,
                    streamStartedAt,
                    clientRequestId,
                  }
                  debugStreamLog('[useStreamingChat] tool_pending appended', {
                    callId,
                    elapsedSinceReceivedMs: Math.round((appendedAt - receivedAt) * 100) / 100,
                    eventsAfter: summarizeToolEvents(eventsBuffer),
                  })
                  setStreamEvents([...eventsBuffer])
                  window.requestAnimationFrame(() => {
                    const timing = pendingToolTimingsRef.current[callId]
                    if (!timing) return
                    debugStreamLog('[useStreamingChat] tool_pending rendered', {
                      callId,
                      clientRequestId: timing.clientRequestId,
                      elapsedSinceStreamStartMs: elapsedMsSince(timing.streamStartedAt),
                      elapsedSinceReceivedMs: elapsedMsSince(timing.receivedAt),
                      elapsedSinceAppendedMs: elapsedMsSince(timing.appendedAt),
                    })
                  })
                }

                // tool_confirmed / tool_rejected: 更新对应的 pending 事件状态
                if ((data.tool_confirmed || data.tool_rejected) && data.call_id) {
                  const callId = data.call_id as string
                  debugStreamLog('[useStreamingChat] tool decision handling start', {
                    callId,
                    confirmed: Boolean(data.tool_confirmed),
                    rejected: Boolean(data.tool_rejected),
                    eventsBefore: summarizeToolEvents(eventsBuffer),
                  })
                  delete pendingToolTimingsRef.current[callId]
                  const newType: 'tool_confirmed' | 'tool_rejected' = data.tool_confirmed
                    ? 'tool_confirmed'
                    : 'tool_rejected'
                  eventsBuffer = eventsBuffer.flatMap(e => {
                    if (e.type === 'tool_call' && e.callId === callId) {
                      return [{
                        type: 'tool_result' as const,
                        callId,
                        toolName: e.toolName,
                        toolId: e.toolId,
                        displayMessage: data.display_message ? String(data.display_message) : undefined,
                      }]
                    }
                    if (e.type === 'tool_pending' && e.callId === callId) {
                      return [{
                        type: newType,
                        callId: e.callId,
                        toolName: e.toolName,
                        toolId: e.toolId,
                        diffSummary: e.diffSummary,
                        diffItems: e.diffItems,
                      }]
                    }
                    return [e]
                  })
                  debugStreamLog('[useStreamingChat] tool decision handling end', {
                    callId,
                    newType,
                    eventsAfter: summarizeToolEvents(eventsBuffer),
                  })
                  setStreamEvents([...eventsBuffer])
                }

                // 处理简历更新
                if (data.resume_content) {
                  debugStreamLog('[useStreamingChat] 收到 resume_content，触发预览更新', {
                    sections: Object.keys(data.resume_content),
                  })
                  onResumeUpdate?.(data.resume_content)
                }

                if (data.content) {
                  streamingContent += data.content
                  setCurrentStreamingMessage(streamingContent)
                  const last = eventsBuffer[eventsBuffer.length - 1]
                  if (last?.type === 'text') {
                    eventsBuffer = [...eventsBuffer.slice(0, -1), { type: 'text', content: last.content + data.content }]
                  } else {
                    eventsBuffer = [...eventsBuffer, { type: 'text', content: data.content }]
                  }
                  setStreamEvents([...eventsBuffer])
                  if (!firstContentRenderedLogged) {
                    firstContentRenderedLogged = true
                    window.requestAnimationFrame(() => {
                      logStreamPhase('first_content_rendered', streamStartedAt, clientRequestId, {
                        contentChars: String(data.content).length,
                        streamEventCount: eventsBuffer.length,
                      })
                    })
                  }
                }
              } catch {
                console.warn('Failed to parse SSE data:', line)
              }
            }
          }
        }
      } finally {
        reader.releaseLock()
      }

      if (!lastEventIdRef.current || replayAttempted) {
        break
      }
      replayAttempted = true
      buffer = ''
      }

    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        debugStreamLog('Streaming aborted', { clientRequestId })
      } else {
        console.error('Streaming error:', { error, clientRequestId })
        const errorMessage = error instanceof Error ? error.message : 'Unknown streaming error'
        onError?.(formatStreamError(errorMessage, clientRequestId))
      }
    } finally {
      // 清理所有 tool_pending 超时计时器
      clearPendingToolState()
      // 释放锁
      isStreamingLockRef.current = false
      setIsStreaming(false)
      setCurrentStreamingMessage('')
      setStreamEvents([])
      setSessionId(null)
      sessionIdRef.current = null
      abortControllerRef.current = null
    }
  }

  // 用于处理stop流式。
  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    clearPendingToolState()
    isStreamingLockRef.current = false
    setIsStreaming(false)
    setCurrentStreamingMessage('')
    setStreamEvents([])
    setSessionId(null)
    sessionIdRef.current = null
  }

  // 用于从后端恢复持久化的待确认工具 diff。
  const restorePendingConfirmation = useCallback(async () => {
    if (isStreamingLockRef.current) return
    const apiBaseUrl = options.apiBaseUrl || API_BASE_URL
    const response = await fetch(
      apiUrl(`/api/ai/chat/pending-confirmation?resume_id=${resumeId}`, apiBaseUrl),
      { credentials: 'include' },
    )
    if (!response.ok) return
    const body = await response.json().catch(() => null) as PendingConfirmationResponse | null
    const action = body?.pending_action
    if (!body?.session_id || !action?.call_id) return
    sessionIdRef.current = body.session_id
    setSessionId(body.session_id)
    isStreamingLockRef.current = true
    setIsStreaming(true)
    setStreamEvents([
      {
        type: 'tool_pending',
        callId: action.call_id,
        toolName: action.tool_name || '',
        toolId: action.tool_id,
        diffSummary: action.diff_summary || '',
        diffItems: normalizeDiffItems(action.diff_items),
      },
    ])
  }, [options.apiBaseUrl, resumeId])

  // 用于处理confirm工具。
  const confirmTool = async (
    callId: string,
    confirmed: boolean,
    source = 'unknown',
    feedback?: string,
  ) => {
    const clickedAt = nowMs()
    const timing = pendingToolTimingsRef.current[callId]
    const sid = sessionIdRef.current
    const cleanFeedback = feedback?.trim()
    if (!sid) {
      console.warn('[confirmTool] 没有活跃 session', { callId, confirmed, source })
      debugStreamLog('[confirmTool] no active session', {
        callId,
        confirmed,
        source,
        hasFeedback: Boolean(cleanFeedback),
        elapsedSincePendingReceivedMs: timing
          ? Math.round((clickedAt - timing.receivedAt) * 100) / 100
          : null,
      })
      return
    }
    if (confirmingToolCallsRef.current.has(callId)) {
      console.warn('[confirmTool] 正在确认中，忽略重复点击', { callId, confirmed, source })
      debugStreamLog('[confirmTool] duplicate click ignored', {
        callId,
        confirmed,
        source,
        sessionIdShort: sid.slice(0, 8),
      })
      return
    }
    confirmingToolCallsRef.current.add(callId)
    debugStreamLog('[confirmTool] click', {
      callId,
      confirmed,
      source,
      hasFeedback: Boolean(cleanFeedback),
      sessionIdShort: sid.slice(0, 8),
      elapsedSincePendingReceivedMs: timing
        ? Math.round((clickedAt - timing.receivedAt) * 100) / 100
        : null,
      elapsedSincePendingRenderedEstimateMs: timing
        ? Math.round((clickedAt - timing.appendedAt) * 100) / 100
        : null,
    })
    const apiBaseUrl = options.apiBaseUrl || API_BASE_URL
    const fetchStartedAt = nowMs()
    debugStreamLog('[confirmTool] fetch start', {
      callId,
      confirmed,
      source,
      hasFeedback: Boolean(cleanFeedback),
      sessionIdShort: sid.slice(0, 8),
      elapsedSinceClickMs: Math.round((fetchStartedAt - clickedAt) * 100) / 100,
    })
    const response = await fetch(apiUrl('/api/ai/chat/confirm-tool', apiBaseUrl), {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sid,
        call_id: callId,
        confirmed,
        source,
        ...(cleanFeedback ? { feedback: cleanFeedback } : {}),
      }),
    })
    if (response.status === 409) {
      console.warn('[confirmTool] 工具确认状态已变化，忽略重复确认', {
        callId,
        confirmed,
        source,
      })
      debugStreamLog('[confirmTool] conflict response', {
        callId,
        confirmed,
        source,
        status: response.status,
        elapsedSinceFetchStartMs: elapsedMsSince(fetchStartedAt),
      })
      return
    }
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(detail || `工具确认失败: ${response.status}`)
    }
    const body = await response.json().catch(() => null)
    debugStreamLog('[confirmTool] response', {
      callId,
      confirmed,
      source,
      hasFeedback: Boolean(cleanFeedback),
      status: response.status,
      ok: Boolean(body?.ok),
      resumable: Boolean(body?.resumable),
      duplicate: Boolean(body?.duplicate),
      elapsedSinceFetchStartMs: elapsedMsSince(fetchStartedAt),
      elapsedSinceClickMs: elapsedMsSince(clickedAt),
    })
    if (body?.resumable === true) {
      await resumePausedSession(sid)
      setStreamEvents([])
      setIsStreaming(false)
      setCurrentStreamingMessage('')
      setSessionId(null)
      sessionIdRef.current = null
      isStreamingLockRef.current = false
    }
  }

  // 用于恢复已经记录确认结果但原 SSE 连接已断开的 session。
  const resumePausedSession = async (sid: string) => {
    const apiBaseUrl = options.apiBaseUrl || API_BASE_URL
    const response = await fetch(apiUrl('/api/ai/chat/resume-session', apiBaseUrl), {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ session_id: sid }),
    })
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(detail || `恢复 session 失败: ${response.status}`)
    }
    const body = await response.json()
    if (body.resume_content) {
      onResumeUpdate?.(body.resume_content)
    }
  }

  return {
    isStreaming,
    currentStreamingMessage,
    streamEvents,
    sessionId,
    sendStreamingMessage,
    stopStreaming,
    confirmTool,
    restorePendingConfirmation,
  }
}
