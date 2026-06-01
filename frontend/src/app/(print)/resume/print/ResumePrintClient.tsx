'use client'
// 用于提供打印页客户端载荷读取和预览渲染。

import ResumePreview from '@/components/preview/ResumePreview'
import {
  buildModuleConfig,
  deserializeLayoutConfig,
} from '@/lib/resumeLayoutConfig'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'
import { useEffect, useState } from 'react'
import { isResumePrintReady, readPrintPayload } from './printPayload'
import type { PrintPayload } from './printPayload'

interface ResumePrintClientProps {
  data?: string
  invalidPrintDataText: string
  payloadKey?: string
}

// 用于标准化templatestyle。
function normalizeTemplateStyle(template?: string): ResumeTemplateStyle {
  return template === 'modern' || template === 'formal' || template === 'emerald' ? template : 'classic'
}

// 用于渲染 ResumePrintClient 组件。
export default function ResumePrintClient({
  data,
  invalidPrintDataText,
  payloadKey,
}: ResumePrintClientProps) {
  const [payload, setPayload] = useState<PrintPayload | null>(null)
  const [isReady, setIsReady] = useState(false)
  const [previewReady, setPreviewReady] = useState(false)

  useEffect(() => {
    setPreviewReady(false)
    setPayload(readPrintPayload(data, payloadKey))
    setIsReady(true)
  }, [data, payloadKey])

  const content = payload?.content
  const printReady = isResumePrintReady(payload, previewReady)
  const layoutConfig = deserializeLayoutConfig(payload?.layout_config)
  const templateStyle = normalizeTemplateStyle(
    payload?.template || layoutConfig.templateStyle,
  )
  const moduleOrder = buildModuleConfig(
    layoutConfig.moduleOrder,
    layoutConfig.visibleModules,
  )

  if (!isReady) {
    return <main className="bg-white" />
  }

  if (!content) {
    return (
      <main
        className="bg-white flex items-center justify-center text-gray-500"
        data-resume-print-error="missing-content"
      >
        <p>{invalidPrintDataText}</p>
      </main>
    )
  }

  return (
    <main
      className="bg-white"
      data-resume-print-ready={printReady ? 'true' : undefined}
    >
      <ResumePreview
        content={content}
        moduleOrder={moduleOrder}
        spacingScale={layoutConfig.spacingScale}
        templateStyle={templateStyle}
        onRenderReady={setPreviewReady}
      />
    </main>
  )
}
