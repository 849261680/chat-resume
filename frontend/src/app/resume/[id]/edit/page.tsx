'use client'

import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { resumeApi } from '@/lib/api'
import toast from 'react-hot-toast'
import Link from 'next/link'
import { 
  ArrowLeftIcon,
  EyeIcon,
  CheckIcon
} from '@heroicons/react/24/outline'
import PersonalInfoEditor from '@/components/editor/PersonalInfoEditor'
import EducationEditor from '@/components/editor/EducationEditor'
import WorkExperienceEditor from '@/components/editor/WorkExperienceEditor'
import SkillsEditor from '@/components/editor/SkillsEditor'
import ProjectsEditor from '@/components/editor/ProjectsEditor'
import ResumePreview from '@/components/preview/ResumePreview'

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

  const resumeId = params?.id as string

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
      // TODO: 实现保存API调用
      // await resumeApi.updateResume(resume.id, { content: resume.content })
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
            返回仪表板
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
                <span>返回仪表板</span>
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
              <button className="btn-secondary flex items-center space-x-2">
                <EyeIcon className="w-4 h-4" />
                <span>预览</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-[calc(100vh-200px)]">
          {/* Left Panel - Editor */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8 }}
            className="flex flex-col"
          >
            <div className="card p-6 flex-1 overflow-hidden">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                📝 编辑区域
              </h2>
              <div className="h-full flex flex-col">
                {/* Section Tabs */}
                <div className="flex space-x-1 mb-4 bg-gray-100 p-1 rounded-lg">
                  {[
                    { key: 'personal', label: '个人信息', icon: '👤' },
                    { key: 'education', label: '教育经历', icon: '🎓' },
                    { key: 'work', label: '工作经验', icon: '💼' },
                    { key: 'skills', label: '技能', icon: '🛠️' },
                    { key: 'projects', label: '项目', icon: '📁' }
                  ].map(section => (
                    <button
                      key={section.key}
                      onClick={() => setActiveSection(section.key)}
                      className={`flex-1 flex items-center justify-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                        activeSection === section.key
                          ? 'bg-white text-primary-600 shadow-sm'
                          : 'text-gray-600 hover:text-gray-900'
                      }`}
                    >
                      <span>{section.icon}</span>
                      <span className="hidden sm:inline">{section.label}</span>
                    </button>
                  ))}
                </div>

                {/* Editor Content */}
                <div className="flex-1 overflow-y-auto">
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

          {/* Middle Panel - AI Assistant */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="flex flex-col"
          >
            <div className="card p-6 flex-1 overflow-hidden">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                🤖 AI助手
              </h2>
              <div className="h-full flex flex-col space-y-4">
                {/* JD Input */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    目标职位描述 (可选)
                  </label>
                  <textarea
                    placeholder="粘贴目标职位JD，获取更精准的优化建议..."
                    className="w-full p-3 border border-gray-300 rounded-lg text-sm resize-none"
                    rows={3}
                  />
                  <button className="mt-2 btn-primary w-full text-sm">
                    🎯 获取针对性优化建议
                  </button>
                </div>

                {/* AI Suggestions */}
                <div className="flex-1 overflow-y-auto">
                  <h3 className="font-medium text-gray-900 mb-3">✨ 实时优化建议</h3>
                  
                  <div className="space-y-3">
                    {/* Sample Suggestions */}
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-blue-900">💡 个人信息建议</span>
                        <button className="text-xs bg-blue-600 text-white px-2 py-1 rounded">
                          应用
                        </button>
                      </div>
                      <p className="text-xs text-blue-800">
                        建议添加GitHub链接展示技术能力
                      </p>
                    </div>

                    <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-green-900">💡 工作经验建议</span>
                        <button className="text-xs bg-green-600 text-white px-2 py-1 rounded">
                          应用
                        </button>
                      </div>
                      <p className="text-xs text-green-800">
                        建议增加具体项目和技术栈描述
                      </p>
                      <div className="mt-2 text-xs text-green-700 bg-green-100 p-2 rounded">
                        <strong>预览:</strong> "负责后端开发..." → "负责后端开发，使用Python/Django..."
                      </div>
                    </div>

                    <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-orange-900">💡 技能建议</span>
                        <button className="text-xs bg-orange-600 text-white px-2 py-1 rounded">
                          应用
                        </button>
                      </div>
                      <p className="text-xs text-orange-800">
                        建议添加Docker、Kubernetes等容器化技术
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t">
                    <button className="btn-primary w-full text-sm">
                      ✅ 应用所有建议
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
            className="flex flex-col"
          >
            <div className="card p-6 flex-1 overflow-hidden">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                👁️ 实时预览
              </h2>
              <div className="h-full overflow-y-auto">
                <ResumePreview content={resume.content} />
              </div>
            </div>
          </motion.div>
        </div>
      </main>
    </div>
  )
}