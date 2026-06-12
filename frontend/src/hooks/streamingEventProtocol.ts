// 用于定义 Resume Agent SSE payload 到前端 stream event 的协议边界。

export type DiffItem = {
  before?: string
  after?: string
  reason?: string
}

export type UserInputRequest = {
  question: string
  options: string[]
  category?: string
  context?: string
  allowCustom: boolean
}

export type StreamEvent =
  | { type: 'text'; content: string }
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
  | {
      type: 'user_input_request'
      callId?: string
      toolName?: string
      request: UserInputRequest
    }

export type StreamProtocolState = {
  content: string
  events: StreamEvent[]
  userInputRequest: UserInputRequest | null
}

export type StreamProtocolReduction = {
  state: StreamProtocolState
  event: StreamEvent | null
  ignoredAskUserToolEvent: boolean
  completedToolCallId?: string
  pendingToolCallId?: string
  decisionToolCallId?: string
}

const TOOL_NAME_ALIASES: Record<string, string> = {
  update_highlight: 'update_bullet',
  add_highlight: 'add_bullet',
  remove_highlight: 'remove_bullet',
}

// 用于标准化差异条目。
export function normalizeDiffItems(value: unknown): DiffItem[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => normalizeDiffItem(item))
}

// 用于标准化单条差异。
function normalizeDiffItem(value: unknown): DiffItem[] {
  if (!value || typeof value !== 'object') return []
  const record = value as Record<string, unknown>
  const diffItem: DiffItem = {}
  for (const key of ['before', 'after', 'reason'] as const) {
    const raw = record[key]
    if (raw !== undefined && raw !== null) diffItem[key] = String(raw)
  }
  return Object.keys(diffItem).length > 0 ? [diffItem] : []
}

// 用于标准化工具名称。
function normalizeToolName(name: string): string {
  return TOOL_NAME_ALIASES[name] || name
}

// 用于解析工具 id。
export function resolveToolId(data: Record<string, unknown>): string {
  if (data.tool_id) return normalizeToolName(String(data.tool_id))
  if (data.tool_name) return normalizeToolName(String(data.tool_name))
  const toolCall = data.tool_call
  if (!toolCall || typeof toolCall !== 'object') return ''
  const fn = (toolCall as { function?: unknown }).function
  if (!fn || typeof fn !== 'object' || !('name' in fn)) return ''
  return normalizeToolName(String((fn as { name?: unknown }).name || ''))
}

// 用于生成空的前端流协议状态。
export function createStreamProtocolState(): StreamProtocolState {
  return {
    content: '',
    events: [],
    userInputRequest: null,
  }
}

// 用于判断单个 SSE payload 是否属于工具生命周期事件。
export function isToolLifecyclePayload(data: Record<string, unknown>): boolean {
  const eventType = typeof data.event_type === 'string' ? data.event_type : ''
  return (
    eventType.startsWith('tool_') ||
    Boolean(data.tool_pending || data.tool_confirmed || data.tool_rejected)
  )
}

// 用于从 SSE id 行和 payload 中解析下一次 replay cursor。
export function resolveStreamCursor(
  data: Record<string, unknown>,
  pendingSseEventId: string | null,
): string | null {
  if (typeof data.event_id === 'string') return data.event_id
  return pendingSseEventId
}

