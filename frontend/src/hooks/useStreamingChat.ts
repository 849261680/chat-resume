import { useState, useRef } from 'react'

interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
}

interface StreamingChatOptions {
  onMessage?: (message: ChatMessage) => void
  onError?: (error: string) => void
  apiBaseUrl?: string
}

export function useStreamingChat(resumeId: number, options: StreamingChatOptions = {}) {
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('')
  const abortControllerRef = useRef<AbortController | null>(null)
  
  const {
    onMessage,
    onError,
    apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  } = options

  const sendStreamingMessage = async (message: string, chatHistory: ChatMessage[] = []) => {
    if (isStreaming) return

    setIsStreaming(true)
    setCurrentStreamingMessage('')
    
    // 创建中止控制器
    abortControllerRef.current = new AbortController()
    
    try {
      // 获取认证token
      const token = localStorage.getItem('access_token')
      if (!token) {
        throw new Error('未找到认证token，请重新登录')
      }

      const response = await fetch(`${apiBaseUrl}/api/v1/ai/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          message,
          resume_id: resumeId,
          chat_history: chatHistory
        }),
        signal: abortControllerRef.current.signal
      })

      if (!response.ok) {
        if (response.status === 401) {
          // 处理认证失败
          localStorage.removeItem('access_token')
          localStorage.removeItem('user')
          throw new Error('认证已过期，请重新登录')
        }
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      if (!response.body) {
        throw new Error('Response body is null')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamingContent = ''

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
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                
                if (data.error) {
                  onError?.(data.error)
                  return
                }
                
                if (data.done) {
                  // 流式传输完成，创建完整的AI消息
                  const aiMessage: ChatMessage = {
                    id: Date.now().toString(),
                    type: 'ai',
                    content: streamingContent,
                    timestamp: new Date()
                  }
                  onMessage?.(aiMessage)
                  setCurrentStreamingMessage('')
                  return
                }
                
                if (data.content) {
                  streamingContent += data.content
                  setCurrentStreamingMessage(streamingContent)
                }
              } catch (error) {
                console.warn('Failed to parse SSE data:', line)
              }
            }
          }
        }
      } finally {
        reader.releaseLock()
      }
      
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Streaming aborted')
      } else {
        console.error('Streaming error:', error)
        const errorMessage = error instanceof Error ? error.message : 'Unknown streaming error'
        onError?.(errorMessage)
      }
    } finally {
      setIsStreaming(false)
      setCurrentStreamingMessage('')
      abortControllerRef.current = null
    }
  }

  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }

  return {
    isStreaming,
    currentStreamingMessage,
    sendStreamingMessage,
    stopStreaming
  }
}