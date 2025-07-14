'use client'

import { useState } from 'react'
import { ChevronDownIcon } from '@heroicons/react/24/outline'

interface InterviewerProfile {
  id: string
  name: string
  title: string
  company: string
  style: string
  description: string
  avatar: string
  color: string
}

const interviewerProfiles: InterviewerProfile[] = [
  {
    id: 'ai_tech',
    name: 'AI面试官',
    title: '技术面试官',
    company: '模拟科技',
    style: '专业严谨',
    description: '专注技术深度，注重逻辑思维和解决问题的能力',
    avatar: 'AI',
    color: 'from-blue-500 to-indigo-600'
  },
  {
    id: 'hr_friendly',
    name: '李雪梅',
    title: 'HR总监',
    company: '创新企业',
    style: '亲切友善',
    description: '关注沟通能力和团队协作，营造轻松的面试氛围',
    avatar: '李',
    color: 'from-green-500 to-emerald-600'
  },
  {
    id: 'senior_dev',
    name: '王技术',
    title: '高级开发经理',
    company: '独角兽公司',
    style: '实战导向',
    description: '重视项目经验和实际应用，喜欢深入技术细节',
    avatar: '王',
    color: 'from-purple-500 to-violet-600'
  },
  {
    id: 'startup_cto',
    name: '张创新',
    title: 'CTO',
    company: '创业公司',
    style: '挑战思维',
    description: '关注创新思维和解决复杂问题的能力，节奏较快',
    avatar: '张',
    color: 'from-orange-500 to-red-600'
  }
]

interface InterviewerAvatarProps {
  selectedInterviewer?: InterviewerProfile
  onSelect?: (interviewer: InterviewerProfile) => void
  showSelector?: boolean
}

export default function InterviewerAvatar({ 
  selectedInterviewer = interviewerProfiles[0], 
  onSelect,
  showSelector = false 
}: InterviewerAvatarProps) {
  const [isOpen, setIsOpen] = useState(false)

  const handleSelect = (interviewer: InterviewerProfile) => {
    onSelect?.(interviewer)
    setIsOpen(false)
  }

  return (
    <div className="relative">
      <div className="flex items-center space-x-3">
        {/* 头像 */}
        <div className={`w-12 h-12 bg-gradient-to-br ${selectedInterviewer.color} rounded-full flex items-center justify-center text-white font-semibold text-lg shadow-lg`}>
          {selectedInterviewer.avatar}
        </div>
        
        {/* 信息 */}
        <div className="flex-1">
          <div className="flex items-center space-x-2">
            <h3 className="font-semibold text-gray-900">{selectedInterviewer.name}</h3>
            {showSelector && (
              <button
                onClick={() => setIsOpen(!isOpen)}
                className="p-1 hover:bg-gray-100 rounded transition-colors"
                title="更换面试官"
              >
                <ChevronDownIcon className="w-4 h-4 text-gray-500" />
              </button>
            )}
          </div>
          <p className="text-sm text-gray-600">
            {selectedInterviewer.title} | {selectedInterviewer.company}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {selectedInterviewer.style} · {selectedInterviewer.description}
          </p>
        </div>
      </div>

      {/* 面试官选择下拉菜单 */}
      {isOpen && showSelector && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-lg shadow-lg border border-gray-200 z-10 max-h-80 overflow-y-auto">
          <div className="p-3 border-b border-gray-100">
            <h4 className="font-medium text-gray-900 text-sm">选择面试官类型</h4>
            <p className="text-xs text-gray-500 mt-1">不同的面试官有不同的提问风格</p>
          </div>
          
          <div className="p-2">
            {interviewerProfiles.map((interviewer) => (
              <button
                key={interviewer.id}
                onClick={() => handleSelect(interviewer)}
                className={`w-full p-3 rounded-lg text-left transition-colors ${
                  selectedInterviewer.id === interviewer.id
                    ? 'bg-blue-50 border border-blue-200'
                    : 'hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <div className={`w-10 h-10 bg-gradient-to-br ${interviewer.color} rounded-full flex items-center justify-center text-white font-medium text-sm`}>
                    {interviewer.avatar}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-sm text-gray-900">{interviewer.name}</span>
                      <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded">
                        {interviewer.style}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 mt-1">{interviewer.title} | {interviewer.company}</p>
                    <p className="text-xs text-gray-500 mt-1">{interviewer.description}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export { interviewerProfiles }
export type { InterviewerProfile }