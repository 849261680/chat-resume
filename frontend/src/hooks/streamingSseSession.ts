// 用于把 Resume Agent SSE 文本流规约成前端 StreamEvent 状态。
import {
  createStreamProtocolState,
  reduceStreamSsePayload,
  resolveStreamCursor,
  type StreamEvent,
  type StreamProtocolReduction,
  type StreamProtocolState,
} from './streamingEventProtocol.ts'

export type StreamingSseReduction = StreamProtocolReduction & {
  data: Record<string, unknown>
  previousEvents: StreamEvent[]
  nextCursor: string | null
  protocolEvent: StreamEvent | null
}

type ParsedSseLine =
  | { type: 'id'; value: string }
  | { type: 'data'; value: Record<string, unknown> }
  | { type: 'ignore' }

// 用于创建一次 Resume Agent SSE 解析 session。
export function createStreamingSseSession(fallbackToolName: string) {
  return new StreamingSseSession(fallbackToolName)
}

// 用于保存 SSE buffer、cursor 和 StreamEvent reducer 状态。
class StreamingSseSession {
  private buffer = ''
  private pendingSseEventId: string | null = null
  private protocolState = createStreamProtocolState()
  private readonly fallbackToolName: string

  constructor(fallbackToolName: string) {
    this.fallbackToolName = fallbackToolName
  }

  // 用于推入网络 chunk 并返回已完成 data 帧的规约结果。
  pushChunk(chunk: string): StreamingSseReduction[] {
    this.buffer += chunk
    const lines = this.buffer.split('\n')
    this.buffer = lines.pop() || ''

    const reductions: StreamingSseReduction[] = []
    for (const line of lines) {
      const parsed = parseSseLine(line)
      if (parsed.type === 'id') {
        this.pendingSseEventId = parsed.value
        continue
      }
      if (parsed.type !== 'data') continue
      reductions.push(this.reduceData(parsed.value))
    }
    return reductions
  }

  // 用于返回当前 reducer 状态快照。
  state(): StreamProtocolState {
    return this.protocolState
  }

  private reduceData(data: Record<string, unknown>): StreamingSseReduction {
    const previousEvents = this.protocolState.events
    const nextCursor = resolveStreamCursor(data, this.pendingSseEventId)
    this.pendingSseEventId = null
    const reduced = reduceStreamSsePayload(
      this.protocolState,
      data,
      this.fallbackToolName,
    )
    this.protocolState = reduced.state
    return {
      ...reduced,
      data,
      previousEvents,
      nextCursor,
      protocolEvent: reduced.event,
    }
  }
}

// 用于解析单行 SSE 文本。
function parseSseLine(line: string): ParsedSseLine {
  if (line.startsWith('id: ')) {
    return { type: 'id', value: line.slice(4).trim() }
  }
  if (!line.startsWith('data: ')) return { type: 'ignore' }
  try {
    const parsed = JSON.parse(line.slice(6))
    if (parsed && typeof parsed === 'object') {
      return { type: 'data', value: parsed as Record<string, unknown> }
    }
  } catch {
    return { type: 'ignore' }
  }
  return { type: 'ignore' }
}
