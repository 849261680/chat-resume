// 用于提供 components/editor/UserInputRequestCard.tsx 模块。
'use client'

import { useState } from 'react'
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

  return (
    <div
      className="mb-3 flex-shrink-0 overflow-hidden border bg-white text-sm shadow-[0_18px_45px_rgba(15,23,42,0.08)]"
      style={{
        borderRadius: '22px',
        borderColor: 'rgba(17,24,39,0.1)',
      }}
    >
      <div className="flex items-start gap-3 px-6 pb-4 pt-5">
        <div className="min-w-0 flex-1">
          <div className="text-[17px] font-semibold leading-6 text-gray-950">{request.question}</div>
          {request.context && (
            <div className="mt-1 text-xs leading-5 text-gray-500">
              {request.context}
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2 text-gray-500">
          <button
            type="button"
            aria-label="Previous question"
            disabled
            className="flex h-8 w-8 items-center justify-center rounded-full text-gray-300 disabled:cursor-not-allowed"
          >
            <ChevronLeftIcon className="h-5 w-5" />
          </button>
          <span className="min-w-[54px] text-center text-sm font-medium text-gray-500">
            {t('userInputRequestProgress', { current: 1, total: 1 })}
          </span>
          <button
            type="button"
            aria-label="Next question"
            disabled
            className="flex h-8 w-8 items-center justify-center rounded-full text-gray-300 disabled:cursor-not-allowed"
          >
            <ChevronRightIcon className="h-5 w-5" />
          </button>
          <button
            type="button"
            aria-label={skipAnswer}
            disabled={disabled}
            onClick={skipQuestion}
            className="flex h-8 w-8 items-center justify-center rounded-full text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <XMarkIcon className="h-5 w-5" />
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
            className="group flex min-h-[76px] w-full items-center gap-5 border-t border-gray-200 px-6 text-left transition-colors hover:bg-gray-100 focus:bg-gray-100 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gray-100 text-[19px] font-medium text-gray-500 transition-colors group-hover:bg-gray-200 group-hover:text-gray-950">
              {index + 1}
            </span>
            <span className="min-w-0 flex-1 text-[17px] font-medium leading-6 text-gray-700 group-hover:text-gray-950">
              {option}
            </span>
            <ArrowRightIcon className="h-6 w-6 shrink-0 text-gray-400 opacity-0 transition-opacity group-hover:opacity-100 group-focus:opacity-100" />
          </button>
        ))}
        {request.allowCustom && (
          <div className="border-t border-gray-200 px-6 py-4">
            {!customOpen ? (
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => setCustomOpen(true)}
                  className="group flex min-h-[48px] min-w-0 flex-1 items-center gap-4 text-left text-[17px] font-medium text-gray-500 transition-colors hover:text-gray-950 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gray-100 text-gray-600 transition-colors group-hover:bg-gray-200 group-hover:text-gray-950">
                    <PencilSquareIcon className="h-6 w-6" />
                  </span>
                  <span className="truncate">{t('userInputRequestCustom')}</span>
                </button>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={skipQuestion}
                  className="shrink-0 rounded-xl border border-gray-200 bg-white px-5 py-2.5 text-base font-semibold text-gray-950 shadow-sm transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {skipAnswer}
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <textarea
                  value={customAnswer}
                  disabled={disabled}
                  rows={3}
                  autoFocus
                  onChange={(event) => setCustomAnswer(event.target.value)}
                  className="w-full resize-none border border-gray-200 bg-white px-4 py-3 text-sm leading-5 text-gray-900 outline-none transition-colors placeholder:text-gray-400 focus:border-gray-400 disabled:cursor-not-allowed disabled:opacity-50"
                  style={{ borderRadius: '14px' }}
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={disabled || !trimmedCustomAnswer}
                    onClick={submitCustomAnswer}
                    className="flex-1 rounded-xl bg-gray-950 px-3 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {t('userInputRequestSubmit')}
                  </button>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => setCustomOpen(false)}
                    className="flex-1 rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm font-semibold text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {t('cancel')}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
