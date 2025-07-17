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
  CheckIcon,
  ArrowUpIcon
} from '@heroicons/react/24/outline'
import PersonalInfoEditor from '@/components/editor/PersonalInfoEditor'
import EducationEditor from '@/components/editor/EducationEditor'
import WorkExperienceEditor from '@/components/editor/WorkExperienceEditor'
import SkillsEditor from '@/components/editor/SkillsEditor'
import ProjectsEditor from '@/components/editor/ProjectsEditor'
import ResumePreview from '@/components/preview/ResumePreview'
import MarkdownMessage from '@/components/ui/MarkdownMessage'
import StreamingMessage from '@/components/ui/StreamingMessage'
import { useStreamingChat } from '@/hooks/useStreamingChat'
// 已移除错误的前端Gemini集成

interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
}

interface Resume {
  id: number
  title: string
  content: {
    personal_info?: {
      name?: string
      email?: string
      phone?: string
      position?: string
      github?: string
    }
    education?: Array<{
      id?: number
      school: string
      major: string
      degree: string
      duration: string
      description?: string
    }>
    work_experience?: Array<{
      id?: number
      company: string
      position: string
      duration: string
      description: string
    }>
    skills?: Array<{
      id?: number
      name: string
      level: string
      category: string
    }>
    projects?: Array<{
      id?: number
      name: string
      description: string
      technologies: string[]
      role: string
      duration: string
      github_url?: string
      demo_url?: string
      achievements: string[]
    }>
  }
  created_at: string
  updated_at?: string
}

