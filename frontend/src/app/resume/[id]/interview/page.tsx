'use client'

import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import Link from 'next/link'
import { 
  ArrowLeftIcon,
  MicrophoneIcon,
  PaperAirplaneIcon,
  ClockIcon
} from '@heroicons/react/24/outline'

export default function InterviewPage() {
  const params = useParams()
  const router = useRouter()
  const { user, isAuthenticated, isLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [currentQuestion, setCurrentQuestion] = useState(1)
  const [totalQuestions] = useState(10)
  const [answer, setAnswer] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const resumeId = params?.id as string

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [mounted, isLoading, isAuthenticated, router])

  const handleSubmitAnswer = async () => {
    if (!answer.trim()) return

    setSubmitting(true)
    try {
      // TODO: 实现答案提交API
      await new Promise(resolve => setTimeout(resolve, 1000)) // 模拟API调用
      
      if (currentQuestion < totalQuestions) {
        setCurrentQuestion(prev => prev + 1)
        setAnswer('')
      } else {
        // 面试结束
        alert('面试完成！')
      }
    } catch (error) {
      console.error('Submit error:', error)
    } finally {
      setSubmitting(false)
    }
  }

  if (!mounted || isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">正在加载面试...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-4">
              <Link
                href="/dashboard"
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900"
              >
                <ArrowLeftIcon className="w-5 h-5" />
                <span>返回仪表板</span>
              </Link>
              <div className="h-6 border-l border-gray-300"></div>
              <h1 className="text-xl font-semibold text-gray-900">
                模拟面试
              </h1>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className="text-sm text-gray-600">
                进度: {currentQuestion}/{totalQuestions} 题
              </div>
              <div className="w-32 bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${(currentQuestion / totalQuestions) * 100}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          {/* AI Interviewer */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="card p-6"
          >
            <div className="flex items-start space-x-4">
              <div className="w-12 h-12 bg-gradient-primary rounded-full flex items-center justify-center">
                <span className="text-white font-bold">🤖</span>
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-gray-900 mb-2">AI面试官</h3>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-gray-800">
                    根据您的简历，我看到您有软件开发经验。请详细介绍一下您在项目中遇到的最有挑战性的技术问题，
                    以及您是如何解决这个问题的？请包括具体的技术细节和解决过程。
                  </p>
                </div>
              </div>
            </div>
          </motion.div>

          {/* User Answer */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="card p-6"
          >
            <h3 className="font-semibold text-gray-900 mb-4">💬 您的回答</h3>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="请在这里输入您的回答..."
              className="w-full p-4 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              rows={8}
            />
            
            <div className="flex items-center justify-between mt-4">
              <div className="flex items-center space-x-4">
                <button className="btn-secondary flex items-center space-x-2">
                  <MicrophoneIcon className="w-4 h-4" />
                  <span>语音回答</span>
                </button>
                <div className="text-sm text-gray-500">
                  建议回答时长: 2-3分钟
                </div>
              </div>
              
              <button
                onClick={handleSubmitAnswer}
                disabled={!answer.trim() || submitting}
                className="btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>提交中...</span>
                  </>
                ) : (
                  <>
                    <PaperAirplaneIcon className="w-4 h-4" />
                    <span>提交回答</span>
                  </>
                )}
              </button>
            </div>
          </motion.div>

          {/* Real-time Feedback */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="card p-6"
          >
            <h3 className="font-semibold text-gray-900 mb-4">📊 实时反馈</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-center space-x-2 mb-2">
                  <ClockIcon className="w-5 h-5 text-blue-600" />
                  <span className="font-medium text-blue-900">回答时长</span>
                </div>
                <p className="text-sm text-blue-800">建议2-3分钟</p>
              </div>

              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-green-600">✓</span>
                  <span className="font-medium text-green-900">关键词覆盖</span>
                </div>
                <p className="text-sm text-green-800">技术栈 ✓ 项目成果 ✗ 团队协作 ✗</p>
              </div>

              <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-orange-600">💡</span>
                  <span className="font-medium text-orange-900">建议</span>
                </div>
                <p className="text-sm text-orange-800">可以增加具体数据支撑</p>
              </div>
            </div>
          </motion.div>
        </div>
      </main>
    </div>
  )
}