// 用于压缩工具流事件，便于诊断前端状态切换。
export function summarizeToolEvents(events: StreamEvent[]): string[] {
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

// 用于判断 pending diff 是否需要先让同一工具的运行态渲染出来。
export function shouldYieldBeforePendingEvent(
  previousEvents: StreamEvent[],
  event: StreamEvent | null,
): boolean {
  if (!event || event.type !== 'tool_pending') return false
  return previousEvents.some((previousEvent) =>
    previousEvent.type === 'tool_call' && previousEvent.callId === event.callId
  )
}

// 用于把单个 SSE payload 规约到稳定的前端流协议状态。
export function reduceStreamSsePayload(
  state: StreamProtocolState,
  data: Record<string, unknown>,
  fallbackToolName: string,
): StreamProtocolReduction {
  const decision = toolDecisionFromSsePayload(data, fallbackToolName)
  if (decision) {
    return reduceToolDecision(state, decision, data)
  }

  const event = streamEventFromSsePayload(data, fallbackToolName)
  if (!event) return reduction(state, null)
  if (isAskUserToolLifecycleEvent(event, data)) {
    return { ...reduction(state, event), ignoredAskUserToolEvent: true }
  }
  if (event.type === 'text') return reduceTextEvent(state, event)
  if (event.type === 'tool_result') return reduceToolCompletion(state, event)
  if (event.type === 'tool_failed') return reduceToolCompletion(state, event)
  if (event.type === 'tool_pending') return reduceToolPending(state, event)
  if (event.type === 'user_input_request') return reduceUserInputRequest(state, event)
  if (event.type === 'tool_call') return reduceAppendOnlyEvent(state, event)
  return reduction(state, event)
}

// 用于解析工具输入。
function resolveToolInput(data: Record<string, unknown>): Record<string, unknown> | undefined {
  if (data.tool_input && typeof data.tool_input === 'object') {
    return data.tool_input as Record<string, unknown>
  }
  return toolInputFromToolCall(data.tool_call)
}

// 用于从 tool_call.function.arguments 解析工具输入。
function toolInputFromToolCall(toolCall: unknown): Record<string, unknown> | undefined {
  if (!toolCall || typeof toolCall !== 'object') return undefined
  const fn = (toolCall as { function?: unknown }).function
  if (!fn || typeof fn !== 'object') return undefined
  const raw = (fn as { arguments?: unknown }).arguments
  if (raw && typeof raw === 'object') return raw as Record<string, unknown>
  if (typeof raw !== 'string') return undefined
  return parseObjectJson(raw)
}

// 用于解析对象 JSON。
function parseObjectJson(value: string): Record<string, unknown> | undefined {
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : undefined
  } catch {
    return undefined
  }
}

// 用于把后端询问工具载荷标准化成前端卡片数据。
function normalizeUserInputRequest(value: unknown): UserInputRequest | null {
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  const question = typeof record.question === 'string' ? record.question.trim() : ''
  const options = normalizeStringOptions(record.options)
  if (!question || options.length === 0) return null
  const request: UserInputRequest = {
    question,
    options,
    allowCustom: record.allow_custom !== false,
  }
  if (typeof record.category === 'string') request.category = record.category
  if (typeof record.context === 'string') request.context = record.context
  return request
}

// 用于标准化选项数组。
function normalizeStringOptions(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((option) => String(option).trim())
    .filter((option) => option.length > 0)
}

// 用于解析工具名称。
function resolveToolName(data: Record<string, unknown>, fallbackName: string): string {
  if (data.tool_display_name) return normalizeToolName(String(data.tool_display_name))
  if (data.tool_name) return normalizeToolName(String(data.tool_name))
  const calls = Array.isArray(data.tool_calls) ? data.tool_calls : []
  const lastCall = calls[calls.length - 1]
  if (!lastCall || typeof lastCall !== 'object' || !('name' in lastCall)) return fallbackName
  return normalizeToolName(String((lastCall as { name?: unknown }).name || ''))
}

// 用于把单个 SSE payload 映射为可直接追加的前端事件。
export function streamEventFromSsePayload(
  data: Record<string, unknown>,
  fallbackToolName: string,
): StreamEvent | null {
  if (data.event_type === 'tool_call' && data.call_id) {
    return toolCallEventFromPayload(data, fallbackToolName)
  }
  if (data.event_type === 'tool_result') {
    return toolResultEventFromPayload(data, fallbackToolName)
  }
  if (data.event_type === 'tool_call_failed' && data.call_id) {
    return toolFailedEventFromPayload(data, fallbackToolName)
  }
  if (data.tool_pending && data.call_id) {
    return toolPendingEventFromPayload(data, fallbackToolName)
  }
  if (data.event_type === 'user_input_request') {
    return userInputEventFromPayload(data)
  }
  if (data.content) {
    return { type: 'text', content: String(data.content) }
  }
  return null
}