export default function ResumeEditPage() {
  const params = useParams()
  const router = useRouter()
  const { user, isAuthenticated, isLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [resume, setResume] = useState<Resume | null>(null)
  const [resumeLoading, setResumeLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [activeSection, setActiveSection] = useState('personal')
  
  // 聊天相关状态
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'ai',
      content: '您好！我是您的AI简历优化师，可以帮您优化简历内容，请告诉我您需要什么帮助？',
      timestamp: new Date()
    }
  ])
  const [inputMessage, setInputMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const resumeId = params?.id as string
  
  // 调试信息
  console.log('Resume ID from params:', resumeId)
  console.log('Parsed Resume ID:', parseInt(resumeId))
  console.log('Current user:', user)
  
  // 流式聊天Hook
  const {
    isStreaming,
    currentStreamingMessage,
    sendStreamingMessage,
    stopStreaming
  } = useStreamingChat(parseInt(resumeId), {
    onMessage: (message) => {
      setMessages(prev => [...prev, message])
    },
    onError: (error) => {
      setApiError(error)
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        type: 'ai',
        content: `抱歉，发生了错误：${error}`,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    }
  })

  useEffect(() => {
    setMounted(true)
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
      router.push('/dashboard')
    } finally {
      setResumeLoading(false)
    }
  }

  useEffect(() => {
    if (mounted && isAuthenticated) {
      fetchResume()
    }
  }, [mounted, isAuthenticated, resumeId])

  // 保存简历
  const handleSave = async () => {
    if (!resume) return

    try {
      setSaving(true)
      // 调用API更新简历
      await resumeApi.updateResume(resume.id, { 
        title: resume.title,
        content: resume.content 
      })
      toast.success('简历保存成功')
    } catch (error) {
      console.error('Save error:', error)
      toast.error('保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  // 更新简历内容
  const updateResumeContent = (section: string, data: any) => {
    if (!resume) return

    setResume(prev => ({
      ...prev!,
      content: {
        ...prev!.content,
        [section]: data
      }
    }))
  }

  // 聊天功能
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const sendMessage = async () => {
    if (!inputMessage.trim() || isSending || isStreaming) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputMessage.trim(),
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    const currentMessage = inputMessage.trim()
    setInputMessage('')
    setIsSending(true)
    setApiError(null)

    try {
      // 使用流式聊天，传递当前的聊天历史
      await sendStreamingMessage(currentMessage, messages)
    } catch (error) {
      console.error('Streaming chat error:', error)
      setApiError('流式聊天发送失败，请重试')
    } finally {
      setIsSending(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }



  // 自动滚动到底部
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  if (!mounted || isLoading || resumeLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">正在加载简历...</p>
        </div>
      </div>
    )
  }

  if (!resume) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">简历不存在</p>
          <Link href="/dashboard" className="btn-primary mt-4">
            返回简历中心
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-4">
              <Link
                href="/dashboard"
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900"
              >
                <ArrowLeftIcon className="w-5 h-5" />
                <span>返回简历中心</span>
              </Link>
              <div className="h-6 border-l border-gray-300"></div>
              <h1 className="text-xl font-semibold text-gray-900">
                简历编辑器 - {resume.title}
              </h1>
            </div>
            
            <div className="flex items-center space-x-3">
              <button
                onClick={handleSave}
                disabled={saving}
                className="btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>保存中...</span>
                  </>
                ) : (
                  <>
                    <CheckIcon className="w-4 h-4" />
                    <span>保存</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-140px)]">
          {/* Left Panel - Editor */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8 }}
            className="flex flex-col min-h-0"
          >
            <div className="card p-4 flex-1 overflow-hidden flex flex-col">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center flex-shrink-0">
                编辑区域
              </h2>
              <div className="flex-1 flex flex-col min-h-0">
                {/* Section Tabs */}
                <div className="flex space-x-1 mb-4 bg-gray-100 p-1 rounded-lg flex-shrink-0">
                  {[
                    { key: 'personal', label: '个人信息' },
                    { key: 'education', label: '教育经历' },
                    { key: 'work', label: '工作经验' },
                    { key: 'skills', label: '技能' },
                    { key: 'projects', label: '项目' }
                  ].map(section => (
                    <button
                      key={section.key}
                      onClick={() => setActiveSection(section.key)}
                      className={`flex-1 flex items-center justify-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                        activeSection === section.key
                          ? 'bg-white text-primary-600 shadow-sm'
                          : 'text-gray-600 hover:text-gray-900'
                      }`}
                    >
                      <span>{section.label}</span>
                    </button>
                  ))}
                </div>

                {/* Editor Content */}
                <div className="flex-1 overflow-y-auto min-h-0 pr-2">
                  {activeSection === 'personal' && (
                    <PersonalInfoEditor
                      data={resume.content.personal_info || {}}
                      onChange={(data) => updateResumeContent('personal_info', data)}
                    />
                  )}
                  
                  {activeSection === 'education' && (
                    <EducationEditor
                      data={resume.content.education || []}
                      onChange={(data) => updateResumeContent('education', data)}
                    />
                  )}
                  
                  {activeSection === 'work' && (
                    <WorkExperienceEditor
                      data={resume.content.work_experience || []}
                      onChange={(data) => updateResumeContent('work_experience', data)}
                    />
                  )}
                  
                  {activeSection === 'skills' && (
                    <SkillsEditor
                      data={resume.content.skills || []}
                      onChange={(data) => updateResumeContent('skills', data)}
                    />
                  )}
                  
                  {activeSection === 'projects' && (
                    <ProjectsEditor
                      data={resume.content.projects || []}
                      onChange={(data) => updateResumeContent('projects', data)}
                    />
                  )}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Middle Panel - AI Chat */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="flex flex-col min-h-0"
          >
            <div className="card p-4 flex-1 overflow-hidden flex flex-col">
              <div className="flex items-center justify-between mb-4 flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">
                  AI简历优化师
                </h2>
              </div>
              
              {/* API错误提示 */}
              {apiError && (
                <div className="mb-3 p-2 bg-orange-50 border border-orange-200 rounded-lg text-sm text-orange-700 flex-shrink-0">
                  ⚠️ {apiError}
                </div>
              )}
              <div className="flex-1 flex flex-col min-h-0">
                {/* Messages Display Area */}
                <div className="flex-1 overflow-y-auto mb-4 space-y-3 pr-2 min-h-0 max-h-full">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[85%] px-4 py-3 rounded-lg ${
                          message.type === 'user'
                            ? 'bg-blue-600 text-white rounded-br-sm text-sm'
                            : 'bg-gray-50 text-gray-800 rounded-bl-sm border border-gray-200'
                        }`}
                      >
                        {message.type === 'ai' ? (
                          <MarkdownMessage content={message.content} />
                        ) : (
                          <span className="text-sm">{message.content}</span>
                        )}
                      </div>
                    </div>
                  ))}
                  {/* 流式传输中的消息 */}
                  {isStreaming && currentStreamingMessage && (
                    <div className="flex justify-start">
                      <div className="max-w-[85%] px-4 py-3 rounded-lg bg-gray-50 text-gray-800 rounded-bl-sm border border-gray-200">
                        <StreamingMessage content={currentStreamingMessage} isComplete={false} />
                      </div>
                    </div>
                  )}
                  
                  {/* 等待响应动画 */}
                  {(isSending || isStreaming) && !currentStreamingMessage && (
                    <div className="flex justify-start">
                      <div className="bg-gray-100 text-gray-800 px-4 py-2 rounded-lg rounded-bl-sm text-sm">
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

                {/* Input Area */}
                <div className="pt-3 flex-shrink-0">
                  <div className="relative">
                    <textarea
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="输入消息..."
                      className="w-full p-2 pr-12 border border-gray-300 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      rows={2}
                      disabled={isSending || isStreaming}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={!inputMessage.trim() || isSending || isStreaming}
                      className={`absolute right-2 top-1/2 transform -translate-y-1/2 w-8 h-8 rounded-full transition-colors flex items-center justify-center ${
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
            </div>
          </motion.div>

          {/* Right Panel - Preview */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="flex flex-col min-h-0"
          >
            <div className="card p-4 flex-1 overflow-hidden flex flex-col">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center flex-shrink-0">
                实时预览
              </h2>
              <div className="flex-1 overflow-hidden min-h-0">
                <ResumePreview content={resume.content} />
              </div>
            </div>
          </motion.div>
        </div>
      </main>
    </div>
  )
}