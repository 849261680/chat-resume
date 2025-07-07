'use client'

import { motion } from 'framer-motion'
import { useEffect, useState, useRef } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { resumeApi } from '@/lib/api'
import toast from 'react-hot-toast'
import Link from 'next/link'
import { 
  UserIcon, 
  DocumentIcon, 
  PlusIcon,
  PencilIcon,
  ChatBubbleLeftRightIcon,
  TrashIcon,
  CloudArrowUpIcon,
  CalendarIcon
} from '@heroicons/react/24/outline'

interface Resume {
  id: number
  title: string
  content: any
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

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getResumeCompleteness = (content: any) => {
    const sections = ['personal_info', 'education', 'work_experience', 'skills']
    const completed = sections.filter(section => {
      const sectionData = content[section]
      if (Array.isArray(sectionData)) {
        return sectionData.length > 0
      }
      return sectionData && Object.keys(sectionData).length > 0
    })
    return {
      completed: completed.length,
      total: sections.length,
      sections: {
        personal_info: content.personal_info && Object.keys(content.personal_info).length > 0,
        education: content.education && content.education.length > 0,
        work_experience: content.work_experience && content.work_experience.length > 0,
        skills: content.skills && content.skills.length > 0
      }
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
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center">
                <UserIcon className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-gray-900">Chat Resume</span>
            </div>
            
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">
                欢迎, {user?.full_name || user?.email}
              </span>
              <button
                onClick={logout}
                className="btn-secondary"
              >
                退出登录
              </button>
            </div>
          </div>
        </div>
      </header>

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
                我的简历
              </h1>
              <p className="text-gray-600">
                管理您的简历，使用AI优化，并进行模拟面试
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
              <button className="btn-secondary flex items-center space-x-2">
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
                const completeness = getResumeCompleteness(resume.content)
                return (
                  <motion.div
                    key={resume.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, delay: index * 0.1 }}
                    className="card p-6 hover:shadow-lg transition-shadow"
                  >
                    {/* Resume Header */}
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-gray-900 mb-1">
                          {resume.title}
                        </h3>
                        <div className="flex items-center text-sm text-gray-500">
                          <CalendarIcon className="w-4 h-4 mr-1" />
                          <span>
                            最后编辑: {formatDate(resume.updated_at || resume.created_at)}
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-medium text-gray-900">
                          {completeness.completed}/{completeness.total}
                        </div>
                        <div className="text-xs text-gray-500">完成度</div>
                      </div>
                    </div>

                    {/* Completeness Indicators */}
                    <div className="flex items-center space-x-4 text-sm mb-6">
                      <div className="flex items-center">
                        <span className="text-gray-600">个人信息</span>
                        <span className={`ml-1 ${completeness.sections.personal_info ? 'text-green-600' : 'text-gray-400'}`}>
                          {completeness.sections.personal_info ? '✓' : '○'}
                        </span>
                      </div>
                      <div className="flex items-center">
                        <span className="text-gray-600">工作经验</span>
                        <span className={`ml-1 ${completeness.sections.work_experience ? 'text-green-600' : 'text-orange-500'}`}>
                          {completeness.sections.work_experience ? '✓' : '⚠️'}
                        </span>
                      </div>
                      <div className="flex items-center">
                        <span className="text-gray-600">教育</span>
                        <span className={`ml-1 ${completeness.sections.education ? 'text-green-600' : 'text-gray-400'}`}>
                          {completeness.sections.education ? '✓' : '○'}
                        </span>
                      </div>
                      <div className="flex items-center">
                        <span className="text-gray-600">技能</span>
                        <span className={`ml-1 ${completeness.sections.skills ? 'text-green-600' : 'text-gray-400'}`}>
                          {completeness.sections.skills ? '✓' : '○'}
                        </span>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex space-x-2">
                      <Link
                        href={`/resume/${resume.id}/edit`}
                        className="btn-primary flex-1 flex items-center justify-center space-x-1 text-sm"
                      >
                        <PencilIcon className="w-4 h-4" />
                        <span>编辑</span>
                      </Link>
                      <Link
                        href={`/resume/${resume.id}/interview`}
                        className="btn-secondary flex-1 flex items-center justify-center space-x-1 text-sm"
                      >
                        <ChatBubbleLeftRightIcon className="w-4 h-4" />
                        <span>面试</span>
                      </Link>
                      <button
                        onClick={() => handleDeleteResume(resume.id, resume.title)}
                        className="btn-danger flex items-center justify-center px-3"
                        title="删除简历"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}