// 用于把工具确认/拒绝 SSE payload 映射为前端事件。
export function toolDecisionFromSsePayload(
  data: Record<string, unknown>,
  fallbackToolName: string,
): Extract<StreamEvent, { type: 'tool_confirmed' | 'tool_rejected' }> | null {
  if (!(data.tool_confirmed || data.tool_rejected) || !data.call_id) return null
  return {
    type: data.tool_confirmed ? 'tool_confirmed' : 'tool_rejected',
    callId: String(data.call_id),
    toolName: resolveToolName(data, fallbackToolName),
    toolId: resolveToolId(data),
    diffSummary: data.diff_summary ? String(data.diff_summary) : '',
    diffItems: normalizeDiffItems(data.diff_items),
  }
}

// 用于构造工具调用事件。
function toolCallEventFromPayload(
  data: Record<string, unknown>,
  fallbackToolName: string,
): Extract<StreamEvent, { type: 'tool_call' }> {
  return {
    type: 'tool_call',
    callId: String(data.call_id),
    toolName: resolveToolName(data, fallbackToolName),
    toolId: resolveToolId(data),
    toolInput: resolveToolInput(data),
    displayMessage: data.display_message ? String(data.display_message) : undefined,
  }
}

// 用于构造工具结果事件。
function toolResultEventFromPayload(
  data: Record<string, unknown>,
  fallbackToolName: string,
): Extract<StreamEvent, { type: 'tool_result' }> {
  return {
    type: 'tool_result',
    callId: data.call_id ? String(data.call_id) : undefined,
    toolName: resolveToolName(data, fallbackToolName),
    toolId: resolveToolId(data),
    displayMessage: data.display_message ? String(data.display_message) : undefined,
  }
}

// 用于构造工具失败事件。
function toolFailedEventFromPayload(
  data: Record<string, unknown>,
  fallbackToolName: string,
): Extract<StreamEvent, { type: 'tool_failed' }> {
  return {
    type: 'tool_failed',
    callId: String(data.call_id),
    toolName: resolveToolName(data, fallbackToolName),
    toolId: resolveToolId(data),
    displayMessage: data.display_message ? String(data.display_message) : undefined,
  }
}

// 用于构造工具待确认事件。
function toolPendingEventFromPayload(
  data: Record<string, unknown>,
  fallbackToolName: string,
): Extract<StreamEvent, { type: 'tool_pending' }> {
  return {
    type: 'tool_pending',
    callId: String(data.call_id),
    toolName: resolveToolName(data, fallbackToolName),
    toolId: resolveToolId(data),
    toolInput: resolveToolInput(data),
    diffSummary: data.diff_summary ? String(data.diff_summary) : '',
    diffItems: normalizeDiffItems(data.diff_items),
  }
}

// 用于构造追问用户事件。
function userInputEventFromPayload(data: Record<string, unknown>): Extract<StreamEvent, { type: 'user_input_request' }> | null {
  const request = normalizeUserInputRequest(data.user_input_request)
  if (!request) return null
  return {
    type: 'user_input_request',
    callId: data.call_id ? String(data.call_id) : undefined,
    toolName: data.tool_display_name ? String(data.tool_display_name) : undefined,
    request,
  }
}

// 用于生成无副作用规约结果。
function reduction(
  state: StreamProtocolState,
  event: StreamEvent | null,
): StreamProtocolReduction {
  return {
    state,
    event,
    ignoredAskUserToolEvent: false,
  }
}

// 用于判断 ask_user 的底层工具调用是否应从工具活动流里隐藏。
function isAskUserToolLifecycleEvent(
  event: StreamEvent,
  data: Record<string, unknown>,
): boolean {
  if (resolveToolId(data) !== 'ask_user') return false
  return event.type === 'tool_call' || event.type === 'tool_result' || event.type === 'tool_failed'
}

