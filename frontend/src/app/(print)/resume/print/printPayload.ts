// 提供打印页载荷读取和渲染就绪判断。

import type { ResumeContent } from '@/types/resume'

export interface PrintPayload {
  content?: ResumeContent | null
  layout_config?: Record<string, unknown> | null
  template?: string
}

// 用于把 base64url 字符串解码成 UTF-8 JSON 字符串。
export function decodeBase64Url(data: string): string {
  const normalized = data.replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
  const binary = window.atob(padded)
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0))
  return new TextDecoder().decode(bytes)
}

// 用于解码打印页载荷。
export function decodePayload(data?: string | null): PrintPayload | null {
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
export function readPrintPayload(data?: string, payloadKey?: string): PrintPayload | null {
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

// 用于判断载荷是否包含可打印的简历内容。
export function hasPrintableResumeContent(payload: PrintPayload | null): boolean {
  const content = payload?.content
  return Boolean(
    content?.personal_info ||
    content?.summary?.text ||
    content?.education?.length ||
    content?.work_experience?.length ||
    content?.skills?.length ||
    content?.projects?.length ||
    content?.open_source?.length,
  )
}

// 用于判断后端 Playwright 是否可以安全开始打印。
export function isResumePrintReady(
  payload: PrintPayload | null,
  previewReady: boolean,
): boolean {
  return previewReady && hasPrintableResumeContent(payload)
}
