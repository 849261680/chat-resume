'use client'

import { useEffect } from 'react'
import PaginatedResumePreview from './PaginatedResumePreview'

interface PersonalInfo {
  name?: string
  email?: string
  phone?: string
  position?: string
  github?: string
  linkedin?: string
  website?: string
  address?: string
}

interface Education {
  id?: number
  school: string
  major: string
  degree: string
  duration: string
  description?: string
}

interface WorkExperience {
  id?: number
  company: string
  position: string
  duration: string
  description: string
}

interface Skill {
  id?: number
  name: string
  level: string
  category: string
}

interface Project {
  id?: number
  name: string
  description: string
  technologies: string[]
  role: string
  duration: string
  github_url?: string
  demo_url?: string
  achievements: string[]
}

interface ResumeContent {
  personal_info?: PersonalInfo
  education?: Education[]
  work_experience?: WorkExperience[]
  skills?: Skill[]
  projects?: Project[]
}

interface ResumePreviewProps {
  content: ResumeContent
}

export default function ResumePreview({ content }: ResumePreviewProps) {
  // 加载打印样式
  useEffect(() => {
    // 动态加载打印样式
    const loadPrintStyles = () => {
      if (typeof document !== 'undefined') {
        const existingLink = document.getElementById('resume-print-styles')
        if (!existingLink) {
          const link = document.createElement('link')
          link.id = 'resume-print-styles'
          link.rel = 'stylesheet'
          link.href = '/styles/resume-print.css'
          document.head.appendChild(link)
        }
      }
    }

    loadPrintStyles()
  }, [])

  return (
    <div className="h-full overflow-hidden bg-gray-50 p-1">
      <PaginatedResumePreview content={content} />
    </div>
  )
}