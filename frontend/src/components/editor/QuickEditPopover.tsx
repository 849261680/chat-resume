'use client'
// 用于提供简历快速编辑浮层，避免输入时重渲染整个编辑页。

import { ArrowUpIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { useCallback, useEffect, useRef } from 'react'

interface QuickEditPopoverProps {
  selectedText: string
  top: number
  left: number
  disabled?: boolean
  onClose: () => void
  onSubmit: (selectedText: string, prompt: string) => void
}

// 用于渲染只在本组件内更新输入状态的快速编辑浮层。
export default function QuickEditPopover({
  selectedText,
  top,
  left,
  disabled = false,
  onClose,
  onSubmit,
}: QuickEditPopoverProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const submitButtonRef = useRef<HTMLButtonElement>(null)

  // 用于同步非受控输入对应的提交按钮状态。
  const syncSubmitButton = useCallback(() => {
    const button = submitButtonRef.current
    if (!button) return
    const hasPrompt = Boolean(textareaRef.current?.value.trim())
    button.disabled = !hasPrompt || disabled
    button.style.backgroundColor = hasPrompt && !disabled ? '#0052ff' : '#eef0f3'
    button.style.color = hasPrompt && !disabled ? '#ffffff' : '#9ca3af'
  }, [disabled])

  useEffect(() => {
    window.requestAnimationFrame(() => {
      textareaRef.current?.focus()
      syncSubmitButton()
    })
  }, [syncSubmitButton])

  useEffect(() => {
    syncSubmitButton()
  }, [syncSubmitButton])

  // 用于读取非受控 textarea 当前输入并提交给父组件。
  const submitCurrentPrompt = useCallback(() => {
    const prompt = textareaRef.current?.value.trim() ?? ''
    if (!prompt || disabled) return
    onSubmit(selectedText, prompt)
  }, [disabled, onSubmit, selectedText])

  return (
    <div
      data-resume-selection-action="true"
      className="absolute z-30 w-[min(360px,calc(100%-16px))] rounded-lg border bg-white px-2 py-1 shadow-lg print:hidden"
      style={{
        top,
        left,
        borderColor: 'rgba(91,97,110,0.25)',
      }}
      onMouseUp={(event) => event.stopPropagation()}
      onKeyUp={(event) => event.stopPropagation()}
      onPointerDown={(event) => event.stopPropagation()}
    >
      <button
        type="button"
        aria-label="关闭快速优化"
        className="absolute right-2 top-1.5 inline-flex h-6 w-6 items-center justify-center rounded-full text-gray-400 transition-colors hover:text-gray-600"
        onPointerDown={(event) => {
          event.preventDefault()
          event.stopPropagation()
          onClose()
        }}
        onClick={onClose}
      >
        <XMarkIcon className="h-4 w-4" />
      </button>
      <textarea
        ref={textareaRef}
        defaultValue=""
        onInput={syncSubmitButton}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            submitCurrentPrompt()
          }
        }}
        placeholder="输入优化要求"
        rows={1}
        className="min-h-[30px] w-full resize-none bg-transparent py-1 pl-1 pr-8 text-sm leading-relaxed text-[#0a0b0d] placeholder:text-gray-400 focus:outline-none"
      />
      <div className="-mt-1 flex items-center justify-end">
        <button
          ref={submitButtonRef}
          type="button"
          aria-label="发送快速优化"
          disabled
          className="inline-flex h-6 w-6 items-center justify-center rounded-full transition-colors disabled:cursor-not-allowed"
          style={{
            backgroundColor: '#eef0f3',
            color: '#9ca3af',
          }}
          onClick={submitCurrentPrompt}
        >
          <ArrowUpIcon className="h-3 w-3" />
        </button>
      </div>
    </div>
  )
}
