import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from '@/lib/auth'
import './globals.css'
import '../styles/markdown.css'

const inter = Inter({ 
  subsets: ['latin'],
  fallback: ['system-ui', 'arial'],
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Chat Resume - AI驱动的智能简历优化平台',
  description: '使用AI技术优化简历，提供模拟面试训练，帮助您获得理想工作',
  keywords: '简历优化, AI简历, 模拟面试, 求职, 简历制作',
  authors: [{ name: 'Chat Resume Team' }],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body className={inter.className}>
        <AuthProvider>
          {children}
        </AuthProvider>
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#fff',
              color: '#374151',
              boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
              border: '1px solid #e5e7eb',
              borderRadius: '0.75rem',
            },
            success: {
              iconTheme: {
                primary: '#10b981',
                secondary: '#fff',
              },
            },
            error: {
              iconTheme: {
                primary: '#ef4444',
                secondary: '#fff',
              },
            },
          }}
        />
      </body>
    </html>
  )
}