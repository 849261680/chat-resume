'use client'

import { motion } from 'framer-motion'
import { useEffect, useState, useRef } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { resumeApi } from '@/lib/api'
import toast from 'react-hot-toast'
import Link from 'next/link'
import MainNavigation from '@/components/layout/MainNavigation'
import { 
  DocumentIcon, 
  PlusIcon,
  PencilIcon,
  TrashIcon,
  CloudArrowUpIcon,
  CalendarIcon,
  BriefcaseIcon
} from '@heroicons/react/24/outline'

interface Resume {
  id: number
  title: string
  content: {
    job_application?: {
      company?: string
      position?: string
      jd?: string
    }
    personal_info?: any
    education?: any
    work_experience?: any
    skills?: any
    projects?: any
    [key: string]: any
  }
  original_filename?: string
  created_at: string
  updated_at?: string
}

export default function DashboardPage() {
  const { user, isAuthenticated, isLoading, logout } = useAuth()
  const router = useRouter()
  const [mounted, setMounted] = useState(false)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [resumes, setResumes] = useState<Resume[]>([])
  const [resumesLoading, setResumesLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newResumeTitle, setNewResumeTitle] = useState('')
  const [creating, setCreating] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  useEffect(() => {
    if (mounted && isAuthenticated) {
      fetchResumes()
    }
  }, [mounted, isAuthenticated])

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    // 检查文件类型
    const allowedTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
    if (!allowedTypes.includes(file.type)) {
      toast.error('请上传 PDF、Word 或 TXT 格式的文件')
      return
    }

    // 检查文件大小 (5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast.error('文件大小不能超过 5MB')
      return
    }

    setUploadLoading(true)
    
    try {
      toast.loading('正在上传和解析简历...', { id: 'upload' })
      
      const result = await resumeApi.uploadResume(file)
      
      // 检查解析质量并提供相应反馈
      const parsingQuality = result.content?.parsing_quality || 0
      const parsingMethod = result.content?.parsing_method || 'unknown'
      
      console.log('Upload result:', result)
      console.log('Parsing quality:', parsingQuality)
      console.log('Parsing method:', parsingMethod)
      
      if (parsingMethod === 'fallback' || parsingQuality === 0) {
        toast.success('简历上传成功，但AI解析失败，请手动编辑简历信息', { 
          id: 'upload',
          duration: 5000
        })
      } else if (parsingQuality < 0.3) {
        toast.success(`简历上传成功，但解析质量较低(${Math.round(parsingQuality * 100)}%)，建议检查并完善信息`, { 
          id: 'upload',
          duration: 5000 
        })
      } else {
        toast.success(`简历上传并解析成功！解析质量: ${Math.round(parsingQuality * 100)}%`, { 
          id: 'upload' 
        })
      }
      
      // 刷新简历列表
      await fetchResumes()
      
    } catch (error: any) {
      console.error('Upload error:', error)
      const errorMessage = error.response?.data?.detail || '上传失败，请重试'
      toast.error(errorMessage, { id: 'upload' })
    } finally {
      setUploadLoading(false)
      // 清空文件输入
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleDeleteResume = async (resumeId: number, title: string) => {
    if (!confirm(`确定要删除简历 "${title}" 吗？此操作无法撤销。`)) {
      return
    }

    try {
      toast.loading('正在删除简历...', { id: 'delete' })
      
      // 调用删除API
      await resumeApi.deleteResume(resumeId)
      
      // 从本地状态中移除
      setResumes(prev => prev.filter(resume => resume.id !== resumeId))
      
      toast.success('简历已删除', { id: 'delete' })
    } catch (error: any) {
      console.error('Delete error:', error)
      const errorMessage = error.response?.data?.detail || '删除失败，请重试'
      toast.error(errorMessage, { id: 'delete' })
    }
  }

  // 处理新建简历
  const handleCreateResume = () => {
    setShowCreateModal(true)
    setNewResumeTitle('')
  }

  // 确认创建简历
  const handleConfirmCreate = async () => {
    if (!newResumeTitle.trim()) {
      toast.error('请输入简历标题')
      return
    }

    setCreating(true)
    try {
      toast.loading('正在创建简历...', { id: 'create' })
      
      // 创建空白简历模板
      const emptyResumeContent = {
        job_application: {
          company: '',
          position: '',
          jd: ''
        },
        personal_info: {
          name: '',
          email: '',
          phone: '',
          position: '',
          github: ''
        },
        education: [],
        work_experience: [],
        skills: [],
        projects: []
      }

      // 调用创建API
      const newResume = await resumeApi.createResume({
        title: newResumeTitle.trim(),
        content: emptyResumeContent
      })
      
      toast.success('简历创建成功！', { id: 'create' })
      
      // 关闭弹窗
      setShowCreateModal(false)
      setNewResumeTitle('')
      
      // 跳转到编辑页面
      router.push(`/resume/${newResume.id}/edit`)
      
    } catch (error: any) {
      console.error('Create error:', error)
      const errorMessage = error.response?.data?.detail || '创建失败，请重试'
      toast.error(errorMessage, { id: 'create' })
    } finally {
      setCreating(false)
    }
  }

  // 取消创建
  const handleCancelCreate = () => {
    setShowCreateModal(false)
    setNewResumeTitle('')
  }

  const formatDate = (dateString: string) => {
    // 如果日期字符串没有时区信息，说明是UTC时间，需要添加Z后缀
    const normalizedDateString = dateString.includes('T') && !dateString.includes('Z') && !dateString.includes('+') 
      ? dateString + 'Z' 
      : dateString
    
    const date = new Date(normalizedDateString)
    
    // 确保使用北京时间格式化
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
                简历中心
              </h1>
              <p className="text-gray-600">
                管理您的简历文档，使用AI进行优化
              </p>
            </div>
            <div className="flex space-x-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                onChange={handleFileUpload}
                className="hidden"
              />
              <button
                onClick={handleUploadClick}
                disabled={uploadLoading}
                className="btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploadLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                    <span>上传中...</span>
                  </>
                ) : (
                  <>
                    <CloudArrowUpIcon className="w-5 h-5" />
                    <span>上传简历</span>
                  </>
                )}
              </button>
              <button 
                onClick={handleCreateResume}
                className="btn-secondary flex items-center space-x-2"
              >
                <PlusIcon className="w-5 h-5" />
                <span>新建简历</span>
              </button>
            </div>
          </div>

          {/* Resume List */}
          {resumesLoading ? (
            <div className="flex justify-center items-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              <span className="ml-3 text-gray-600">加载简历列表...</span>
            </div>
          ) : resumes.length === 0 ? (
            // Empty State
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="text-center py-12"
            >
              <DocumentIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                还没有简历
              </h3>
              <p className="text-gray-500 mb-6">
                上传您的第一份简历，开始使用AI优化功能
              </p>
              <button
                onClick={handleUploadClick}
                disabled={uploadLoading}
                className="btn-primary flex items-center space-x-2 mx-auto disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <CloudArrowUpIcon className="w-5 h-5" />
                <span>上传简历文件</span>
              </button>
            </motion.div>
          ) : (
            // Resume Grid
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {resumes.map((resume, index) => {
                return (
                  <motion.div
                    key={resume.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, delay: index * 0.1 }}
                    className="card px-6 py-5 hover:shadow-lg transition-shadow"
                  >
                    {/* Resume Header */}
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-gray-900 mb-1">
                          {resume.title}
                        </h3>
                        
                        {/* 投递信息 */}
                        <div className="flex items-center text-sm text-gray-500 mb-1">
                          <BriefcaseIcon className="w-4 h-4 mr-1" />
                          <span>
                            投递岗位: {resume.content.job_application && (
                              resume.content.job_application.company || resume.content.job_application.position
                            ) && (
                              <>
                                {resume.content.job_application.company && (
                                  <span>{resume.content.job_application.company}</span>
                                )}
                                {resume.content.job_application.company && resume.content.job_application.position && (
                                  <span className="mx-1">•</span>
                                )}
                                {resume.content.job_application.position && (
                                  <span>{resume.content.job_application.position}</span>
                                )}
                              </>
                            )}
                          </span>
                        </div>
                        
                        <div className="flex items-center text-sm text-gray-500">
                          <CalendarIcon className="w-4 h-4 mr-1" />
                          <span>
                            最后编辑: {formatDate(resume.updated_at || resume.created_at)}
                          </span>
                        </div>
                      </div>
                      
                      {/* 删除按钮 - 右上角 */}
                      <button
                        onClick={() => handleDeleteResume(resume.id, resume.title)}
                        className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors"
                        title="删除简历"
                      >
                        <TrashIcon className="w-5 h-5" />
                      </button>
                    </div>


                    {/* Action Buttons */}
                    <div className="grid grid-cols-2 gap-2">
                      <Link
                        href={`/resume/${resume.id}/edit`}
                        className="btn-primary flex items-center justify-center space-x-1 text-sm py-2"
                      >
                        <PencilIcon className="w-4 h-4" />
                        <span>编辑</span>
                      </Link>
                      <div></div>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          )}
        </motion.div>
      </main>

      {/* 创建简历弹窗 */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
            className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4"
          >
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              新建简历
            </h3>
            
            <div className="mb-4">
              <label htmlFor="resumeTitle" className="block text-sm font-medium text-gray-700 mb-2">
                简历标题
              </label>
              <input
                id="resumeTitle"
                type="text"
                value={newResumeTitle}
                onChange={(e) => setNewResumeTitle(e.target.value)}
                placeholder="请输入简历标题，如：前端工程师简历"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                autoFocus
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && !creating) {
                    handleConfirmCreate()
                  }
                }}
              />
            </div>
            
            <div className="flex justify-end space-x-3">
              <button
                onClick={handleCancelCreate}
                disabled={creating}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                取消
              </button>
              <button
                onClick={handleConfirmCreate}
                disabled={creating || !newResumeTitle.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
              >
                {creating ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>创建中...</span>
                  </>
                ) : (
                  <span>创建简历</span>
                )}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}