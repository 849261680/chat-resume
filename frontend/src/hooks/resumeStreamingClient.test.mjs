// Tests the non-React Resume Agent streaming client session.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { registerHooks } from 'node:module'

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === '@/lib/httpClient') {
      return {
        shortCircuit: true,
        url: new URL('../lib/httpClient.ts', import.meta.url).href,
      }
    }
    if (specifier.endsWith('./streamingSseSession')) {
      return {
        shortCircuit: true,
        url: new URL('./streamingSseSession.ts', import.meta.url).href,
      }
    }
    if (specifier.endsWith('./streamingEventProtocol.ts')) {
      return {
        shortCircuit: true,
        url: new URL('./streamingEventProtocol.ts', import.meta.url).href,
      }
    }
    return nextResolve(specifier, context)
  },
})

const { ResumeStreamingClient } = await import('./resumeStreamingClient.ts')

// 用于构造带文本 SSE 内容的 fetch Response。
function streamResponse(text) {
  return {
    ok: true,
    status: 200,
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(text))
        controller.close()
      },
    }),
  }
}

test('streaming client parses SSE and replays once with Last-Event-ID', async () => {
  const requests = []
  const fetchImpl = async (_url, init) => {
    requests.push(init)
    if (requests.length === 1) {
      return streamResponse('id: sess_1:1\ndata: {"event_type":"text_delta","content":"先改"}\n')
    }
    return streamResponse('id: sess_1:2\ndata: {"done":true}\n')
  }
  const client = new ResumeStreamingClient({
    apiBaseUrl: 'https://api.example.com',
    fallbackToolName: 'Tool call',
    fetchImpl,
  })
  const events = []

  for await (const event of client.stream({
    message: '优化',
    resumeId: 7,
    chatHistory: [],
    visibleModules: ['summary'],
    agentType: 'resume',
    clientRequestId: 'ai_test',
  })) {
    events.push(event)
  }

  assert.equal(events[0].protocolEvent?.type, 'text')
  assert.equal(events[1].data.done, true)
  assert.equal(requests.length, 2)
  assert.equal(requests[1].headers['Last-Event-ID'], 'sess_1:1')
})

test('streaming client calls the default browser fetch with a window receiver', async () => {
  const originalFetch = globalThis.fetch
  const calls = []
  globalThis.fetch = async function fetchWithReceiverCheck(url, init) {
    if (this !== globalThis) {
      throw new TypeError('Illegal invocation')
    }
    calls.push({ url: String(url), init })
    return {
      ok: true,
      status: 200,
      async json() {
        return {
          session_id: 'sess_1',
          pending_action: {
            call_id: 'call_1',
            tool_name: '优化要点',
            diff_summary: 'diff',
            diff_items: [],
          },
        }
      },
    }
  }
  try {
    const client = new ResumeStreamingClient({
      apiBaseUrl: 'https://api.example.com',
      fallbackToolName: 'Tool call',
    })

    const pending = await client.restorePendingConfirmation(7)

    assert.equal(pending.sessionId, 'sess_1')
    assert.equal(calls.length, 1)
    assert.equal(calls[0].url, 'https://api.example.com/api/ai/chat/pending-confirmation?resume_id=7')
  } finally {
    globalThis.fetch = originalFetch
  }
})