// 用于把文本增量合并进内容和事件列表。
function reduceTextEvent(
  state: StreamProtocolState,
  event: Extract<StreamEvent, { type: 'text' }>,
): StreamProtocolReduction {
  const last = state.events[state.events.length - 1]
  const events = last?.type === 'text'
    ? [...state.events.slice(0, -1), { type: 'text' as const, content: last.content + event.content }]
    : [...state.events, event]
  return reduction({
    ...state,
    content: state.content + event.content,
    events,
  }, event)
}

// 用于追加不需要状态转移的事件。
function reduceAppendOnlyEvent(
  state: StreamProtocolState,
  event: Extract<StreamEvent, { type: 'tool_call' }>,
): StreamProtocolReduction {
  return reduction({
    ...state,
    events: [...state.events, event],
  }, event)
}

// 用于把工具调用事件推进到完成或失败状态。
function reduceToolCompletion(
  state: StreamProtocolState,
  event: Extract<StreamEvent, { type: 'tool_result' | 'tool_failed' }>,
): StreamProtocolReduction {
  const callId = event.callId || ''
  if (!callId) {
    return reduction({
      ...state,
      events: [...state.events, event],
    }, event)
  }
  let updated = false
  const events = state.events.map((existingEvent) => {
    if (existingEvent.type !== 'tool_call' || existingEvent.callId !== callId) {
      return existingEvent
    }
    updated = true
    return {
      type: event.type,
      callId,
      toolName: existingEvent.toolName || event.toolName,
      toolId: existingEvent.toolId || event.toolId,
      displayMessage: event.displayMessage,
    }
  })
  const nextEvents = updated || events.some((existingEvent) => (
    existingEvent.type === event.type && existingEvent.callId === callId
  ))
    ? events
    : [...events, event]
  return {
    ...reduction({ ...state, events: nextEvents }, event),
    completedToolCallId: callId,
  }
}

// 用于追加等待确认的工具事件。
function reduceToolPending(
  state: StreamProtocolState,
  event: Extract<StreamEvent, { type: 'tool_pending' }>,
): StreamProtocolReduction {
  return {
    ...reduction({
      ...state,
      events: [...state.events, event],
    }, event),
    pendingToolCallId: event.callId,
  }
}

// 用于记录需要用户补充信息的事件。
function reduceUserInputRequest(
  state: StreamProtocolState,
  event: Extract<StreamEvent, { type: 'user_input_request' }>,
): StreamProtocolReduction {
  return reduction({
    ...state,
    events: [...state.events, event],
    userInputRequest: event.request,
  }, event)
}

// 用于把工具待确认状态推进为已确认或已拒绝。
function reduceToolDecision(
  state: StreamProtocolState,
  decision: Extract<StreamEvent, { type: 'tool_confirmed' | 'tool_rejected' }>,
  data: Record<string, unknown>,
): StreamProtocolReduction {
  const events = state.events.flatMap((event) => {
    if (event.type === 'tool_call' && event.callId === decision.callId) {
      return [{
        type: 'tool_result' as const,
        callId: decision.callId,
        toolName: event.toolName,
        toolId: event.toolId,
        displayMessage: data.display_message ? String(data.display_message) : undefined,
      }]
    }
    if (event.type !== 'tool_pending' || event.callId !== decision.callId) {
      return [event]
    }
    return [{
      type: decision.type,
      callId: event.callId,
      toolName: event.toolName || decision.toolName,
      toolId: event.toolId || decision.toolId,
      diffSummary: decision.diffSummary || event.diffSummary,
      diffItems: decision.diffItems?.length ? decision.diffItems : event.diffItems,
    }]
  })
  return {
    ...reduction({ ...state, events }, decision),
    decisionToolCallId: decision.callId,
  }
}
