'use client'
// 用于提供 components/auth/GoogleContinueLink.tsx 模块。

import { useTranslations } from 'next-intl'
import { apiUrl } from '@/lib/httpClient'

// 用于获取Google登录地址。
function getGoogleLoginUrl() {
  return apiUrl('/api/auth/google/login')
}

// 用于渲染 GoogleContinueLink 组件。
export default function GoogleContinueLink() {
  const t = useTranslations('auth.oauth')

  return (
    <a
      href={getGoogleLoginUrl()}
      aria-label={t('google')}
      className="flex h-12 w-full items-center justify-center gap-3 rounded-full border text-base font-semibold transition-colors hover:bg-gray-50"
      style={{ borderColor: 'rgba(91,97,110,0.28)', color: '#0a0b0d' }}
    >
      <span
        aria-hidden="true"
        className="flex h-6 w-6 items-center justify-center rounded-full text-sm font-bold"
        style={{ border: '1px solid rgba(91,97,110,0.28)' }}
      >
        <svg className="h-4 w-4" viewBox="0 0 18 18" role="img">
          <path
            fill="#4285F4"
            d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"
          />
          <path
            fill="#34A853"
            d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.83.86-3.04.86-2.34 0-4.33-1.58-5.04-3.7H.94v2.34A9 9 0 0 0 9 18z"
          />
          <path
            fill="#FBBC05"
            d="M3.96 10.72A5.41 5.41 0 0 1 3.68 9c0-.6.1-1.18.28-1.72V4.94H.94A9 9 0 0 0 0 9c0 1.45.34 2.82.94 4.06l3.02-2.34z"
          />
          <path
            fill="#EA4335"
            d="M9 3.58c1.32 0 2.5.46 3.44 1.34l2.58-2.58C13.46.88 11.43 0 9 0A9 9 0 0 0 .94 4.94l3.02 2.34C4.67 5.16 6.66 3.58 9 3.58z"
          />
        </svg>
      </span>
      <span>{t('google')}</span>
    </a>
  )
}
