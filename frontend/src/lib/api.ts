import type { ResumeContent } from '@/types/resume'
import type { ResumeLayoutConfig } from './resumeLayoutConfig'
import { apiFetch, fetchWithTimeout, handleApiResponse } from './httpClient'

// 简历内容接口定义
export interface Resume {
  id: number
  title: string
  content: ResumeContent
  layout_config?: Record<string, unknown> | null
  original_filename?: string
  owner_id: number
  created_at: string
  updated_at?: string
}

export interface ResumeListItem {
  id: number
  title: string
  original_filename?: string
  owner_id: number
  created_at: string
  updated_at?: string
  target_company?: string
  target_title?: string
  layout_config?: Record<string, unknown> | null
  preview_content?: Partial<ResumeContent>
}

interface CreateResumeData {
  title: string
  content: ResumeContent
  layout_config?: Record<string, unknown> | null
  original_filename?: string
}

interface UpdateResumeData {
  title?: string
  content?: ResumeContent
}

interface ExportResponse {
  download_url: string
  filename: string
  format: string
}

interface JDOcrResponse {
  text: string
}

interface ResumeUploadJobCreated {
  job_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
}

interface ResumeUploadJobStatus {
  job_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  resume_id?: number | null
  error?: string | null
  original_filename: string
}

interface InterviewTurnEvaluation {
  summary?: string
  gaps?: string[]
  evidence?: string[]
  advice?: string
}

interface InterviewTurn {
  id: number
  turn_index: number
  round_index: number
  question: string
  question_type: string
  intent?: string
  expected_points?: string[]
  answer?: string
  evaluation?: InterviewTurnEvaluation | null
  follow_up_count: number
  status: string
}

interface LearningPriority {
  topic: string
  level: string
}

interface RoadmapPhase {
  phase: string
  timeframe: string
  items: string[]
}

interface LearningPlan {
  learning_priorities?: LearningPriority[]
  improvement_roadmap?: RoadmapPhase[]
}

interface InterviewReportDimension {
  title: string
  score?: number
  assessment: string
  evidence: string
  advice: string
}

interface InterviewCandidateVerdict {
  level?: string
  label?: string
  reason?: string
}

interface InterviewJobMatch {
  target_title?: string
  target_company?: string
  required_capabilities?: string[]
  covered_capabilities?: string[]
  missing_capabilities?: string[]
  interviewer_concerns?: string[]
  likely_followups?: string[]
}

interface InterviewAnswerRewrite {
  turn_index?: number | null
  original_problem?: string
  recommended_answer?: string
  why_better?: string
}

interface InterviewSession {
  id: number
  resume_id: number
  target_title?: string
  target_company?: string
  jd_text?: string
  interview_type: string
  difficulty: string
  language: string
  mode: string
  status: string
  current_round_index: number
  current_turn_index: number
  plan?: {
    rounds?: Array<{ type: string; goal: string }>
  }
  started_at?: string
  ended_at?: string
  report_data?: {
    summary?: string
    candidate_verdict?: InterviewCandidateVerdict
    job_match?: InterviewJobMatch
    strengths?: string[]
    dimensions?: InterviewReportDimension[]
    recurring_issues?: string[]
    weaknesses?: string[]
    interviewer_risks?: string[]
    answer_rewrites?: InterviewAnswerRewrite[]
    next_training_plan?: string[]
    resume_feedback?: string[]
    interviewer_evaluation?: {
      overall?: string
      key_observations?: string[]
      core_recommendations?: string[]
    }
    learning_plan?: LearningPlan
  }
  turns: InterviewTurn[]
  current_turn?: InterviewTurn | null
}

interface InterviewSessionSummary {
  id: number
  resume_id: number
  target_title?: string
  target_company?: string
  jd_text?: string
  interview_type: string
  difficulty: string
  language: string
  mode: string
  status: string
  started_at?: string
  ended_at?: string
  answered_turn_count: number
  has_report?: boolean
}

interface InterviewActionResponse {
  session: InterviewSession
  message?: string
  evaluation?: InterviewTurn['evaluation']
  next_action?: string
}

interface InterviewReportProgressEvent {
  event_type: string
  phase?: string
  label?: string
  status?: string
  progress?: number
  done?: boolean
  generated?: boolean
  next_action?: string
  message?: string
  session?: InterviewSession
}

interface DigitalHumanConversation {
  provider: 'volcengine'
  session_id: string
  status: string
}

interface PayPalSubscriptionCheckout {
  provider: 'paypal'
  subscription_id: string
  status: string
  approval_url: string
}

interface BillingStatus {
  provider: 'paypal' | null
  subscription_id: string | null
  status: string
  is_active: boolean
}

interface PayPalPlan {
  id: string
  name: string
  price: string
  currency_code: string
}

