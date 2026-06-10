// 用于提供 components/editor/UserInputRequestCard.tsx 模块。
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
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

  // 用于提交用户自己输入的答案。
  const submitCustomAnswer = () => {
    if (!trimmedCustomAnswer || disabled) return
    onSubmit(trimmedCustomAnswer)
    setCustomAnswer('')
    setCustomOpen(false)
  }

  return (
    <div
      className="mb-3 flex-shrink-0 overflow-hidden border bg-white text-sm shadow-sm"
      style={{
        borderRadius: '12px',
        borderColor: 'rgba(0,82,255,0.22)',
      }}
    >
      <div className="border-b border-blue-100 bg-blue-50 px-4 py-3">
        {request.context && (
          <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.04em] text-blue-600">
            {request.context}
          </div>
        )}
        <div className="font-semibold leading-5 text-gray-950">{request.question}</div>
      </div>
      <div className="space-y-2 px-4 py-3">
        {request.options.map((option) => (
          <button
            key={option}
            type="button"
            disabled={disabled}
            onClick={() => onSubmit(option)}
            className="block w-full border border-gray-200 bg-white px-3 py-2 text-left text-sm font-medium text-gray-900 transition-colors hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
            style={{ borderRadius: '10px' }}
          >
            {option}
          </button>
        ))}
        {request.allowCustom && (
          <div className="border-t border-gray-100 pt-2">
            {!customOpen ? (
              <button
                type="button"
                disabled={disabled}
                onClick={() => setCustomOpen(true)}
                className="block w-full border border-dashed border-gray-300 bg-gray-50 px-3 py-2 text-left text-sm font-medium text-gray-700 transition-colors hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
                style={{ borderRadius: '10px' }}
              >
                {t('userInputRequestCustom')}
              </button>
            ) : (
              <div className="space-y-2">
                <textarea
                  value={customAnswer}
                  disabled={disabled}
                  rows={3}
                  autoFocus
                  onChange={(event) => setCustomAnswer(event.target.value)}
                  className="w-full resize-none border border-gray-200 bg-white px-3 py-2 text-sm leading-5 text-gray-900 outline-none transition-colors placeholder:text-gray-400 focus:border-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                  style={{ borderRadius: '10px' }}
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={disabled || !trimmedCustomAnswer}
                    onClick={submitCustomAnswer}
                    className="flex-1 px-3 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                    style={{ borderRadius: '999px', backgroundColor: '#0052ff' }}
                  >
                    {t('userInputRequestSubmit')}
                  </button>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => setCustomOpen(false)}
                    className="flex-1 border border-gray-200 bg-white px-3 py-2 text-xs font-semibold text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                    style={{ borderRadius: '999px' }}
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
