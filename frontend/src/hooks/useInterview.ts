import { useState, useRef } from 'react'

interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
}

interface InterviewSession {
  id: string
  resumeId: number
  status: 'active' | 'completed' | 'paused'
  startTime: Date
  questions: string[]
  answers: string[]
}

interface InterviewHookOptions {
  onMessage?: (message: ChatMessage) => void
  onError?: (error: string) => void
  apiBaseUrl?: string
  chatHistory?: ChatMessage[]
}

export function useInterview(resumeId: number, options: InterviewHookOptions = {}) {
  const [isInterviewActive, setIsInterviewActive] = useState(false)
  const [currentSession, setCurrentSession] = useState<InterviewSession | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('')
  const abortControllerRef = useRef<AbortController | null>(null)
  
  const {
    onMessage,
    onError,
    apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    chatHistory = []
  } = options

  // 开始面试会话
  const startInterview = async (jdContent?: string) => {
    if (isInterviewActive) return null

    setIsLoading(true)
    
    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        throw new Error('未找到认证token，请重新登录')
      }

      // 创建本地面试会话
      const session: InterviewSession = {
        id: Date.now().toString(),
        resumeId,
        status: 'active',
        startTime: new Date(),
        questions: [],
        answers: []
      }

      setCurrentSession(session)
      setIsInterviewActive(true)
      
      // 调用AI获取面试开场白
      try {
        const response = await fetch(`${apiBaseUrl}/api/v1/ai/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            message: "请开始面试，先打个招呼并提出第一个问题。",
            resume_id: resumeId,
            chat_history: chatHistory,
            is_interview: true
          })
        })

        if (response.ok && response.body) {
          const reader = response.body.getReader()
          const decoder = new TextDecoder()
          let buffer = ''
          let streamingContent = ''

          try {
            while (true) {
              const { done, value } = await reader.read()
              if (done) break

              buffer += decoder.decode(value, { stream: true })
              const lines = buffer.split('\n')
              buffer = lines.pop() || ''
              
              for (const line of lines) {
                if (line.startsWith('data: ')) {
                  try {
                    const data = JSON.parse(line.slice(6))
                    if (data.content) {
                      streamingContent += data.content
                    }
                    if (data.done) {
                      const welcomeMessage: ChatMessage = {
                        id: Date.now().toString(),
                        type: 'ai',
                        content: streamingContent,
                        timestamp: new Date()
                      }
                      onMessage?.(welcomeMessage)
                      break
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
        }
      } catch (error) {
        console.error('Failed to get welcome message:', error)
        // 失败时使用默认欢迎消息
        const welcomeMessage: ChatMessage = {
          id: Date.now().toString(),
          type: 'ai',
          content: `您好！我是您的AI面试官。今天我将基于您的简历进行模拟面试。请先做一个简单的自我介绍，包括您的姓名、职位和主要工作经验。`,
          timestamp: new Date()
        }
        onMessage?.(welcomeMessage)
      }
      
      return session
    } catch (error) {
      console.error('Start interview error:', error)
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      onError?.(errorMessage)
      return null
    } finally {
      setIsLoading(false)
    }
  }

  // 发送面试答案并获取下一个问题
  const sendAnswer = async (answer: string) => {
    if (!currentSession || !isInterviewActive) return

    setIsLoading(true)
    abortControllerRef.current = new AbortController()
    
    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        throw new Error('未找到认证token，请重新登录')
      }

      // 发送用户答案消息
      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        type: 'user',
        content: answer,
        timestamp: new Date()
      }
      onMessage?.(userMessage)

      // 调用流式面试API
      const requestBody = {
        message: answer,
        resume_id: resumeId,
        chat_history: chatHistory,
        is_interview: true
      }
      console.log('面试API请求:', requestBody)
      
      const response = await fetch(`${apiBaseUrl}/api/v1/ai/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(requestBody),
        signal: abortControllerRef.current.signal
      })

      if (!response.ok) {
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

          buffer += decoder.decode(value, { stream: true })
          
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                
                if (data.error) {
                  onError?.(data.error)
                  return
                }
                
                if (data.done) {
                  const aiMessage: ChatMessage = {
                    id: Date.now().toString(),
                    type: 'ai',
                    content: streamingContent,
                    timestamp: new Date()
                  }
                  onMessage?.(aiMessage)
                  setCurrentStreamingMessage('')
                  
                  // 更新会话状态
                  setCurrentSession(prev => prev ? {
                    ...prev,
                    answers: [...prev.answers, answer]
                  } : null)
                  
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
        console.log('Request aborted')
      } else {
        console.error('Send answer error:', error)
        const errorMessage = error instanceof Error ? error.message : 'Unknown error'
        onError?.(errorMessage)
      }
    } finally {
      setIsLoading(false)
      setCurrentStreamingMessage('')
      abortControllerRef.current = null
    }
  }

  // 结束面试
  const endInterview = async () => {
    if (!currentSession) return

    try {
      setIsInterviewActive(false)
      
      // 这里可以调用后端API保存面试结果
      // await saveInterviewResults(currentSession)
      
      const endMessage: ChatMessage = {
        id: Date.now().toString(),
        type: 'ai',
        content: `面试结束！感谢您的参与。\n\n**面试问题数**: ${currentSession.answers.length}\n**面试时长**: ${Math.floor((Date.now() - currentSession.startTime.getTime()) / 1000 / 60)} 分钟\n\n您可以回到简历编辑页面继续优化简历，或查看面试反馈报告。`,
        timestamp: new Date()
      }
      
      onMessage?.(endMessage)
      setCurrentSession(null)
      
    } catch (error) {
      console.error('End interview error:', error)
      onError?.('结束面试时出现错误')
    }
  }

  // 停止当前请求
  const stopCurrentRequest = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }

  return {
    isInterviewActive,
    currentSession,
    isLoading,
    currentStreamingMessage,
    startInterview,
    sendAnswer,
    endInterview,
    stopCurrentRequest
  }
}