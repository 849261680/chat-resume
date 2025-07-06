'use client'

import { useState, useEffect } from 'react'
import { 
  AcademicCapIcon,
  PlusIcon,
  TrashIcon
} from '@heroicons/react/24/outline'

interface Education {
  id?: number
  school: string
  major: string
  degree: string
  duration: string
  description?: string
  gpa?: string
}

interface EducationEditorProps {
  data: Education[]
  onChange: (data: Education[]) => void
}

export default function EducationEditor({ data, onChange }: EducationEditorProps) {
  const [educationList, setEducationList] = useState<Education[]>(data || [])

  useEffect(() => {
    setEducationList(data || [])
  }, [data])

  const addEducation = () => {
    const newEducation: Education = {
      id: Date.now(),
      school: '',
      major: '',
      degree: '',
      duration: '',
      description: '',
      gpa: ''
    }
    const newList = [...educationList, newEducation]
    setEducationList(newList)
    onChange(newList)
  }

  const removeEducation = (id: number) => {
    const newList = educationList.filter(edu => edu.id !== id)
    setEducationList(newList)
    onChange(newList)
  }

  const updateEducation = (id: number, field: keyof Education, value: string) => {
    const newList = educationList.map(edu => 
      edu.id === id ? { ...edu, [field]: value } : edu
    )
    setEducationList(newList)
    onChange(newList)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center">
          <AcademicCapIcon className="w-5 h-5 mr-2" />
          教育经历
        </h3>
        <button
          onClick={addEducation}
          className="btn-secondary flex items-center space-x-1 text-sm"
        >
          <PlusIcon className="w-4 h-4" />
          <span>添加教育经历</span>
        </button>
      </div>

      {educationList.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <AcademicCapIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 mb-4">还没有添加教育经历</p>
          <button
            onClick={addEducation}
            className="btn-primary flex items-center space-x-2 mx-auto"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加第一个教育经历</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {educationList.map((education, index) => (
            <div key={education.id || index} className="bg-gray-50 rounded-lg p-4 border">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-medium text-gray-900">教育经历 {index + 1}</h4>
                {educationList.length > 1 && (
                  <button
                    onClick={() => removeEducation(education.id!)}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="删除此教育经历"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* 学校名称 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    学校名称 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={education.school}
                    onChange={(e) => updateEducation(education.id!, 'school', e.target.value)}
                    placeholder="北京大学"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                {/* 专业 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    专业 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={education.major}
                    onChange={(e) => updateEducation(education.id!, 'major', e.target.value)}
                    placeholder="计算机科学与技术"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                {/* 学历 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    学历 <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={education.degree}
                    onChange={(e) => updateEducation(education.id!, 'degree', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  >
                    <option value="">请选择学历</option>
                    <option value="博士">博士</option>
                    <option value="硕士">硕士</option>
                    <option value="本科">本科</option>
                    <option value="专科">专科</option>
                    <option value="高中">高中</option>
                    <option value="中专">中专</option>
                  </select>
                </div>

                {/* 就读时间 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    就读时间 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={education.duration}
                    onChange={(e) => updateEducation(education.id!, 'duration', e.target.value)}
                    placeholder="2018.09 - 2022.06"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                {/* GPA */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    GPA (可选)
                  </label>
                  <input
                    type="text"
                    value={education.gpa || ''}
                    onChange={(e) => updateEducation(education.id!, 'gpa', e.target.value)}
                    placeholder="3.8/4.0"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              </div>

              {/* 描述 */}
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  相关描述 (可选)
                </label>
                <textarea
                  value={education.description || ''}
                  onChange={(e) => updateEducation(education.id!, 'description', e.target.value)}
                  placeholder="主要课程、获奖经历、社团活动等..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}