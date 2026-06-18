// 用于提供 hooks/useStreamingChat.ts 模块。
import { useCallback, useRef, useState } from 'react'
import { API_BASE_URL } from '@/lib/httpClient'
import { useTranslations } from 'next-intl'
import { commitCompletedStreamMessage } from './streamingCompletion'
import { ResumeStreamingClient, ResumeStreamingHttpError } from './resumeStreamingClient'
import { createStreamingUiSession, type StreamingUiSession } from './streamingUiSession'
import { buildStreamingViewStatePatch } from './streamingViewState'
import {
  isToolLifecyclePayload,
  summarizeToolEvents,
  type DiffItem,
  type StreamEvent,
  type UserInputRequest,
} from './streamingEventProtocol'

export type { DiffItem, StreamEvent, UserInputRequest } from './streamingEventProtocol'

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

// 用于等待浏览器提交上一帧工具运行态，避免 pending diff 与 tool_call 同帧出现。
function waitForNextPaint(): Promise<void> {
  if (typeof window === 'undefined') return Promise.resolve()
  return new Promise((resolve) => {
    window.requestAnimationFrame(() => resolve())
  })
}

// 用于封装流式聊天相关状态和行为。
export function useStreamingChat(resumeId: number, options: StreamingChatOptions = {}) {
  const t = useTranslations('resume.editor')
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('')
  const [streamEvents, setStreamEvents] = useState<StreamEvent[]>([])
  const [userInputRequest, setUserInputRequest] = useState<UserInputRequest | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const lastEventIdRef = useRef<string | null>(null)
  const sseEventSequenceRef = useRef(0)
  const uiSessionRef = useRef<StreamingUiSession | null>(null)
  if (!uiSessionRef.current) {
    uiSessionRef.current = createStreamingUiSession({ debugLog: debugStreamLog })
  }
  const uiSession = uiSessionRef.current

  const {
    onMessage,
    onError,
    apiBaseUrl = API_BASE_URL,
    onQrImages,
    onResumeUpdate,
    visibleModules = [],
    agentType = 'resume'
  } = options

  // 用于创建非 React streaming client，集中网络状态机和工具确认请求。
  const createStreamingClient = () => new ResumeStreamingClient({
    apiBaseUrl,
    fallbackToolName: t('toolCall'),
  })

  // 用于处理send流式消息。
  const sendStreamingMessage = async (message: string, chatHistory: ChatMessage[] = []) => {
    // 使用 ref 做立即检查，防止并发调用
    if (!uiSession.beginStreaming()) {
      debugStreamLog('[useStreamingChat] 已有流式请求进行中，跳过重复调用')
      return
    }
    setUserInputRequest(null)

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
      const streamingClient = createStreamingClient()
      let firstSseReceivedLogged = false
      let firstContentRenderedLogged = false

      logStreamPhase('fetch_start', streamStartedAt, clientRequestId)
      for await (const reduced of streamingClient.stream({
            message,
            resumeId,
            chatHistory: historyToSend,
            visibleModules,
            agentType,
            clientRequestId,
            signal: abortControllerRef.current.signal,
          })) {
            const data = reduced.data
            const protocolState = reduced.state
            const previousEvents = reduced.previousEvents
            const protocolEvent = reduced.protocolEvent
            const viewPatch = buildStreamingViewStatePatch(reduced)
            if (!firstSseReceivedLogged) {
              firstSseReceivedLogged = true
              logStreamPhase('first_sse_received', streamStartedAt, clientRequestId, {
                replay: reduced.replayAttempted,
                eventType: typeof data.event_type === 'string' ? data.event_type : '',
                hasContent: Boolean(data.content),
                done: Boolean(data.done),
              })
            }
            if (viewPatch.nextCursor) lastEventIdRef.current = viewPatch.nextCursor
            const eventType = typeof data.event_type === 'string' ? data.event_type : ''
            const isToolEvent = isToolLifecyclePayload(data)
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
                eventsBefore: summarizeToolEvents(previousEvents),
              })
            }

            if (viewPatch.error) {
              onError?.(formatStreamError(viewPatch.error, clientRequestId))
              return
            }

            if (viewPatch.doneMessage) {
              logStreamPhase('done_received', streamStartedAt, clientRequestId, {
                eventType,
                hadContent: Boolean(viewPatch.doneMessage.content),
                streamEventCount: protocolState.events.length,
              })
              if (viewPatch.doneMessage.resumeContent) {
                debugStreamLog('[useStreamingChat] done 事件收到 resume_content', {
                  sections: Object.keys(viewPatch.doneMessage.resumeContent),
                })
                onResumeUpdate?.(viewPatch.doneMessage.resumeContent)
              }
              const aiMessage: ChatMessage = {
                id: Date.now().toString(),
                type: 'ai',
                content: viewPatch.doneMessage.content,
                timestamp: new Date(),
                streamEvents: viewPatch.doneMessage.streamEvents,
              }
              commitCompletedStreamMessage(aiMessage, onMessage, () => {
                setIsStreaming(false)
                setCurrentStreamingMessage('')
                setStreamEvents([])
              })
              return
            }

            if (viewPatch.sessionId) {
              uiSession.setSessionId(viewPatch.sessionId)
              setSessionId(viewPatch.sessionId)
            }

            if (viewPatch.qrImages) {
              onQrImages?.(viewPatch.qrImages)
            }

            if (viewPatch.ignoredAskUserToolEvent) continue

            if (protocolEvent?.type === 'tool_pending' && viewPatch.pendingToolCallId) {
              const callId = viewPatch.pendingToolCallId
              uiSession.recordPendingTool({
                callId,
                toolName: protocolEvent.toolName,
                diffItemCount: Array.isArray(data.diff_items) ? data.diff_items.length : 0,
                streamStartedAt,
                clientRequestId,
                previousEvents,
                eventsAfter: protocolState.events,
              })
            }

            if (viewPatch.decisionToolCallId) {
              uiSession.recordToolDecision(
                viewPatch.decisionToolCallId,
                protocolEvent?.type || '',
                previousEvents,
                protocolState.events,
              )
            }

            if (viewPatch.completedToolCallId) {
              uiSession.recordToolCompletion(
                viewPatch.completedToolCallId,
                protocolEvent?.type || '',
                previousEvents,
                protocolState.events,
              )
            }

            if (viewPatch.resumeContent) {
              debugStreamLog('[useStreamingChat] 收到 resume_content，触发预览更新', {
                sections: Object.keys(viewPatch.resumeContent),
              })
              onResumeUpdate?.(viewPatch.resumeContent)
            }

            if (viewPatch.currentStreamingMessage !== undefined) {
              setCurrentStreamingMessage(viewPatch.currentStreamingMessage)
              if (!firstContentRenderedLogged) {
                firstContentRenderedLogged = true
                window.requestAnimationFrame(() => {
                  logStreamPhase('first_content_rendered', streamStartedAt, clientRequestId, {
                    contentChars: viewPatch.currentStreamingMessage?.length ?? 0,
                    streamEventCount: protocolState.events.length,
                  })
                })
              }
            }
            if (viewPatch.userInputRequest !== undefined) {
              setUserInputRequest(viewPatch.userInputRequest)
            }
            if (viewPatch.streamEvents) {
              if (viewPatch.yieldBeforeStreamEvents && viewPatch.previousEventsBeforeYield) {
                setStreamEvents(viewPatch.previousEventsBeforeYield)
                await waitForNextPaint()
              }
              setStreamEvents(viewPatch.streamEvents)
            }
          }

    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        debugStreamLog('Streaming aborted', { clientRequestId })
      } else {
        console.error('Streaming error:', { error, clientRequestId })
        const errorMessage = error instanceof ResumeStreamingHttpError && error.status === 401
          ? t('authExpired')
          : error instanceof Error ? error.message : 'Unknown streaming error'
        onError?.(formatStreamError(errorMessage, clientRequestId))
      }
    } finally {
      uiSession.reset()
      setIsStreaming(false)
      setCurrentStreamingMessage('')
      setStreamEvents([])
      setSessionId(null)
      abortControllerRef.current = null
    }
  }

  // 用于处理stop流式。
  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    uiSession.reset()
    setIsStreaming(false)
    setCurrentStreamingMessage('')
    setStreamEvents([])
    setSessionId(null)
  }

  // 用于从后端恢复持久化的待确认工具 diff。
  const restorePendingConfirmation = useCallback(async () => {
    const restored = await uiSession.restorePendingConfirmation(createStreamingClient(), resumeId)
    if (!restored) return
    setSessionId(restored.sessionId)
    setIsStreaming(true)
    setStreamEvents([restored.event])
  }, [apiBaseUrl, resumeId, t, uiSession])

  // 用于处理confirm工具。
  const confirmTool = async (
    callId: string,
    confirmed: boolean,
    source = 'unknown',
    feedback?: string,
  ) => {
    const result = await uiSession.confirmTool(createStreamingClient(), {
      callId,
      confirmed,
      source,
      feedback,
    })
    if (result.status === 'resumable') {
      if (result.resumeContent) onResumeUpdate?.(result.resumeContent)
      setStreamEvents([])
      setIsStreaming(false)
      setCurrentStreamingMessage('')
      setSessionId(null)
      uiSession.reset()
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
    userInputRequest,
    clearUserInputRequest: () => setUserInputRequest(null),
  }
}
