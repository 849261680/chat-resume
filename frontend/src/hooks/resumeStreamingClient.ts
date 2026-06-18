// 用于封装 Resume Agent 非 React 网络 streaming session。

import { API_BASE_URL, apiUrl } from '@/lib/httpClient'
import { createStreamingSseSession, type StreamingSseReduction } from './streamingSseSession'

export type ResumeStreamingFetch = typeof fetch

export interface ResumeStreamingClientOptions {
  apiBaseUrl?: string
  fallbackToolName: string
  fetchImpl?: ResumeStreamingFetch
}

export interface ResumeStreamingRequest {
  message: string
  resumeId: number
  chatHistory: Array<{ role: string; content: string }>
  visibleModules: string[]
  agentType: 'resume'
  clientRequestId: string
  signal?: AbortSignal
}

export interface ResumePendingConfirmation {
  sessionId: string
  action: {
    call_id?: string
    tool_name?: string
    tool_id?: string
    diff_summary?: string
    diff_items?: unknown
  }
}

interface PendingConfirmationResponse {
  session_id?: string | null
  pending_action?: ResumePendingConfirmation['action'] | null
}

export interface ResumeToolConfirmationResponse {
  ok?: boolean
  resumable?: boolean
  duplicate?: boolean
}

export class ResumeStreamingHttpError extends Error {
  status: number

  // 用于暴露 Resume streaming HTTP 状态码。
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ResumeStreamingHttpError'
    this.status = status
  }
}

export type ResumeStreamingReduction = StreamingSseReduction & {
  replayAttempted: boolean
}

export class ResumeStreamingClient {
  private readonly apiBaseUrl: string
  private readonly fallbackToolName: string
  private readonly fetchImpl: ResumeStreamingFetch

  constructor(options: ResumeStreamingClientOptions) {
    this.apiBaseUrl = options.apiBaseUrl || API_BASE_URL
    this.fallbackToolName = options.fallbackToolName
    const fetchImpl = options.fetchImpl || globalThis.fetch
    this.fetchImpl = (input, init) => fetchImpl.call(globalThis, input, init)
  }

  // 用于发送流式消息并按 SSE 帧产出协议规约结果。
  async *stream(request: ResumeStreamingRequest): AsyncGenerator<ResumeStreamingReduction> {
    const sseSession = createStreamingSseSession(this.fallbackToolName)
    let lastEventId: string | null = null
    let replayAttempted = false

    while (true) {
      const response = await this.postStream(request, lastEventId)
      const reader = response.body?.getReader()
      if (!reader) throw new Error('Response body is null')

      try {
        const decoder = new TextDecoder()
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const reductions = sseSession.pushChunk(decoder.decode(value, { stream: true }))
          for (const reduction of reductions) {
            if (reduction.nextCursor) lastEventId = reduction.nextCursor
            yield { ...reduction, replayAttempted }
            if (reduction.data.done || reduction.data.error) return
          }
        }
      } finally {
        reader.releaseLock()
      }

      if (!lastEventId || replayAttempted) return
      replayAttempted = true
    }
  }

  // 用于读取后端持久化的待确认工具动作。
  async restorePendingConfirmation(resumeId: number): Promise<ResumePendingConfirmation | null> {
    const response = await this.fetchImpl(
      apiUrl(`/api/ai/chat/pending-confirmation?resume_id=${resumeId}`, this.apiBaseUrl),
      { credentials: 'include' },
    )
    if (!response.ok) return null
    const body = await response.json().catch(() => null) as PendingConfirmationResponse | null
    const action = body?.pending_action
    if (!body?.session_id || !action?.call_id) return null
    return { sessionId: body.session_id, action }
  }

  // 用于提交工具确认或拒绝。
  async confirmTool(params: {
    sessionId: string
    callId: string
    confirmed: boolean
    source: string
    feedback?: string
  }): Promise<ResumeToolConfirmationResponse> {
    const response = await this.fetchImpl(apiUrl('/api/ai/chat/confirm-tool', this.apiBaseUrl), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: params.sessionId,
        call_id: params.callId,
        confirmed: params.confirmed,
        source: params.source,
        ...(params.feedback ? { feedback: params.feedback } : {}),
      }),
    })
    if (response.status === 409) return { duplicate: true }
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(detail || `工具确认失败: ${response.status}`)
    }
    return await response.json().catch(() => ({})) as ResumeToolConfirmationResponse
  }

  // 用于恢复已记录确认结果但原 SSE 连接断开的 session。
  async resumePausedSession(sessionId: string): Promise<Record<string, unknown> | null> {
    const response = await this.fetchImpl(apiUrl('/api/ai/chat/resume-session', this.apiBaseUrl), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(detail || `恢复 session 失败: ${response.status}`)
    }
    const body = await response.json()
    return body.resume_content && typeof body.resume_content === 'object'
      ? body.resume_content as Record<string, unknown>
      : null
  }

  // 用于发送一次 Resume Agent streaming HTTP 请求。
  private async postStream(
    request: ResumeStreamingRequest,
    lastEventId: string | null,
  ): Promise<Response> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Client-Request-ID': request.clientRequestId,
    }
    if (lastEventId) headers['Last-Event-ID'] = lastEventId
    const response = await this.fetchImpl(apiUrl('/api/ai/chat/stream', this.apiBaseUrl), {
      method: 'POST',
      credentials: 'include',
      headers,
      body: JSON.stringify({
        message: request.message,
        resume_id: request.resumeId,
        chat_history: request.chatHistory,
        visible_modules: request.visibleModules,
        agent_type: request.agentType,
      }),
      signal: request.signal,
    })
    if (!response.ok) {
      throw new ResumeStreamingHttpError(response.status, `HTTP error! status: ${response.status}`)
    }
    return response
  }
}
