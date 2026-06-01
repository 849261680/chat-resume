// 用于提供 app/(print)/resume/print/page.tsx 模块。
import { getTranslations } from 'next-intl/server'
import ResumePrintClient from './ResumePrintClient'

export const dynamic = 'force-dynamic'

interface PageProps {
  searchParams?: Promise<{
    data?: string
    payloadKey?: string
  }>
}

// 用于渲染 ResumePrintPage 组件。
export default async function ResumePrintPage({ searchParams }: PageProps) {
  const t = await getTranslations({ locale: 'zh', namespace: 'resume.preview' })
  const resolvedSearchParams = await searchParams

  return (
    <ResumePrintClient
      data={resolvedSearchParams?.data}
      invalidPrintDataText={t('invalidPrintData')}
      payloadKey={resolvedSearchParams?.payloadKey}
    />
  )
}
