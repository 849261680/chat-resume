// 用于提供 app/(print)/layout.tsx 模块。
import type { Metadata, Viewport } from 'next'
import { NextIntlClientProvider } from 'next-intl'
import '../globals.css'
import '../../styles/markdown.css'

export const metadata: Metadata = {
  title: 'Chat Resume',
  description: 'AI resume optimization and mock interview platform',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#2563eb',
}

// 用于渲染 PrintRootLayout 组件。
export default function PrintRootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh" data-scroll-behavior="smooth" suppressHydrationWarning>
      <head>
        <link id="resume-print-styles" rel="stylesheet" href="/styles/resume-print.css" />
      </head>
      <body className="font-sans">
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  )
}
