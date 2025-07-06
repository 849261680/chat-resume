'use client'

import { useState, useEffect } from 'react'
import { 
  BriefcaseIcon,
  PlusIcon,
  TrashIcon
} from '@heroicons/react/24/outline'

interface WorkExperience {
  id?: number
  company: string
  position: string
  duration: string
  description: string
  location?: string
  employment_type?: string
}

interface WorkExperienceEditorProps {
  data: WorkExperience[]
  onChange: (data: WorkExperience[]) => void
}

export default function WorkExperienceEditor({ data, onChange }: WorkExperienceEditorProps) {
  const [workList, setWorkList] = useState<WorkExperience[]>(data || [])

  useEffect(() => {
    setWorkList(data || [])
  }, [data])

  const addWork = () => {
    const newWork: WorkExperience = {
      id: Date.now(),
      company: '',
      position: '',
      duration: '',
      description: '',
      location: '',
      employment_type: '全职'
    }
    const newList = [...workList, newWork]
    setWorkList(newList)
    onChange(newList)
  }

  const removeWork = (id: number) => {
    const newList = workList.filter(work => work.id !== id)
    setWorkList(newList)
    onChange(newList)
  }

  const updateWork = (id: number, field: keyof WorkExperience, value: string) => {
    const newList = workList.map(work => 
      work.id === id ? { ...work, [field]: value } : work
    )
    setWorkList(newList)
    onChange(newList)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center">
          <BriefcaseIcon className="w-5 h-5 mr-2" />
          工作经验
        </h3>
        <button
          onClick={addWork}
          className="btn-secondary flex items-center space-x-1 text-sm"
        >
          <PlusIcon className="w-4 h-4" />
          <span>添加工作经验</span>
        </button>
      </div>

      {workList.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <BriefcaseIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 mb-4">还没有添加工作经验</p>
          <button
            onClick={addWork}
            className="btn-primary flex items-center space-x-2 mx-auto"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加第一个工作经验</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {workList.map((work, index) => (
            <div key={work.id || index} className="bg-gray-50 rounded-lg p-4 border">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-medium text-gray-900">工作经验 {index + 1}</h4>
                {workList.length > 1 && (
                  <button
                    onClick={() => removeWork(work.id!)}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="删除此工作经验"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* 公司名称 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      公司名称 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={work.company}
                      onChange={(e) => updateWork(work.id!, 'company', e.target.value)}
                      placeholder="腾讯科技"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  {/* 职位 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      职位 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={work.position}
                      onChange={(e) => updateWork(work.id!, 'position', e.target.value)}
                      placeholder="软件工程师"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  {/* 工作时间 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      工作时间 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={work.duration}
                      onChange={(e) => updateWork(work.id!, 'duration', e.target.value)}
                      placeholder="2022.07 - 2024.06"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  {/* 工作地点 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      工作地点
                    </label>
                    <input
                      type="text"
                      value={work.location || ''}
                      onChange={(e) => updateWork(work.id!, 'location', e.target.value)}
                      placeholder="北京"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  {/* 雇佣类型 */}
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      雇佣类型
                    </label>
                    <select
                      value={work.employment_type || '全职'}
                      onChange={(e) => updateWork(work.id!, 'employment_type', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    >
                      <option value="全职">全职</option>
                      <option value="兼职">兼职</option>
                      <option value="实习">实习</option>
                      <option value="自由职业">自由职业</option>
                      <option value="合同工">合同工</option>
                    </select>
                  </div>
                </div>

                {/* 工作描述 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    工作描述 <span className="text-red-500">*</span>
                  </label>
                  <div className="mb-2">
                    <p className="text-xs text-gray-500">
                      💡 建议包含：具体职责、使用的技术栈、项目成果、数据指标等
                    </p>
                  </div>
                  <textarea
                    value={work.description}
                    onChange={(e) => updateWork(work.id!, 'description', e.target.value)}
                    placeholder="• 负责后端系统开发，使用Python/Django框架&#10;• 参与微服务架构设计，提升系统性能30%&#10;• 负责数据库优化，查询效率提升50%&#10;• 参与代码审查和技术方案设计"
                    rows={6}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                  />
                  <div className="mt-1 text-xs text-gray-500">
                    建议使用 • 开头的列表格式，突出关键成果
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}