'use client'

import { useState, useEffect } from 'react'
import { 
  UserIcon, 
  EnvelopeIcon, 
  PhoneIcon,
  LinkIcon,
  BriefcaseIcon
} from '@heroicons/react/24/outline'

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

interface PersonalInfoEditorProps {
  data: PersonalInfo
  onChange: (data: PersonalInfo) => void
}

export default function PersonalInfoEditor({ data, onChange }: PersonalInfoEditorProps) {
  const [formData, setFormData] = useState<PersonalInfo>(data || {})

  useEffect(() => {
    setFormData(data || {})
  }, [data])

  const handleChange = (field: keyof PersonalInfo, value: string) => {
    const newData = { ...formData, [field]: value }
    setFormData(newData)
    onChange(newData)
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <UserIcon className="w-5 h-5 mr-2" />
          个人信息
        </h3>
      </div>

      <div className="space-y-4">
        {/* 姓名 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            姓名 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={formData.name || ''}
            onChange={(e) => handleChange('name', e.target.value)}
            placeholder="请输入您的姓名"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        </div>

        {/* 邮箱 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            邮箱 <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <EnvelopeIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="email"
              value={formData.email || ''}
              onChange={(e) => handleChange('email', e.target.value)}
              placeholder="your@email.com"
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* 手机号 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            手机号 <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <PhoneIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="tel"
              value={formData.phone || ''}
              onChange={(e) => handleChange('phone', e.target.value)}
              placeholder="138-0000-0000"
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* 期望职位 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            期望职位
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <BriefcaseIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              value={formData.position || ''}
              onChange={(e) => handleChange('position', e.target.value)}
              placeholder="软件工程师"
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* GitHub */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            GitHub
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <LinkIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="url"
              value={formData.github || ''}
              onChange={(e) => handleChange('github', e.target.value)}
              placeholder="https://github.com/yourusername"
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* LinkedIn */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            LinkedIn
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <LinkIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="url"
              value={formData.linkedin || ''}
              onChange={(e) => handleChange('linkedin', e.target.value)}
              placeholder="https://linkedin.com/in/yourusername"
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* 个人网站 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            个人网站
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <LinkIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="url"
              value={formData.website || ''}
              onChange={(e) => handleChange('website', e.target.value)}
              placeholder="https://yourwebsite.com"
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* 地址 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            居住地址
          </label>
          <input
            type="text"
            value={formData.address || ''}
            onChange={(e) => handleChange('address', e.target.value)}
            placeholder="北京市朝阳区"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        </div>
      </div>
    </div>
  )
}