// 用于提供 i18n/navigation.ts 模块。
import { createNavigation } from 'next-intl/navigation'
import { routing } from './routing'

export const { Link, usePathname, useRouter } =
  createNavigation(routing)
