'use client'

import { motion } from 'framer-motion'
import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { resumeApi } from '@/lib/api'
import toast from 'react-hot-toast'
import Link from 'next/link'
import { 
  ArrowLeftIcon,
  StopIcon,
  ClockIcon,
  ArrowUpIcon,
  MicrophoneIcon
} from '@heroicons/react/24/outline'
import MarkdownMessage from '@/components/ui/MarkdownMessage'
import StreamingMessage from '@/components/ui/StreamingMessage'
import { useInterview } from '@/hooks/useInterview'
import InterviewerAvatar, { InterviewerProfile, interviewerProfiles } from '@/components/interview/InterviewerAvatar'
import QuestionTypeLabel, { detectQuestionType } from '@/components/interview/QuestionTypeLabel'
import FeedbackPanel from '@/components/interview/FeedbackPanel'
import VoiceControls from '@/components/interview/VoiceControls'
import VoiceRecorder, { VoiceRecorderRef } from '@/components/interview/VoiceRecorder'

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
  const [resumeFetched, setResumeFetched] = useState(false)
  
  // 获取URL参数
  const [interviewConfig, setInterviewConfig] = useState({
    mode: 'comprehensive',
    position: '',
    jd: '',
    sessionId: null as number | null
  })
  
  // 面试相关状态
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [interviewTime, setInterviewTime] = useState(0)
  const [currentQuestion, setCurrentQuestion] = useState(1)
  const [selectedInterviewer, setSelectedInterviewer] = useState<InterviewerProfile>(interviewerProfiles[0])
  const [hasStartedInterview, setHasStartedInterview] = useState(false) // 防重复标志
  const [interviewError, setInterviewError] = useState<string | null>(null)
  const [autoPlayVoice, setAutoPlayVoice] = useState(true) // 自动播放语音
  const [isVoiceRecording, setIsVoiceRecording] = useState(false) // 语音录制状态
  const [inputMode, setInputMode] = useState<'text' | 'voice'>('text') // 输入模式
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const processedSessionRef = useRef<number | null>(null) // 防止重复处理同一会话ID
  const hasCheckedExistingSession = useRef(false) // 防止重复检查现有会话
  const voiceRecorderRef = useRef<VoiceRecorderRef>(null) // VoiceRecorder组件引用

  const resumeId = params?.id as string

  // 稳定回调函数
  const handleMessage = useCallback((message: ChatMessage) => {
    setMessages(prev => [...prev, message])
  }, [])

  const handleError = useCallback((error: string) => {
    console.error('Interview error:', error)
    setInterviewError(error)
    toast.error(`面试错误: ${error}`)
  }, [])

  // 使用 useRef 确保回调稳定性
  const handleMessageRef = useRef(handleMessage)
  const handleErrorRef = useRef(handleError)
  
  useEffect(() => {
    handleMessageRef.current = handleMessage
    handleErrorRef.current = handleError
  })

  // 使用 useMemo 稳定 useInterview 的 options 对象
  const interviewOptions = useMemo(() => ({
    onMessage: (msg: ChatMessage) => handleMessageRef.current(msg),
    onError: (error: string) => handleErrorRef.current(error),
    interviewMode: interviewConfig.mode,
    jobPosition: interviewConfig.position,
    jdContent: interviewConfig.jd,
    existingSessionId: interviewConfig.sessionId
  }), [interviewConfig.mode, interviewConfig.position, interviewConfig.jd, interviewConfig.sessionId])

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
  } = useInterview(resumeId ? parseInt(resumeId) : 0, interviewOptions)

  useEffect(() => {
    setMounted(true)
    
    // 重置检查标志
    hasCheckedExistingSession.current = false
    processedSessionRef.current = null
    
    // 抑制Chrome扩展的runtime.lastError错误
    const originalError = console.error
    console.error = (...args) => {
      const message = args[0]?.toString() || ''
      if (message.includes('runtime.lastError') || 
          message.includes('message channel closed')) {
        // 静默忽略Chrome扩展错误
        return
      }
      originalError.apply(console, args)
    }
    
    // 清理函数
    return () => {
      console.error = originalError
    }
    
    // 解析URL参数
    const urlParams = new URLSearchParams(window.location.search)
    const mode = urlParams.get('mode') || 'comprehensive'
    const position = urlParams.get('position') || ''
    const jd = urlParams.get('jd') || ''
    const sessionId = urlParams.get('session') ? parseInt(urlParams.get('session')!) : null
    
    console.log('URL参数解析完成:', { mode, position, jd, sessionId })
    
    // 如果URL中有sessionId，标记为已处理
    if (sessionId) {
      processedSessionRef.current = sessionId
    }
    
    setInterviewConfig({
      mode,
      position,
      jd,
      sessionId
    })
  }, [])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [mounted, isLoading, isAuthenticated, router])

  // 确保 resumeLoading 状态正确重置
  useEffect(() => {
    if (mounted && isAuthenticated && !resumeFetched && resumeId) {
      fetchResume()
    } else if (mounted && (!isAuthenticated || !resumeId)) {
      setResumeLoading(false)
    }
  }, [mounted, isAuthenticated, resumeId, resumeFetched])

  // 监听面试配置变化
  useEffect(() => {
    console.log('面试配置已更新:', interviewConfig)
    if (interviewConfig.sessionId) {
      console.log('检测到面试会话ID:', interviewConfig.sessionId, '- Hook应该自动加载会话')
    }
  }, [interviewConfig])

  // 监听面试状态变化（减少日志输出）
  useEffect(() => {
    if (isInterviewActive !== undefined) {
      console.log('面试状态变化:', { 
        isInterviewActive, 
        interviewLoading, 
        currentSession: currentSession?.id,
        messagesCount: messages.length 
      })
    }
  }, [isInterviewActive, interviewLoading, currentSession?.id, messages.length])

  // 获取简历数据
  const fetchResume = async () => {
    if (!resumeId || !isAuthenticated || resumeFetched) {
      return
    }

    try {
      setResumeLoading(true)
      const data = await resumeApi.getResume(parseInt(resumeId))
      setResume(data)
      setResumeFetched(true)
    } catch (error) {
      console.error('Failed to fetch resume:', error)
      toast.error('获取简历失败')
      router.push('/interviews')
    } finally {
      setResumeLoading(false)
    }
  }

  // 开始面试
  const handleStartInterview = useCallback(async () => {
    if (!resume) return

    // 如果是继续现有会话，不需要防重复逻辑
    if (!interviewConfig.sessionId && hasStartedInterview) return

    console.log('Debug - handleStartInterview 被调用', { 
      existingSessionId: interviewConfig.sessionId,
      hasStartedInterview 
    })
    
    if (!interviewConfig.sessionId) {
      setHasStartedInterview(true) // 只对新面试设置标志
    }

    try {
      // 先清空消息，然后等待hook添加欢迎消息
      setMessages([])
      setInterviewTime(0)
      setCurrentQuestion(1)
      
      const session = await startInterview(interviewConfig.jd, parseInt(new URLSearchParams(window.location.search).get('questionCount') || '10'))
      if (session) {
        const action = interviewConfig.sessionId ? '继续' : '开始'
        toast.success(`面试已${action}！模式：${getModeDisplayName(interviewConfig.mode)}`)
      }
    } catch (error) {
      console.error('Failed to start interview:', error)
      toast.error('开始面试失败，请重试')
      if (!interviewConfig.sessionId) {
        setHasStartedInterview(false) // 失败时重置标志（仅限新面试）
      }
    }
  }, [resume, hasStartedInterview, startInterview, interviewConfig.jd])

  // 自动开始面试 - 仅在没有指定sessionId时运行
  useEffect(() => {
    if (resume && 
        !isInterviewActive && 
        !interviewLoading && 
        !hasStartedInterview && 
        !interviewConfig.sessionId &&
        !hasCheckedExistingSession.current) {
      
      console.log('自动检查面试会话 - 没有指定sessionId')
      hasCheckedExistingSession.current = true // 立即设置标志，防止重复检查
      
      // 检查是否已有进行中的面试会话，避免重复创建
      const checkAndStartInterview = async () => {
        try {
          const token = localStorage.getItem('access_token')
          if (!token) return
          
          // 检查现有的面试会话
          const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/resumes/${resumeId}/interview/sessions`, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          
          if (response.ok) {
            const sessions = await response.json()
            const activeSession = sessions.find((s: any) => s.status === 'active')
            
            if (activeSession && processedSessionRef.current !== activeSession.id) {
              console.log('发现进行中的面试会话:', activeSession.id)
              console.log('会话详情:', activeSession)
              
              const answeredCount = (activeSession.answers || []).length
              const totalQuestions = (activeSession.questions || []).length
              
              // 检查会话是否实际已完成（所有问题都已回答）
              if (answeredCount >= totalQuestions && totalQuestions > 0) {
                console.log('检测到会话实际已完成，但状态未更新，自动更新状态')
                try {
                  await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/resumes/${resumeId}/interview/${activeSession.id}/end`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` }
                  })
                  console.log('已完成会话状态已更新，继续创建新会话')
                  // 继续创建新会话
                } catch (error) {
                  console.error('更新会话状态失败:', error)
                }
              } else {
                // 会话确实未完成，询问用户是否继续
                const shouldContinue = confirm(`发现您有一个未完成的面试会话（已回答 ${answeredCount}/${totalQuestions} 题）。\n\n点击"确定"继续上次面试\n点击"取消"开始新面试`)
                
                if (shouldContinue) {
                  console.log('用户选择继续现有会话')
                  processedSessionRef.current = activeSession.id
                  setInterviewConfig(prev => ({
                    ...prev,
                    sessionId: activeSession.id
                  }))
                  setHasStartedInterview(true)
                  return
                } else {
                  console.log('用户选择开始新面试，将结束现有会话')
                  try {
                    // 结束现有会话
                    await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/resumes/${resumeId}/interview/${activeSession.id}/end`, {
                      method: 'POST',
                      headers: { 'Authorization': `Bearer ${token}` }
                    })
                    console.log('现有会话已结束，将创建新会话')
                    toast.success('已结束上次面试，开始新面试')
                  } catch (error) {
                    console.error('结束现有会话失败:', error)
                    toast.error('结束上次面试失败，请稍后重试')
                    return
                  }
                }
              }
            }
          }
        } catch (error) {
          console.warn('检查现有会话失败:', error)
        }
        
        console.log('Debug - 开始新的面试会话')
        handleStartInterview()
      }
      
      checkAndStartInterview()
    }
  }, [resume, isInterviewActive, interviewLoading, hasStartedInterview, handleStartInterview, resumeId])


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
      setHasStartedInterview(false) // 重置标志，允许重新开始面试
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

  // 处理录音按钮点击
  const handleVoiceButtonClick = async () => {
    if (isVoiceRecording) {
      // 如果正在录音，停止录音
      if (voiceRecorderRef.current) {
        await voiceRecorderRef.current.stopRecording()
      }
    } else {
      // 如果没有在录音，开始录音
      if (voiceRecorderRef.current) {
        await voiceRecorderRef.current.startRecording()
      }
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
                  {/* 自动播放开关 */}
                  <label className="flex items-center space-x-2 text-sm">
                    <input
                      type="checkbox"
                      checked={autoPlayVoice}
                      onChange={(e) => setAutoPlayVoice(e.target.checked)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-gray-700">自动播放</span>
                  </label>
                  
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
        {!isInterviewActive ? (
          // 面试未开始状态或错误状态
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex-1 flex items-center justify-center"
          >
            <div className="text-center">
              {interviewLoading ? (
                // 面试启动中的加载状态
                <div>
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                  <p className="text-gray-600">正在启动面试系统...</p>
                </div>
              ) : interviewError ? (
                <>
                  <div className="text-red-600 mb-4">
                    <svg className="w-12 h-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-lg font-medium">面试启动失败</p>
                    <p className="text-sm mt-2">{interviewError}</p>
                  </div>
                  <div className="space-x-4">
                    <button 
                      onClick={() => {
                        setInterviewError(null)
                        setHasStartedInterview(false)
                        window.location.reload()
                      }}
                      className="btn-primary"
                    >
                      重新尝试
                    </button>
                    <Link href="/interviews" className="btn-secondary">
                      返回面试中心
                    </Link>
                  </div>
                </>
              ) : (
                <p className="text-gray-600">面试系统准备就绪，等待启动...</p>
              )}
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
                          <div className="mb-2 flex items-center justify-between">
                            <QuestionTypeLabel type={detectQuestionType(message.content)} />
                            <VoiceControls 
                              questionText={message.content}
                              isVisible={true}
                              autoPlay={autoPlayVoice}
                              onVoiceStart={() => console.log('语音开始播放')}
                              onVoiceEnd={() => console.log('语音播放结束')}
                              onVoiceError={(error) => {
                                console.error('语音播放错误:', error)
                                toast.error('语音播放失败')
                              }}
                            />
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
                      <div className="max-w-[85%]">
                        <div className="mb-2 flex items-center justify-between">
                          <QuestionTypeLabel type={detectQuestionType(currentStreamingMessage)} />
                          <VoiceControls 
                            questionText={currentStreamingMessage}
                            isVisible={currentStreamingMessage.length > 10}
                            onVoiceStart={() => console.log('语音开始播放')}
                            onVoiceEnd={() => console.log('语音播放结束')}
                            onVoiceError={(error) => {
                              console.error('语音播放错误:', error)
                              toast.error('语音播放失败')
                            }}
                          />
                        </div>
                        <div className="px-4 py-3 rounded-lg bg-gray-50 text-gray-800 rounded-bl-sm border border-gray-200">
                          <StreamingMessage content={currentStreamingMessage} isComplete={false} />
                        </div>
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
                {/* 隐藏的语音录制组件 */}
                <div style={{ display: 'none' }}>
                  <VoiceRecorder
                    ref={voiceRecorderRef}
                    onTranscriptionComplete={(text) => {
                      setInputMessage(text)
                      // 自动发送识别结果
                      setTimeout(() => {
                        if (text.trim()) {
                          handleSendMessage()
                        }
                      }, 500)
                    }}
                    onRecordingStateChange={(recording) => {
                      setIsVoiceRecording(recording)
                    }}
                    onError={(error) => {
                      console.error('语音录制错误:', error)
                      toast.error(`语音录制失败: ${error}`)
                    }}
                    disabled={interviewLoading}
                  />
                </div>

                {/* 输入框和按钮 */}
                <div className="relative">
                  <textarea
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="请输入您的回答..."
                    className="w-full p-3 pr-20 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                    rows={3}
                    disabled={interviewLoading}
                  />
                  
                  {/* 语音输入按钮 */}
                  <button
                    onClick={handleVoiceButtonClick}
                    disabled={interviewLoading}
                    className={`absolute right-12 bottom-3 w-8 h-8 rounded-full transition-colors flex items-center justify-center ${
                      isVoiceRecording
                        ? 'bg-red-500 text-white hover:bg-red-600'
                        : 'bg-gray-400 text-white hover:bg-gray-500'
                    } disabled:cursor-not-allowed disabled:opacity-50`}
                    title={isVoiceRecording ? '停止录音' : '开始录音'}
                  >
                    <MicrophoneIcon className="w-4 h-4" />
                  </button>
                  
                  {/* 发送按钮 */}
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