// 用于解析报告生成 SSE 事件并返回最终动作响应。
async function readInterviewReportStream(
  response: Response,
  onEvent: (event: InterviewReportProgressEvent) => void,
): Promise<InterviewActionResponse> {
  if (!response.body) {
    throw new Error('报告生成响应为空')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let dataLines: string[] = []
  const finalEventRef: { current?: InterviewReportProgressEvent } = {}

  const flushEvent = () => {
    if (dataLines.length === 0) return
    const event = JSON.parse(dataLines.join('\n')) as InterviewReportProgressEvent
    dataLines = []
    onEvent(event)
    if (event.done) finalEventRef.current = event
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split(/\r?\n/)
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line) {
        flushEvent()
        continue
      }
      if (line.startsWith('data: ')) dataLines.push(line.slice(6))
    }
  }

  buffer += decoder.decode()
  if (buffer.startsWith('data: ')) dataLines.push(buffer.slice(6))
  flushEvent()

  const finalEvent = finalEventRef.current
  if (finalEvent?.event_type === 'error') {
    throw new Error(finalEvent.message || '生成报告失败')
  }
  if (finalEvent?.session) {
    return {
      session: finalEvent.session,
      message: finalEvent.message,
      next_action: finalEvent.next_action,
    }
  }
  throw new Error('报告生成流未返回最终结果')
}


// 简历API类
class ResumeAPI {
  /**
   * 获取所有简历
   */
  // 用于获取简历。
  static async getResumes(): Promise<ResumeListItem[]> {
    const response = await apiFetch('/api/resumes/')

    return handleApiResponse<ResumeListItem[]>(response)
  }

  /**
   * 获取单个简历
   */
  // 用于获取简历。
  static async getResume(id: number): Promise<Resume> {
    const response = await apiFetch(`/api/resumes/${id}`)

    return handleApiResponse<Resume>(response)
  }

