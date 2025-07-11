'use client'

import { motion } from 'framer-motion'
import { useEffect, useState, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { resumeApi } from '@/lib/api'
import toast from 'react-hot-toast'
import Link from 'next/link'
import { 
  ArrowLeftIcon,
  StopIcon,
  ClockIcon,
  ArrowUpIcon
} from '@heroicons/react/24/outline'
import MarkdownMessage from '@/components/ui/MarkdownMessage'
import StreamingMessage from '@/components/ui/StreamingMessage'
import { useInterview } from '@/hooks/useInterview'
import InterviewerAvatar, { InterviewerProfile, interviewerProfiles } from '@/components/interview/InterviewerAvatar'
import QuestionTypeLabel, { detectQuestionType } from '@/components/interview/QuestionTypeLabel'
import FeedbackPanel from '@/components/interview/FeedbackPanel'

interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
}

interface Resume {
  id: number
  title: string
  content: any
  created_at: string
  updated_at?: string
}

export default function InterviewPage() {
  const params = useParams()
  const router = useRouter()
  const { user, isAuthenticated, isLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [resume, setResume] = useState<Resume | null>(null)
  const [resumeLoading, setResumeLoading] = useState(true)
  
  // 获取URL参数
  const [interviewConfig, setInterviewConfig] = useState({
    mode: 'comprehensive',
    position: '',
    jd: ''
  })
  
  // 面试相关状态
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [interviewTime, setInterviewTime] = useState(0)
  const [currentQuestion, setCurrentQuestion] = useState(1)
  const [selectedInterviewer, setSelectedInterviewer] = useState<InterviewerProfile>(interviewerProfiles[0])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<NodeJS.Timeout | null>(null)

  const resumeId = params?.id as string

  // 面试Hook
  const {
    isInterviewActive,
    currentSession,
    isLoading: interviewLoading,
    currentStreamingMessage,
    startInterview,
    sendAnswer,
    endInterview,
    stopCurrentRequest
  } = useInterview(resumeId ? parseInt(resumeId) : 0, {
    onMessage: (message) => {
      setMessages(prev => [...prev, message])
    },
    onError: (error) => {
      toast.error(`面试错误: ${error}`)
    },
    chatHistory: messages,
    interviewMode: interviewConfig.mode,
    jobPosition: interviewConfig.position,
    jdContent: interviewConfig.jd
  })

  useEffect(() => {
    setMounted(true)
    
    // 解析URL参数
    const urlParams = new URLSearchParams(window.location.search)
    const mode = urlParams.get('mode') || 'comprehensive'
    const position = urlParams.get('position') || ''
    const jd = urlParams.get('jd') || ''
    
    setInterviewConfig({
      mode,
      position,
      jd
    })
  }, [])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [mounted, isLoading, isAuthenticated, router])

  // 获取简历数据
  const fetchResume = async () => {
    if (!resumeId || !isAuthenticated) return

    try {
      setResumeLoading(true)
      const data = await resumeApi.getResume(parseInt(resumeId))
      setResume(data)
    } catch (error) {
      console.error('Failed to fetch resume:', error)
      toast.error('获取简历失败')
      router.push('/interviews')
    } finally {
      setResumeLoading(false)
    }
  }

  useEffect(() => {
    if (mounted && isAuthenticated) {
      fetchResume()
    }
  }, [mounted, isAuthenticated, resumeId])

  // 自动开始面试
  useEffect(() => {
    if (resume && !isInterviewActive && !interviewLoading) {
      handleStartInterview()
    }
  }, [resume, isInterviewActive, interviewLoading])

  // 计时器
  useEffect(() => {
    if (isInterviewActive) {
      timerRef.current = setInterval(() => {
        setInterviewTime(prev => prev + 1)
      }, 1000)
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [isInterviewActive])

  // 格式化时间
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  // 开始面试
  const handleStartInterview = async () => {
    if (!resume) return

    try {
      const session = await startInterview(interviewConfig.jd)
      if (session) {
        setInterviewTime(0)
        setCurrentQuestion(1)
        setMessages([]) // 清空之前的消息，hook会添加欢迎消息
        toast.success(`面试已开始！模式：${getModeDisplayName(interviewConfig.mode)}`)
      }
    } catch (error) {
      console.error('Failed to start interview:', error)
      toast.error('开始面试失败，请重试')
    }
  }

  // 获取模式显示名称
  const getModeDisplayName = (mode: string) => {
    const modes = {
      'comprehensive': '综合面试',
      'technical': '技术深挖', 
      'behavioral': '行为面试'
    }
    return modes[mode as keyof typeof modes] || '综合面试'
  }

  // 结束面试
  const handleEndInterview = async () => {
    try {
      await endInterview()
      setInterviewTime(0)
      toast.success('面试已结束')
    } catch (error) {
      console.error('Failed to end interview:', error)
      toast.error('结束面试失败')
    }
  }

  // 发送消息
  const handleSendMessage = async () => {
    if (!inputMessage.trim() || interviewLoading) return

    const currentMessage = inputMessage.trim()
    setInputMessage('')
    
    try {
      await sendAnswer(currentMessage)
      setCurrentQuestion(prev => prev + 1)
    } catch (error) {
      console.error('Failed to send message:', error)
      toast.error('发送消息失败，请重试')
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (!mounted || isLoading || resumeLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">正在加载面试系统...</p>
        </div>
      </div>
    )
  }

  if (!resume) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">简历不存在</p>
          <Link href="/interviews" className="btn-primary mt-4">
            返回面试中心
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col overflow-hidden">
      {/* Enhanced Header */}
      <header className="bg-white shadow-sm border-b flex-shrink-0">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            {/* 左侧：导航和标题 */}
            <div className="flex items-center space-x-4">
              <Link
                href="/interviews"
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 transition-colors"
              >
                <ArrowLeftIcon className="w-5 h-5" />
                <span>返回面试中心</span>
              </Link>
              <div className="h-6 border-l border-gray-300"></div>
              <div>
                <h1 className="text-lg font-semibold text-gray-900">
                  AI模拟面试
                </h1>
                <div className="flex items-center space-x-2 text-sm text-gray-500">
                  <span>{resume.title}</span>
                  {interviewConfig.position && (
                    <>
                      <span>•</span>
                      <span>{interviewConfig.position}</span>
                    </>
                  )}
                  <span>•</span>
                  <span>{getModeDisplayName(interviewConfig.mode)}</span>
                </div>
              </div>
            </div>
            
            {/* 中间：进度条（仅在面试进行时显示） */}
            {isInterviewActive && (
              <div className="flex-1 max-w-md mx-8">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-500">面试进度</span>
                  <span className="text-xs text-gray-500">{currentQuestion}/15 问</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-gradient-to-r from-blue-500 to-indigo-600 h-2 rounded-full transition-all duration-300 ease-out"
                    style={{width: `${(currentQuestion / 15) * 100}%`}}
                  ></div>
                </div>
              </div>
            )}
            
            {/* 右侧：状态和控制 */}
            {isInterviewActive && (
              <div className="flex items-center space-x-6">
                {/* 计时器 */}
                <div className="flex items-center space-x-2 px-3 py-1 bg-blue-50 rounded-full">
                  <ClockIcon className="w-4 h-4 text-blue-600" />
                  <span className="text-sm font-medium text-blue-700">{formatTime(interviewTime)}</span>
                </div>
                
                {/* 当前问题数 */}
                <div className="flex items-center space-x-2 px-3 py-1 bg-green-50 rounded-full">
                  <span className="text-sm font-medium text-green-700">第 {currentQuestion} 问</span>
                </div>
                
                {/* 控制按钮 */}
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => {/* TODO: 暂停功能 */}}
                    className="btn-secondary text-sm px-3 py-1"
                  >
                    暂停
                  </button>
                  <button
                    onClick={handleEndInterview}
                    className="btn-danger text-sm px-3 py-1 flex items-center space-x-1"
                  >
                    <StopIcon className="w-4 h-4" />
                    <span>结束面试</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content - 三区域布局 */}
      <main className="flex-1 flex overflow-hidden">
        {!isInterviewActive && !interviewLoading ? (
          // 加载状态
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex-1 flex items-center justify-center"
          >
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">正在启动面试系统...</p>
            </div>
          </motion.div>
        ) : (
          // 面试进行页面 - 三区域布局
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="flex-1 flex overflow-hidden"
          >
            {/* 左侧：模拟面试区域 */}
            <div className="flex-1 flex flex-col bg-white border-r border-gray-200 overflow-hidden">
              {/* 面试官信息卡片 */}
              <div className="p-4 border-b border-gray-100 bg-gradient-to-r from-blue-50 to-indigo-50 flex-shrink-0">
                <InterviewerAvatar 
                  selectedInterviewer={selectedInterviewer}
                  onSelect={setSelectedInterviewer}
                  showSelector={!isInterviewActive} // 只在面试开始前允许更换面试官
                />
              </div>

              {/* 对话区域 */}
              <div className="flex-1 p-4 overflow-y-auto min-h-0">
                <div className="space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div className={`max-w-[85%] ${message.type === 'user' ? 'flex justify-end' : ''}`}>
                        {message.type === 'ai' && (
                          <div className="mb-2">
                            <QuestionTypeLabel type={detectQuestionType(message.content)} />
                          </div>
                        )}
                        <div
                          className={`px-4 py-3 rounded-lg ${
                            message.type === 'user'
                              ? 'bg-blue-600 text-white rounded-br-sm'
                              : 'bg-gray-50 text-gray-800 rounded-bl-sm border border-gray-200'
                          }`}
                        >
                          {message.type === 'ai' ? (
                            <MarkdownMessage content={message.content} />
                          ) : (
                            <span>{message.content}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                  
                  {/* 流式传输中的消息 */}
                  {currentStreamingMessage && (
                    <div className="flex justify-start">
                      <div className="max-w-[85%] px-4 py-3 rounded-lg bg-gray-50 text-gray-800 rounded-bl-sm border border-gray-200">
                        <StreamingMessage content={currentStreamingMessage} isComplete={false} />
                      </div>
                    </div>
                  )}
                  
                  {/* 等待响应动画 */}
                  {interviewLoading && !currentStreamingMessage && (
                    <div className="flex justify-start">
                      <div className="bg-gray-100 text-gray-800 px-4 py-2 rounded-lg rounded-bl-sm">
                        <div className="flex items-center space-x-1">
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              </div>

              {/* 输入区域 */}
              <div className="p-4 border-t border-gray-200 bg-gray-50 flex-shrink-0">
                <div className="relative">
                  <textarea
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="请输入您的回答..."
                    className="w-full p-3 pr-12 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                    rows={3}
                    disabled={interviewLoading}
                  />
                  <button
                    onClick={handleSendMessage}
                    disabled={!inputMessage.trim() || interviewLoading}
                    className={`absolute right-3 bottom-3 w-8 h-8 rounded-full transition-colors flex items-center justify-center ${
                      inputMessage.trim() 
                        ? 'bg-blue-600 text-white hover:bg-blue-700' 
                        : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    } disabled:cursor-not-allowed`}
                  >
                    <ArrowUpIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* 右侧：实时反馈区域 */}
            <FeedbackPanel
              lastQuestion={messages.filter(m => m.type === 'ai').slice(-1)[0]?.content}
              lastAnswer={messages.filter(m => m.type === 'user').slice(-1)[0]?.content}
              resumeId={resumeId ? parseInt(resumeId) : undefined}
              isLoading={interviewLoading}
            />
          </motion.div>
        )}
      </main>
    </div>
  )
}