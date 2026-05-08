/**
 * 简历 Agent 聊天面板 Hook
 *
 * 用于集中管理聊天历史、流式消息、滚动行为和清空逻辑。
 */

'use client'

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'

import { chatHistoryApi } from '@/lib/api'
import { ChatMessage, StreamEvent, useStreamingChat } from '@/hooks/useStreamingChat'

interface UseResumeChatPanelOptions {
  resumeId: string
  visibleModules: string[]
  performAutoSave: () => Promise<void> | Promise<undefined> | undefined
  onResumeUpdate: (content: Record<string, unknown>) => void
  enabled: boolean
}

/**
 * 提供简历 Agent 面板需要的消息状态、滚动控制和交互方法。
 */
export function useResumeChatPanel({
  resumeId,
  visibleModules,
  performAutoSave,
  onResumeUpdate,
  enabled,
}: UseResumeChatPanelOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isClearingMessages, setIsClearingMessages] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const shouldStickToBottomRef = useRef(true)
  const previousMessageCountRef = useRef(0)

  /**
   * 向当前消息列表追加一条新消息，统一处理本地更新。
   */
  const appendMessage = useCallback((message: ChatMessage) => {
    setMessages((previousMessages) => [...previousMessages, message])
  }, [])

  /**
   * 用完整消息数组替换当前历史，供历史加载和清空复用。
   */
  const replaceMessages = useCallback((nextMessages: ChatMessage[]) => {
    setMessages(nextMessages)
  }, [])

  const {
    isStreaming,
    currentStreamingMessage,
    streamEvents,
    sendStreamingMessage,
    stopStreaming,
    confirmTool,
  } = useStreamingChat(parseInt(resumeId || '0', 10), {
    visibleModules,
    agentType: 'resume',
    onMessage: (message) => {
      appendMessage(message)
      if (resumeId) {
        void chatHistoryApi.appendMessages(parseInt(resumeId, 10), [
          {
            role: 'assistant',
            content: message.content,
            stream_events: message.streamEvents || null,
          },
        ])
      }
    },
    onError: (error) => {
      setApiError(error)
      appendMessage({
        id: Date.now().toString(),
        type: 'ai',
        content: `抱歉，发生了错误：${error}`,
        timestamp: new Date(),
      })
    },
    onResumeUpdate,
  })

  /**
   * 加载已保存的聊天历史，保证刷新页面后还能看到上下文。
   */
  const loadChatHistory = useCallback(async () => {
    if (!resumeId || !enabled) return
    try {
      const records = await chatHistoryApi.getMessages(parseInt(resumeId, 10))
      if (records.length > 0) {
        replaceMessages(records.map((record) => ({
          id: record.id.toString(),
          type: record.role === 'user' ? 'user' : 'ai',
          content: record.content,
          timestamp: new Date(),
          streamEvents: (record as { stream_events?: StreamEvent[] }).stream_events || undefined,
        })))
      }
    } catch (error) {
      console.error('Failed to load chat history:', error)
    }
  }, [enabled, replaceMessages, resumeId])

  /**
   * 当消息区域被用户滚离底部时，记录当前粘底状态，避免打断阅读。
   */
  const updateStickToBottom = useCallback(() => {
    const container = messagesContainerRef.current
    if (!container) return
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    shouldStickToBottomRef.current = distanceFromBottom <= 48
  }, [])

  /**
   * 把消息区域滚动到底部，供新消息和流式更新复用。
   */
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'auto') => {
    const container = messagesContainerRef.current
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior })
      return
    }
    messagesEndRef.current?.scrollIntoView({ behavior })
  }, [])

  /**
   * 处理消息区滚动事件，实时更新是否应自动贴底。
   */
  const handleMessagesScroll = useCallback(() => {
    updateStickToBottom()
  }, [updateStickToBottom])

  /**
   * 切换面板或首次进入时重新计算粘底状态。
   */
  useEffect(() => {
    updateStickToBottom()
  }, [enabled, updateStickToBottom])

  /**
   * 当消息列表或流式内容变化时，按当前粘底策略自动滚动。
   */
  useLayoutEffect(() => {
    const hasNewMessage = messages.length > previousMessageCountRef.current
    previousMessageCountRef.current = messages.length

    if (!shouldStickToBottomRef.current && !hasNewMessage) {
      return
    }
    const behavior: ScrollBehavior = isStreaming ? 'auto' : (hasNewMessage ? 'smooth' : 'auto')
    scrollToBottom(behavior)
  }, [currentStreamingMessage, isStreaming, messages.length, scrollToBottom])

  /**
   * 仅用于同步上一轮消息数量，辅助判断是否出现新消息。
   */
  useEffect(() => {
    previousMessageCountRef.current = messages.length
  }, [messages.length])

  /**
   * 在启用简历 Agent 面板后自动加载聊天历史。
   */
  useEffect(() => {
    if (!enabled) return
    void loadChatHistory()
  }, [enabled, loadChatHistory])

  /**
   * 发送一条指定消息，并在发送前确保当前简历草稿已保存。
   */
  const dispatchMessage = useCallback(async (messageContent: string, clearInput = false) => {
    const trimmedMessage = messageContent.trim()
    if (!trimmedMessage || isSending || isStreaming) return

    try {
      await performAutoSave()
    } catch {
      setApiError('简历保存失败，未发送给 Agent')
      return
    }

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: trimmedMessage,
      timestamp: new Date(),
    }
    appendMessage(userMessage)
    if (resumeId) {
      void chatHistoryApi.appendMessages(parseInt(resumeId, 10), [
        { role: 'user', content: userMessage.content },
      ])
    }

    if (clearInput) {
      setInputMessage('')
    }
    setIsSending(true)
    setApiError(null)
    try {
      await sendStreamingMessage(trimmedMessage, messages)
    } catch (error) {
      setApiError('流式聊天发送失败，请重试')
    } finally {
      setIsSending(false)
    }
  }, [appendMessage, isSending, isStreaming, messages, performAutoSave, resumeId, sendStreamingMessage])

  /**
   * 发送输入框中的消息，并在成功提交后清空输入框。
   */
  const sendMessage = useCallback(async () => {
    await dispatchMessage(inputMessage, true)
  }, [dispatchMessage, inputMessage])

  /**
   * 发送一条预设快捷消息，避免按钮动作覆盖用户手写草稿。
   */
  const sendPresetMessage = useCallback(async (messageContent: string) => {
    await dispatchMessage(messageContent)
  }, [dispatchMessage])

  /**
   * 主动结束当前 Agent 流式对话。
   */
  const endConversation = useCallback(() => {
    if (!isSending && !isStreaming) return
    stopStreaming()
    setIsSending(false)
    setApiError(null)
  }, [isSending, isStreaming, stopStreaming])

  /**
   * 清空当前聊天历史，并同步删除服务端已保存的消息。
   */
  const handleClearMessages = useCallback(async () => {
    if (!resumeId || isStreaming || isSending || isClearingMessages || messages.length === 0) return
    if (!window.confirm('确定清空当前聊天记录吗？此操作不可恢复。')) return

    try {
      setIsClearingMessages(true)
      await chatHistoryApi.clearMessages(parseInt(resumeId, 10))
      replaceMessages([])
      setApiError(null)
      toast.success('已清空消息记录')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '清空消息失败')
    } finally {
      setIsClearingMessages(false)
    }
  }, [isClearingMessages, isSending, isStreaming, messages.length, replaceMessages, resumeId])

  /**
   * 支持 Enter 直接发送，Shift+Enter 保留换行。
   */
  const handleKeyPress = useCallback((event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void sendMessage()
    }
  }, [sendMessage])

  return {
    messages,
    inputMessage,
    setInputMessage,
    isSending,
    isClearingMessages,
    apiError,
    setApiError,
    messagesEndRef,
    messagesContainerRef,
    isStreaming,
    currentStreamingMessage,
    streamEvents,
    confirmTool,
    handleMessagesScroll,
    handleClearMessages,
    handleKeyPress,
    endConversation,
    sendMessage,
    sendPresetMessage,
  }
}
