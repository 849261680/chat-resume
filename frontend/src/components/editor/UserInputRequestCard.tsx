// 用于提供 components/editor/UserInputRequestCard.tsx 模块。
'use client'

import { useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import {
  ArrowRightIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  PencilSquareIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import type { UserInputRequest } from '@/hooks/useStreamingChat'

interface UserInputRequestCardProps {
  request: UserInputRequest
  onSubmit: (answer: string) => void
  disabled?: boolean
}

/** 用户信息询问卡片用于把 Agent 的追问转换成可点击选项和自定义输入。 */
export default function UserInputRequestCard({
  request,
  onSubmit,
  disabled = false,
}: UserInputRequestCardProps) {
  const t = useTranslations('resume.editor')
  const [customOpen, setCustomOpen] = useState(false)
  const [customAnswer, setCustomAnswer] = useState('')
  const customInputRef = useRef<HTMLInputElement>(null)
  const trimmedCustomAnswer = customAnswer.trim()
  const skipAnswer = t('userInputRequestSkip')

  // 用于跳过当前问题并把跳过意图交回 Agent。
  const skipQuestion = () => {
    if (disabled) return
    onSubmit(skipAnswer)
  }

  // 用于提交用户自己输入的答案。
  const submitCustomAnswer = () => {
    if (!trimmedCustomAnswer || disabled) return
    onSubmit(trimmedCustomAnswer)
    setCustomAnswer('')
    setCustomOpen(false)
  }

  // 用于在底部原位打开自定义输入并聚焦。
  const openCustomInput = () => {
    if (disabled) return
    setCustomOpen(true)
    requestAnimationFrame(() => customInputRef.current?.focus())
  }

  return (
    <div
      className="mb-3 flex-shrink-0 overflow-hidden border bg-white text-sm shadow-[0_14px_32px_rgba(15,23,42,0.07)]"
      style={{
        borderRadius: '22px',
        borderColor: 'rgba(17,24,39,0.1)',
      }}
    >
      <div className="flex items-start gap-3 px-5 pb-4 pt-5">
        <div className="min-w-0 flex-1">
          <div className="text-[15px] font-semibold leading-5 text-gray-950">{request.question}</div>
          {request.context && (
            <div className="mt-1 text-xs leading-5 text-gray-500">
              {request.context}
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1.5 text-gray-500">
          <button
            type="button"
            aria-label="Previous question"
            disabled
            className="flex h-7 w-7 items-center justify-center rounded-full text-gray-300 disabled:cursor-not-allowed"
          >
            <ChevronLeftIcon className="h-4 w-4" />
          </button>
          <span className="min-w-[48px] text-center text-xs font-medium text-gray-500">
            {t('userInputRequestProgress', { current: 1, total: 1 })}
          </span>
          <button
            type="button"
            aria-label="Next question"
            disabled
            className="flex h-7 w-7 items-center justify-center rounded-full text-gray-300 disabled:cursor-not-allowed"
          >
            <ChevronRightIcon className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label={skipAnswer}
            disabled={disabled}
            onClick={skipQuestion}
            className="flex h-7 w-7 items-center justify-center rounded-full text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <XMarkIcon className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div>
        {request.options.map((option, index) => (
          <button
            key={option}
            type="button"
            disabled={disabled}
            onClick={() => onSubmit(option)}
            className="group flex min-h-[58px] w-full items-center gap-4 border-t border-gray-200 px-5 text-left transition-colors hover:bg-gray-100 focus:bg-gray-100 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gray-100 text-[15px] font-medium text-gray-500 transition-colors group-hover:bg-gray-200 group-hover:text-gray-950">
              {index + 1}
            </span>
            <span className="min-w-0 flex-1 text-[15px] font-medium leading-5 text-gray-700 group-hover:text-gray-950">
              {option}
            </span>
            <ArrowRightIcon className="h-5 w-5 shrink-0 text-gray-400 opacity-0 transition-opacity group-hover:opacity-100 group-focus:opacity-100" />
          </button>
        ))}
        {request.allowCustom && (
          <div className={`border-t border-gray-200 px-5 py-3 ${customOpen ? 'bg-gray-100' : ''}`}>
            <div className="flex items-center gap-3">
              <div
                onClick={openCustomInput}
                className={`group flex min-h-[42px] min-w-0 flex-1 items-center gap-4 text-left text-[15px] font-medium text-gray-500 transition-colors hover:text-gray-950 ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-text'}`}
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gray-100 text-gray-600 transition-colors group-hover:bg-gray-200 group-hover:text-gray-950">
                  <PencilSquareIcon className="h-5 w-5" />
                </span>
                {customOpen ? (
                  <input
                    ref={customInputRef}
                    value={customAnswer}
                    disabled={disabled}
                    onChange={(event) => setCustomAnswer(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        submitCustomAnswer()
                      }
                      if (event.key === 'Escape') {
                        setCustomAnswer('')
                        setCustomOpen(false)
                      }
                    }}
                    placeholder={t('userInputRequestCustom')}
                    className="min-w-0 flex-1 bg-transparent text-[15px] font-medium text-gray-950 outline-none placeholder:text-gray-400"
                  />
                ) : (
                  <span className="truncate">{t('userInputRequestCustom')}</span>
                )}
              </div>
              {customOpen && (
                <button
                  type="button"
                  disabled={disabled || !trimmedCustomAnswer}
                  onClick={submitCustomAnswer}
                  className="shrink-0 rounded-xl bg-gray-950 px-4 py-2 text-sm font-semibold text-white transition-colors disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {t('userInputRequestSubmit')}
                </button>
              )}
              <button
                type="button"
                disabled={disabled}
                onClick={skipQuestion}
                className="shrink-0 rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-950 shadow-sm transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {skipAnswer}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
