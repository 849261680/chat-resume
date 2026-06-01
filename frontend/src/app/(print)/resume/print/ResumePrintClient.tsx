'use client'
// 用于提供打印页客户端载荷读取和预览渲染。

import ResumePreview from '@/components/preview/ResumePreview'
import {
  buildModuleConfig,
  deserializeLayoutConfig,
} from '@/lib/resumeLayoutConfig'
import type { ResumeContent } from '@/types/resume'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'
import { useEffect, useState } from 'react'

interface PrintPayload {
  content?: ResumeContent
  layout_config?: Record<string, unknown> | null
  template?: string
}

interface ResumePrintClientProps {
  data?: string
  invalidPrintDataText: string
  payloadKey?: string
}

// 用于把 base64url 字符串解码成 UTF-8 JSON 字符串。
function decodeBase64Url(data: string): string {
  const normalized = data.replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
  const binary = window.atob(padded)
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0))
  return new TextDecoder().decode(bytes)
}

// 用于解码打印页载荷。
function decodePayload(data?: string | null): PrintPayload | null {
  if (!data) {
    return null
  }

  try {
    return JSON.parse(decodeBase64Url(data)) as PrintPayload
  } catch {
    return null
  }
}

// 用于读取 URL 或 sessionStorage 中的打印页载荷。
function readPrintPayload(data?: string, payloadKey?: string): PrintPayload | null {
  if (data) {
    return decodePayload(data)
  }

  if (!payloadKey) {
    return null
  }

  const storedPayload = window.sessionStorage.getItem(payloadKey)
  window.sessionStorage.removeItem(payloadKey)
  return decodePayload(storedPayload)
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

  useEffect(() => {
    setPayload(readPrintPayload(data, payloadKey))
    setIsReady(true)
  }, [data, payloadKey])

  const content = payload?.content
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
        data-resume-print-ready="true"
      >
        <p>{invalidPrintDataText}</p>
      </main>
    )
  }

  return (
    <main className="bg-white" data-resume-print-ready="true">
      <ResumePreview
        content={content}
        moduleOrder={moduleOrder}
        spacingScale={layoutConfig.spacingScale}
        templateStyle={templateStyle}
      />
    </main>
  )
}
