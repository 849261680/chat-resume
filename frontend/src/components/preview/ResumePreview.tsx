'use client'

import PersonalInfoPreview from './sections/PersonalInfoPreview'
import EducationPreview from './sections/EducationPreview'
import WorkExperiencePreview from './sections/WorkExperiencePreview'
import SkillsPreview from './sections/SkillsPreview'
import ProjectsPreview from './sections/ProjectsPreview'

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
  // 检查是否有任何内容
  const hasContent = content.personal_info || 
                    (content.education && content.education.length > 0) ||
                    (content.work_experience && content.work_experience.length > 0) ||
                    (content.skills && content.skills.length > 0) ||
                    (content.projects && content.projects.length > 0)

  if (!hasContent) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        <div className="text-center">
          <div className="text-6xl mb-4">📄</div>
          <p className="text-lg font-medium mb-2">开始编辑简历</p>
          <p className="text-sm">在左侧编辑区域填写信息，实时预览将在这里显示</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-8 h-full overflow-y-auto">
      <div className="max-w-none mx-auto space-y-6">
        {/* 个人信息 */}
        <PersonalInfoPreview data={content.personal_info || {}} />
        
        {/* 教育背景 */}
        <EducationPreview data={content.education || []} />
        
        {/* 工作经验 */}
        <WorkExperiencePreview data={content.work_experience || []} />
        
        {/* 技能专长 */}
        <SkillsPreview data={content.skills || []} />
        
        {/* 项目经验 */}
        <ProjectsPreview data={content.projects || []} />
      </div>
    </div>
  )
}