  /**
   * 创建新简历
   */
  // 用于创建简历。
  static async createResume(data: CreateResumeData): Promise<Resume> {
    const response = await apiFetch('/api/resumes/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })

    return handleApiResponse<Resume>(response)
  }

  /**
   * 更新简历
   */
  // 用于更新简历。
  static async updateResume(id: number, data: UpdateResumeData): Promise<Resume> {
    const response = await apiFetch(`/api/resumes/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })

    return handleApiResponse<Resume>(response)
  }

  /**
   * 删除简历
   */
  // 用于处理delete简历。
  static async deleteResume(id: number): Promise<void> {
    const response = await apiFetch(`/api/resumes/${id}`, {
      method: 'DELETE',
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `删除简历失败: ${response.status}`)
    }
  }

  /**
   * 上传简历文件
   */
  // 用于处理upload简历。
  static async uploadResume(file: File): Promise<ResumeUploadJobCreated> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await apiFetch('/api/upload/resume', {
      method: 'POST',
      body: formData,
    })

    return handleApiResponse<ResumeUploadJobCreated>(response)
  }

  /**
   * 查询简历上传解析任务状态
   */
  // 用于获取简历uploadjob。
  static async getResumeUploadJob(jobId: string): Promise<ResumeUploadJobStatus> {
    const response = await apiFetch(`/api/upload/resume-jobs/${jobId}`)

    return handleApiResponse<ResumeUploadJobStatus>(response)
  }

  /**
   * 识别 JD 图片中的文字
   */
  // 用于处理ocrjobdescriptionimage。
  static async ocrJobDescriptionImage(file: File): Promise<JDOcrResponse> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await apiFetch('/api/upload/jd-ocr', {
      method: 'POST',
      body: formData,
    })

    return handleApiResponse<JDOcrResponse>(response)
  }

  /**
   * 导出简历
   */
  // 用于处理export简历。
  static async exportResume(
    id: number,
    format: 'pdf' | 'docx' | 'html',
    template: string = 'default',
    layoutConfig?: ResumeLayoutConfig | Record<string, unknown>,
  ): Promise<ExportResponse> {
    const response = await apiFetch(`/api/resumes/${id}/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        format,
        template,
        layout_config: layoutConfig,
      }),
    })

    return handleApiResponse<ExportResponse>(response)
  }

  // 用于处理list面试会话。
  static async listInterviewSessions(): Promise<InterviewSessionSummary[]> {
    const response = await apiFetch('/api/interviews/')
    return handleApiResponse<InterviewSessionSummary[]>(response)
  }

  /**
   * 删除一条面试记录
   */
  // 用于处理delete面试会话。
  static async deleteInterviewSession(sessionId: number): Promise<void> {
    const response = await apiFetch(`/api/interviews/${sessionId}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `删除面试记录失败: ${response.status}`)
    }
  }

  // 用于创建面试会话。
  static async createInterviewSession(data: {
    resume_id: number
    target_title?: string
    target_company?: string
    jd_text?: string
    interview_type?: string
    difficulty?: string
    language?: string
    mode?: string
  }): Promise<InterviewActionResponse> {
    const response = await apiFetch('/api/interviews/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  // 用于基于历史面试创建新的复练会话。
  static async retryInterviewSession(sessionId: number): Promise<InterviewActionResponse> {
    const response = await apiFetch(`/api/interviews/${sessionId}/retry`, {
      method: 'POST',
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  // 用于获取面试会话。
  static async getInterviewSession(sessionId: number): Promise<InterviewActionResponse> {
    const response = await apiFetch(`/api/interviews/${sessionId}`)
    return handleApiResponse<InterviewActionResponse>(response)
  }

  // 用于处理record面试消息。
  static async recordInterviewMessage(
    sessionId: number,
    data: { role: 'candidate' | 'interviewer'; text: string },
  ): Promise<InterviewActionResponse> {
    const response = await apiFetch(`/api/interviews/${sessionId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  // 用于处理end面试会话。
  static async endInterviewSession(sessionId: number): Promise<InterviewActionResponse> {
    const response = await apiFetch(`/api/interviews/${sessionId}/end`, {
      method: 'POST',
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  // 用于生成面试评估报告。
  static async generateInterviewReport(sessionId: number): Promise<InterviewActionResponse> {
    const response = await apiFetch(`/api/interviews/${sessionId}/report`, {
      method: 'POST',
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  // 用于流式生成面试评估报告并接收真实后端阶段。
  static async generateInterviewReportStream(
    sessionId: number,
    onEvent: (event: InterviewReportProgressEvent) => void,
  ): Promise<InterviewActionResponse> {
    const response = await apiFetch(`/api/interviews/${sessionId}/report/stream`, {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
      },
    })
    if (!response.ok) return handleApiResponse<InterviewActionResponse>(response)
    return readInterviewReportStream(response, onEvent)
  }
}

class DigitalHumanAPI {
  /**
   * 为实时语音面试创建数字人会话。
   */
  // 用于创建conversation。
  static async createConversation(interviewSessionId: number): Promise<DigitalHumanConversation> {
    const response = await fetchWithTimeout('/api/digital-human/conversations', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ interview_session_id: interviewSessionId }),
    })
    return handleApiResponse<DigitalHumanConversation>(response)
  }
}

class BillingAPI {
  // 用于获取状态。
  static async getStatus(): Promise<BillingStatus> {
    const response = await apiFetch('/api/billing/status')
    return handleApiResponse<BillingStatus>(response)
  }

  // 用于获取paypal套餐。
  static async getPayPalPlan(): Promise<PayPalPlan> {
    const response = await apiFetch('/api/billing/paypal/plan')
    return handleApiResponse<PayPalPlan>(response)
  }

  // 用于创建paypalsubscription。
  static async createPayPalSubscription(): Promise<PayPalSubscriptionCheckout> {
    const response = await apiFetch('/api/billing/paypal/subscriptions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    })
    return handleApiResponse<PayPalSubscriptionCheckout>(response)
  }

  // 用于处理syncpaypalsubscription。
  static async syncPayPalSubscription(subscriptionId: string): Promise<BillingStatus> {
    const response = await apiFetch(`/api/billing/paypal/subscriptions/${subscriptionId}/sync`)
    return handleApiResponse<BillingStatus>(response)
  }

  // 用于处理cancelpaypalsubscription。
  static async cancelPayPalSubscription(subscriptionId: string): Promise<BillingStatus> {
    const response = await apiFetch(`/api/billing/paypal/subscriptions/${subscriptionId}/cancel`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    })
    return handleApiResponse<BillingStatus>(response)
  }
}

// ── 聊天记录 API ──────────────────────────────────────────────────────────────

interface ChatMessageRecord {
  id: number
  role: 'user' | 'assistant'
  content: string
  stream_events?: Array<{ type: string; [key: string]: unknown }> | null
}

class ChatHistoryAPI {
  // 用于获取消息。
  static async getMessages(resumeId: number): Promise<ChatMessageRecord[]> {
    const res = await apiFetch(`/api/resumes/${resumeId}/chat-messages`)
    return handleApiResponse<ChatMessageRecord[]>(res)
  }

  // 用于处理append消息。
  static async appendMessages(
    resumeId: number,
    messages: { role: string; content: string; stream_events?: unknown }[]
  ): Promise<ChatMessageRecord[]> {
    const res = await apiFetch(`/api/resumes/${resumeId}/chat-messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(messages),
    })
    return handleApiResponse<ChatMessageRecord[]>(res)
  }

  // 用于清理消息。
  static async clearMessages(resumeId: number): Promise<void> {
    const res = await apiFetch(`/api/resumes/${resumeId}/chat-messages`, {
      method: 'DELETE',
    })
    await handleApiResponse<{ message: string }>(res)
  }
}

// 导出API实例
export const resumeApi = ResumeAPI
export const chatHistoryApi = ChatHistoryAPI
export const digitalHumanApi = DigitalHumanAPI
export const billingApi = BillingAPI

// 导出类型
export type {
  BillingStatus,
  DigitalHumanConversation,
  PayPalPlan,
  PayPalSubscriptionCheckout,
  ResumeUploadJobStatus,
  ResumeContent,
  InterviewSession,
  InterviewSessionSummary,
  InterviewReportProgressEvent,
}
