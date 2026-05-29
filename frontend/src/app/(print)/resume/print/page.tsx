// 用于提供 app/(print)/resume/print/page.tsx 模块。
import ResumePreview from '@/components/preview/ResumePreview'
import {
  buildModuleConfig,
  deserializeLayoutConfig,
} from '@/lib/resumeLayoutConfig'
import type { ResumeContent } from '@/types/resume'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'
import { getTranslations } from 'next-intl/server'

export const dynamic = 'force-dynamic'

interface PageProps {
  searchParams?: Promise<{
    data?: string
  }>
}

// 用于解码载荷。
function decodePayload(data?: string) {
  if (!data) {
    return null
  }

  try {
    const json = Buffer.from(data, 'base64url').toString('utf-8')
    return JSON.parse(json) as {
      content?: ResumeContent
      layout_config?: Record<string, unknown> | null
      template?: string
    }
  } catch {
    return null
  }
}

// 用于标准化templatestyle。
function normalizeTemplateStyle(template?: string): ResumeTemplateStyle {
  return template === 'modern' || template === 'formal' || template === 'emerald' ? template : 'classic'
}

// 用于渲染 ResumePrintPage 组件。
export default async function ResumePrintPage({ searchParams }: PageProps) {
  const t = await getTranslations({ locale: 'zh', namespace: 'resume.preview' })
  const resolvedSearchParams = await searchParams
  const payload = decodePayload(resolvedSearchParams?.data)
  const content = payload?.content
  const layoutConfig = deserializeLayoutConfig(payload?.layout_config)
  const templateStyle = normalizeTemplateStyle(
    payload?.template || layoutConfig.templateStyle,
  )
  const moduleOrder = buildModuleConfig(
    layoutConfig.moduleOrder,
    layoutConfig.visibleModules,
  )

  if (!content) {
    return (
      <main className="bg-white flex items-center justify-center text-gray-500">
        <p>{t('invalidPrintData')}</p>
      </main>
    )
  }

  return (
    <main className="bg-white">
      <ResumePreview
        content={content}
        moduleOrder={moduleOrder}
        spacingScale={layoutConfig.spacingScale}
        templateStyle={templateStyle}
      />
    </main>
  )
}
