/**
 * 聊天输入框组件
 *
 * 用于隔离 inputMessage 状态，避免每次击键触发 ResumeEditPage 整体重渲染。
 * inputMessage 管在组件内部，只在发送时通知父组件。
 */

'use client'

import React, { forwardRef, useCallback, useImperativeHandle, useLayoutEffect, useRef, useState } from 'react'
import { ArrowUpIcon, StopIcon } from '@heroicons/react/24/outline'

export interface ChatInputBoxHandle {
  /** 把选中的简历文本追加到本地引用 chip 中 */
  appendSelectedContext: (text: string) => void
}

interface ChatInputBoxProps {
  /** 发送消息 */
  onSend: (message: string) => void
  /** 停止流式输出 */
  onStop: () => void
  /** 是否正在发送 */
  isSending: boolean
  /** 是否正在流式输出 */
  isStreaming: boolean
  /** 输入框占位文字 */
  placeholder: string
}

// 用于渲染聊天输入框，将 inputMessage 状态隔离在组件内部。
const ChatInputBox = React.memo(forwardRef<ChatInputBoxHandle, ChatInputBoxProps>(function ChatInputBox({
  onSend,
  onStop,
  isSending,
  isStreaming,
  placeholder,
}, ref) {
  const [inputMessage, setInputMessage] = useState('')
  const [selectedResumeContext, setSelectedResumeContext] = useState('')
  const chatInputRef = useRef<HTMLTextAreaElement>(null)

  // textarea 按内容自动增高
  useLayoutEffect(() => {
    const input = chatInputRef.current
    if (!input) return
    input.style.height = 'auto'
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`
    input.style.overflowY = input.scrollHeight > 160 ? 'auto' : 'hidden'
  }, [inputMessage])

  const hasContent = Boolean(inputMessage.trim() || selectedResumeContext.trim())

  useImperativeHandle(ref, () => ({
    appendSelectedContext: (text: string) => {
      const selectedText = text.trim()
      if (!selectedText) return
      setSelectedResumeContext((currentContext) => (
        currentContext.trim()
          ? `${currentContext.trimEnd()}\n\n${selectedText}`
          : selectedText
      ))
      window.requestAnimationFrame(() => {
        chatInputRef.current?.focus()
      })
    },
  }), [])

  // 发送当前输入内容，并在引用被发送后清理引用状态。
  const sendCurrentMessage = useCallback(() => {
    const selectedContext = selectedResumeContext.trim()
    const userRequest = inputMessage.trim()
    if ((!selectedContext && !userRequest) || isSending || isStreaming) return
    const message = selectedContext
      ? `选中的简历内容：\n${selectedResumeContext}\n\n用户要求：\n${userRequest}`
      : userRequest
    onSend(message)
    setInputMessage('')
    if (selectedContext) setSelectedResumeContext('')
  }, [inputMessage, selectedResumeContext, onSend, isSending, isStreaming])

  const handleKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (event.key === 'Backspace' && selectedResumeContext && inputMessage.length === 0) {
      event.preventDefault()
      setSelectedResumeContext('')
      return
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendCurrentMessage()
    }
  }, [inputMessage, selectedResumeContext, sendCurrentMessage])

  return (
    <div className="pt-3 flex-shrink-0">
      <div
        data-testid="resume-chat-input-box"
        className="relative min-h-[66px] px-3 py-2 pr-12"
        style={{
          border: '1px solid rgba(91,97,110,0.25)',
          borderRadius: '12px',
        }}
      >
        <div className="flex min-h-[48px] flex-wrap items-start gap-1.5">
          {selectedResumeContext && (
            <span
              data-testid="selected-resume-context"
              className="max-w-full whitespace-pre-wrap break-words rounded-[5px] px-1.5 py-0.5 text-sm leading-snug"
              style={{
                backgroundColor: 'rgba(0,82,255,0.08)',
                color: '#0667d0',
              }}
            >
              {selectedResumeContext}
            </span>
          )}
          <textarea
            ref={chatInputRef}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="min-h-[32px] min-w-[160px] flex-1 resize-none bg-transparent p-1 text-sm focus:outline-none"
            style={{
              color: '#0a0b0d',
              overflowY: 'hidden',
            }}
            rows={1}
            disabled={isSending || isStreaming}
          />
        </div>
        <button
          type="button"
          aria-label={isStreaming ? '停止 Agent' : '发送消息'}
          onClick={isStreaming ? onStop : sendCurrentMessage}
          disabled={!isStreaming && (!hasContent || isSending)}
          className="absolute right-3 bottom-3 w-9 h-9 rounded-full transition-colors flex items-center justify-center disabled:cursor-not-allowed"
          style={{
            backgroundColor: isStreaming
              ? '#eef0f3'
              : (hasContent ? '#0052ff' : '#eef0f3'),
            color: isStreaming
              ? '#111827'
              : (hasContent ? '#ffffff' : '#9ca3af'),
          }}
        >
          {isStreaming ? (
            <StopIcon className="w-4 h-4" />
          ) : (
            <ArrowUpIcon className="w-4 h-4" />
          )}
        </button>
      </div>
    </div>
  )
}))

export default ChatInputBox
