// 用于提供 i18n/routing.ts 模块。
import { defineRouting } from 'next-intl/routing'

const locales = ['zh', 'en'] as const
export type AppLocale = (typeof locales)[number]

const defaultLocale: AppLocale = 'zh'
export const localeCookieName = 'NEXT_LOCALE'

// Central locale routing contract for UI routes and proxy negotiation.
export const routing = defineRouting({
  locales,
  defaultLocale,
  localePrefix: 'always',
  localeDetection: true,
})

// 用于判断应用语言环境。
export function isAppLocale(value: string | undefined): value is AppLocale {
  return locales.includes(value as AppLocale)
}

// 用于转换面试语言。
export function toInterviewLanguage(locale: AppLocale): 'zh-CN' | 'en-US' {
  return locale === 'zh' ? 'zh-CN' : 'en-US'
}
