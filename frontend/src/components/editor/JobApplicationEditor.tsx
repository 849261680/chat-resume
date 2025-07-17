'use client'

import { motion } from 'framer-motion'
import { useState } from 'react'

interface JobApplicationData {
  company?: string
  position?: string
  jd?: string
}

interface JobApplicationEditorProps {
  data: JobApplicationData
  onChange: (data: JobApplicationData) => void
  resumeTitle?: string
  onTitleChange?: (title: string) => void
}

export default function JobApplicationEditor({ data, onChange, resumeTitle, onTitleChange }: JobApplicationEditorProps) {
  const [formData, setFormData] = useState<JobApplicationData>({
    company: data.company || '',
    position: data.position || '',
    jd: data.jd || ''
  })

  const handleInputChange = (field: keyof JobApplicationData, value: string) => {
    const newData = { ...formData, [field]: value }
    setFormData(newData)
    onChange(newData)
  }

  const handleTitleChange = (value: string) => {
    if (onTitleChange) {
      onTitleChange(value)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            简历名称
          </label>
          <input
            type="text"
            value={resumeTitle || ''}
            onChange={(e) => handleTitleChange(e.target.value)}
            placeholder="请输入简历名称"
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            目标公司
          </label>
          <input
            type="text"
            value={formData.company}
            onChange={(e) => handleInputChange('company', e.target.value)}
            placeholder="请输入目标公司名称"
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            目标岗位
          </label>
          <input
            type="text"
            value={formData.position}
            onChange={(e) => handleInputChange('position', e.target.value)}
            placeholder="请输入目标岗位名称"
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            职位描述 (JD)
          </label>
          <textarea
            value={formData.jd}
            onChange={(e) => handleInputChange('jd', e.target.value)}
            placeholder="请粘贴完整的职位描述，包括岗位职责、任职要求等信息"
            rows={12}
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
        </div>
      </div>

    </motion.div>
  )
}