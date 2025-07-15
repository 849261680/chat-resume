'use client'

import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { resumeApi, interviewApi, type InterviewSession } from '@/lib/api'
import toast from 'react-hot-toast'
import Link from 'next/link'
import MainNavigation from '@/components/layout/MainNavigation'
import { 
  PlusIcon,
  ClockIcon,
  CalendarIcon,
  UserIcon,
  ChartBarIcon,
  PlayIcon,
  DocumentIcon,
  TrashIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline'

interface Resume {
  id: number
  title: string
  content: any
  created_at: string
  updated_at?: string
}


export default function InterviewsPage() {
  const { user, isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const [mounted, setMounted] = useState(false)
  const [resumes, setResumes] = useState<Resume[]>([])
  const [resumesLoading, setResumesLoading] = useState(true)
  const [showNewInterviewModal, setShowNewInterviewModal] = useState(false)
  const [interviewSessions, setInterviewSessions] = useState<InterviewSession[]>([])
  const [interviewsLoading, setInterviewsLoading] = useState(true)
  
  // 新建面试表单状态
  const [formData, setFormData] = useState({
    jobPosition: '',
    selectedResumeId: '',
    interviewMode: 'comprehensive',
    jdContent: ''
  })
  const [isCreating, setIsCreating] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [mounted, isLoading, isAuthenticated, router])

  // 获取简历列表
  const fetchResumes = async () => {
    if (!isAuthenticated) return
    
    try {
      setResumesLoading(true)
      const data = await resumeApi.getResumes()
      setResumes(data)
    } catch (error) {
      console.error('Failed to fetch resumes:', error)
      toast.error('获取简历列表失败')
    } finally {
      setResumesLoading(false)
    }
  }

  // 获取所有面试记录
  const fetchInterviewSessions = async () => {
    if (!isAuthenticated) return
    
    try {
      setInterviewsLoading(true)
      const allSessions: InterviewSession[] = []
      
      // 为每个简历获取面试记录
      for (const resume of resumes) {
        try {
          // 调用真实API获取面试会话
          const sessions = await interviewApi.getInterviewSessions(resume.id)
          
          // 检查是否有已完成但没有分数的面试
          const needScoreCalculation = sessions.some(session => 
            session.status === 'completed' && !session.overall_score
          )
          
          // 如果有需要计算分数的面试，先计算分数
          if (needScoreCalculation) {
            try {
              const result = await interviewApi.calculateScoresForCompletedInterviews(resume.id)
              if (result.updated_count > 0) {
                console.log(`为简历ID ${resume.id} 计算了 ${result.updated_count} 个面试的分数`)
                // 重新获取更新后的面试记录
                const updatedSessions = await interviewApi.getInterviewSessions(resume.id)
                const sessionsWithTitle = updatedSessions.map(session => ({
                  ...session,
                  resume_title: resume.title
                }))
                allSessions.push(...sessionsWithTitle)
              } else {
                const sessionsWithTitle = sessions.map(session => ({
                  ...session,
                  resume_title: resume.title
                }))
                allSessions.push(...sessionsWithTitle)
              }
            } catch (scoreError) {
              console.warn(`计算分数失败，简历ID: ${resume.id}`, scoreError)
              // 分数计算失败也继续显示面试记录
              const sessionsWithTitle = sessions.map(session => ({
                ...session,
                resume_title: resume.title
              }))
              allSessions.push(...sessionsWithTitle)
            }
          } else {
            const sessionsWithTitle = sessions.map(session => ({
              ...session,
              resume_title: resume.title
            }))
            allSessions.push(...sessionsWithTitle)
          }
          
          console.log(`获取到 ${sessions.length} 个真实面试记录，简历ID: ${resume.id}`)
          
        } catch (error) {
          console.error(`Failed to fetch sessions for resume ${resume.id}:`, error)
          
          // API调用失败时才添加模拟数据
          const baseId = resume.id * 1000 // 使用更大的基数避免冲突
          const mockSessions = [
            {
              id: baseId + 1,
              resume_id: resume.id,
              resume_title: resume.title,
              job_position: "AI应用开发工程师",
              interview_mode: "综合面试",
              jd_content: "负责AI应用开发...",
              questions: [],
              answers: [],
              feedback: {},
              status: "completed",
              overall_score: 87,
              current_question: 5,
              total_questions: 5,
              created_at: "2025-07-11T15:19:00Z",
              updated_at: "2025-07-11T15:44:00Z"
            },
            {
              id: baseId + 2,
              resume_id: resume.id,
              resume_title: resume.title,
              job_position: "高级前端工程师",
              interview_mode: "技术面试",
              jd_content: "负责前端开发...",
              questions: [],
              answers: [],
              feedback: {},
              status: "active",
              current_question: 7,
              total_questions: 15,
              created_at: "2025-07-11T16:00:00Z",
              updated_at: "2025-07-11T16:00:00Z"
            }
          ]
          console.log(`添加模拟数据，简历ID: ${resume.id}`)
          allSessions.push(...mockSessions)
        }
      }
      
      // 按创建时间降序排序
      allSessions.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      
      // 检测并标记可能的重复会话
      const processedSessions = allSessions.map(session => {
        // 检查是否有相同简历的其他活跃会话
        const duplicateActiveSessions = allSessions.filter(s => 
          s.resume_id === session.resume_id && 
          s.status === 'active' && 
          s.id !== session.id
        )
        
        // 如果当前会话是活跃状态，但有其他更新的活跃会话，标记为可能重复
        if (session.status === 'active' && duplicateActiveSessions.length > 0) {
          const newerActiveSession = duplicateActiveSessions.find(s => 
            new Date(s.created_at).getTime() > new Date(session.created_at).getTime()
          )
          if (newerActiveSession) {
            return { ...session, isPossibleDuplicate: true }
          }
        }
        
        return { ...session, isPossibleDuplicate: false }
      })
      
      setInterviewSessions(processedSessions)
    } catch (error) {
      console.error('Failed to fetch interview sessions:', error)
      toast.error('获取面试记录失败')
    } finally {
      setInterviewsLoading(false)
    }
  }

  useEffect(() => {
    if (mounted && isAuthenticated) {
      fetchResumes()
    }
  }, [mounted, isAuthenticated])

  // 在简历列表加载完成后获取面试记录
  useEffect(() => {
    if (resumes.length > 0 && !resumesLoading) {
      fetchInterviewSessions()
    }
  }, [resumes, resumesLoading])

  const formatDate = (dateString: string) => {
    // 时区处理与dashboard页面相同
    const normalizedDateString = dateString.includes('T') && !dateString.includes('Z') && !dateString.includes('+') 
      ? dateString + 'Z' 
      : dateString
    
    const date = new Date(normalizedDateString)
    
    return new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Shanghai',
      hour12: false
    }).format(date)
  }

  const handleNewInterview = () => {
    setShowNewInterviewModal(true)
    // 重置表单
    setFormData({
      jobPosition: '',
      selectedResumeId: '',
      interviewMode: 'comprehensive',
      jdContent: ''
    })
  }

  const handleCloseModal = () => {
    setShowNewInterviewModal(false)
    setFormData({
      jobPosition: '',
      selectedResumeId: '',
      interviewMode: 'comprehensive',
      jdContent: ''
    })
  }

  const handleDeleteInterview = async (sessionId: number, jobPosition: string) => {
    if (!confirm(`确定要删除面试记录 "${jobPosition}" 吗？此操作无法撤销。`)) {
      return
    }

    // 找到要删除的会话以获取resume_id
    const session = interviewSessions.find(s => s.id === sessionId)
    if (!session) {
      toast.error('未找到面试记录')
      return
    }

    try {
      toast.loading('正在删除面试记录...', { id: 'delete-interview' })
      
      // 检查是否为模拟数据（ID > 1000 表示模拟数据）
      if (sessionId > 1000) {
        // 模拟数据只需要从本地状态中移除
        console.log('删除模拟面试数据:', sessionId)
        setInterviewSessions(prev => prev.filter(s => s.id !== sessionId))
        toast.success('面试记录已删除', { id: 'delete-interview' })
      } else {
        // 真实数据需要调用API
        await interviewApi.deleteInterviewSession(session.resume_id, sessionId)
        // 从本地状态中移除
        setInterviewSessions(prev => prev.filter(s => s.id !== sessionId))
        toast.success('面试记录已删除', { id: 'delete-interview' })
      }
    } catch (error: any) {
      console.error('Delete interview error:', error)
      const errorMessage = error.message || '删除失败，请重试'
      toast.error(errorMessage, { id: 'delete-interview' })
    }
  }

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const handleStartInterview = async () => {
    // 验证表单
    if (!formData.selectedResumeId) {
      toast.error('请选择要面试的简历')
      return
    }

    if (!formData.jobPosition.trim()) {
      toast.error('请输入面试职位')
      return
    }

    setIsCreating(true)
    
    try {
      // 直接跳转到面试页面，将配置参数传递过去
      const params = new URLSearchParams({
        mode: formData.interviewMode,
        position: formData.jobPosition,
        ...(formData.jdContent && { jd: formData.jdContent })
      })
      
      router.push(`/resume/${formData.selectedResumeId}/interview?${params.toString()}`)
      
    } catch (error) {
      console.error('创建面试失败:', error)
      toast.error('创建面试失败，请重试')
    } finally {
      setIsCreating(false)
    }
  }

  if (!mounted || isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">正在加载...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <MainNavigation />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
        >
          {/* Header Section */}
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                面试中心
              </h1>
              <p className="text-gray-600">
                进行AI模拟面试，获得专业反馈和建议
              </p>
            </div>
            <button
              onClick={handleNewInterview}
              className="btn-primary flex items-center space-x-2"
            >
              <PlusIcon className="w-5 h-5" />
              <span>新建面试</span>
            </button>
          </div>

          {/* Interview History */}
          {interviewsLoading ? (
            <div className="flex justify-center items-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              <span className="ml-3 text-gray-600">加载面试记录...</span>
            </div>
          ) : interviewSessions.length === 0 ? (
            // Empty State
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="text-center py-12"
            >
              <ChartBarIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                还没有面试记录
              </h3>
              <p className="text-gray-500 mb-6">
                开始您的第一次AI模拟面试，提升面试表现
              </p>
              <button
                onClick={handleNewInterview}
                className="btn-primary flex items-center space-x-2 mx-auto"
              >
                <PlusIcon className="w-5 h-5" />
                <span>开始面试</span>
              </button>
            </motion.div>
          ) : (
            // Interview List
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {interviewSessions.map((session, index) => (
                <motion.div
                  key={session.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.8, delay: index * 0.1 }}
                  className="card px-6 py-5 hover:shadow-lg transition-shadow"
                >
                  {/* Session Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">
                        {session.job_position}
                      </h3>
                      <div className="space-y-1">
                        <div className="flex items-center text-sm text-gray-500">
                          <DocumentIcon className="w-4 h-4 mr-1" />
                          <span>基于简历: {session.resume_title}</span>
                        </div>
                        <div className="flex items-center text-sm text-gray-500">
                          <CalendarIcon className="w-4 h-4 mr-1" />
                          <span>{formatDate(session.created_at)}</span>
                        </div>
                        {session.status === 'active' && (
                          <div className="flex items-center text-sm text-gray-500">
                            <ClockIcon className="w-4 h-4 mr-1" />
                            <span>
                              {/* 优先使用 current_question/total_questions，否则动态计算 */}
                              {session.current_question && session.total_questions ? 
                                `${session.current_question}/${session.total_questions} 题` :
                                `${(session.answers || []).length}/${(session.questions || []).length} 题`
                              }
                            </span>
                          </div>
                        )}
                        {session.status === 'completed' && (
                          <div className="flex items-center text-sm text-gray-500">
                            <ClockIcon className="w-4 h-4 mr-1" />
                            <span>{session.total_questions || session.questions.length} 题</span>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    {/* 删除按钮 - 右上角 */}
                    <button
                      onClick={() => handleDeleteInterview(session.id, session.job_position)}
                      className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors"
                      title="删除面试"
                    >
                      <TrashIcon className="w-5 h-5" />
                    </button>
                  </div>

                  {/* Action Buttons - 根据状态显示不同按钮 */}
                  {session.status === 'completed' ? (
                    // 已完成的面试 - 面试完成按钮和查看报告按钮
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        className="btn-secondary flex items-center justify-center space-x-1 text-sm py-2 cursor-default"
                        disabled
                      >
                        <CheckCircleIcon className="w-4 h-4" />
                        <span>面试完成</span>
                      </button>
                      <Link
                        href={`/interviews/${session.id}/report?resume_id=${session.resume_id}`}
                        className="btn-primary flex items-center justify-center space-x-1 text-sm py-2"
                      >
                        <ChartBarIcon className="w-4 h-4" />
                        <span>查看报告</span>
                      </Link>
                    </div>
                  ) : session.status === 'active' ? (
                    // 进行中的面试 - 继续面试和查看报告按钮
                    <div className="grid grid-cols-2 gap-2">
                      <Link
                        href={`/resume/${session.resume_id}/interview?session=${session.id}`}
                        className="btn-primary flex items-center justify-center space-x-1 text-sm py-2"
                      >
                        <PlayIcon className="w-4 h-4" />
                        <span>继续面试</span>
                      </Link>
                      <Link
                        href={`/interviews/${session.id}/report?resume_id=${session.resume_id}`}
                        className="btn-secondary flex items-center justify-center space-x-1 text-sm py-2"
                      >
                        <ChartBarIcon className="w-4 h-4" />
                        <span>查看报告</span>
                      </Link>
                    </div>
                  ) : (
                    // 其他状态 - 显示两个按钮
                    <div className="grid grid-cols-2 gap-2">
                      <Link
                        href={`/resume/${session.resume_id}/interview?session=${session.id}`}
                        className="btn-primary flex items-center justify-center space-x-1 text-sm py-2"
                      >
                        <PlayIcon className="w-4 h-4" />
                        <span>继续面试</span>
                      </Link>
                      <Link
                        href={`/interviews/${session.id}/report`}
                        className="btn-secondary flex items-center justify-center space-x-1 text-sm py-2"
                      >
                        <ChartBarIcon className="w-4 h-4" />
                        <span>查看报告</span>
                      </Link>
                    </div>
                  )}
                </motion.div>
              ))}
            </div>
          )}
        </motion.div>
      </main>

      {/* New Interview Modal */}
      {showNewInterviewModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
            className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl mx-4 max-h-[80vh] overflow-y-auto"
          >
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold text-gray-900">
                新建面试
              </h3>
              <button
                onClick={handleCloseModal}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Interview Configuration Form */}
            <div className="space-y-6">
              {/* Job Position */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  面试职位
                </label>
                <input
                  type="text"
                  value={formData.jobPosition}
                  onChange={(e) => handleInputChange('jobPosition', e.target.value)}
                  placeholder="请输入面试职位，如：前端工程师"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Resume Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  选择简历
                </label>
                {resumesLoading ? (
                  <div className="flex items-center py-4">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600 mr-2"></div>
                    <span className="text-gray-600">加载简历列表...</span>
                  </div>
                ) : (
                  <select 
                    value={formData.selectedResumeId}
                    onChange={(e) => handleInputChange('selectedResumeId', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">请选择要面试的简历</option>
                    {resumes.map((resume) => (
                      <option key={resume.id} value={resume.id}>
                        {resume.title}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Interview Mode */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  面试模式
                </label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div 
                    className={`border rounded-lg p-3 cursor-pointer transition-colors ${
                      formData.interviewMode === 'comprehensive' 
                        ? 'bg-blue-50 border-blue-300 ring-2 ring-blue-500' 
                        : 'border-gray-200 hover:bg-blue-50 hover:border-blue-300'
                    }`}
                    onClick={() => handleInputChange('interviewMode', 'comprehensive')}
                  >
                    <div className="flex items-center space-x-2">
                      <input 
                        type="radio" 
                        name="interviewMode" 
                        value="comprehensive" 
                        checked={formData.interviewMode === 'comprehensive'}
                        onChange={() => handleInputChange('interviewMode', 'comprehensive')}
                        className="text-blue-600" 
                      />
                      <div>
                        <div className="font-medium text-gray-900">综合面试</div>
                        <div className="text-sm text-gray-500">技术+行为综合考察</div>
                      </div>
                    </div>
                  </div>
                  <div 
                    className={`border rounded-lg p-3 cursor-pointer transition-colors ${
                      formData.interviewMode === 'technical' 
                        ? 'bg-blue-50 border-blue-300 ring-2 ring-blue-500' 
                        : 'border-gray-200 hover:bg-blue-50 hover:border-blue-300'
                    }`}
                    onClick={() => handleInputChange('interviewMode', 'technical')}
                  >
                    <div className="flex items-center space-x-2">
                      <input 
                        type="radio" 
                        name="interviewMode" 
                        value="technical" 
                        checked={formData.interviewMode === 'technical'}
                        onChange={() => handleInputChange('interviewMode', 'technical')}
                        className="text-blue-600" 
                      />
                      <div>
                        <div className="font-medium text-gray-900">技术深挖</div>
                        <div className="text-sm text-gray-500">专注技术能力考察</div>
                      </div>
                    </div>
                  </div>
                  <div 
                    className={`border rounded-lg p-3 cursor-pointer transition-colors ${
                      formData.interviewMode === 'behavioral' 
                        ? 'bg-blue-50 border-blue-300 ring-2 ring-blue-500' 
                        : 'border-gray-200 hover:bg-blue-50 hover:border-blue-300'
                    }`}
                    onClick={() => handleInputChange('interviewMode', 'behavioral')}
                  >
                    <div className="flex items-center space-x-2">
                      <input 
                        type="radio" 
                        name="interviewMode" 
                        value="behavioral" 
                        checked={formData.interviewMode === 'behavioral'}
                        onChange={() => handleInputChange('interviewMode', 'behavioral')}
                        className="text-blue-600" 
                      />
                      <div>
                        <div className="font-medium text-gray-900">行为面试</div>
                        <div className="text-sm text-gray-500">关注软技能和文化契合</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* JD Content */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  职位描述 (JD)
                  <span className="text-gray-500 text-xs ml-1">可选，有助于生成更精准的面试问题</span>
                </label>
                <textarea
                  rows={6}
                  value={formData.jdContent}
                  onChange={(e) => handleInputChange('jdContent', e.target.value)}
                  placeholder="请粘贴职位描述内容，包括岗位职责、技能要求等..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end space-x-3 mt-8 pt-4 border-t">
              <button
                onClick={handleCloseModal}
                className="px-6 py-2 text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                取消
              </button>
              <button 
                onClick={handleStartInterview}
                disabled={isCreating || !formData.selectedResumeId || !formData.jobPosition.trim()}
                className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center space-x-2"
              >
                {isCreating ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>创建中...</span>
                  </>
                ) : (
                  <>
                    <PlayIcon className="w-4 h-4" />
                    <span>开始面试</span>
                  </>
                )}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}