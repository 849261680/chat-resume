'use client'
// 用于提供 components/editor/EducationEditor.tsx 模块。

import { useState, useEffect, useLayoutEffect, useRef } from 'react'
import {
  AcademicCapIcon,
  ChevronDownIcon,
  PlusIcon,
  TrashIcon
} from '@heroicons/react/24/outline'
import type { Education } from '@/types/resume'
import { useTranslations } from 'next-intl'

interface EducationEditorProps {
  data: Education[]
  onChange: (data: Education[]) => void
}

/** 按内容高度撑开教育要点输入框，避免长课程列表被单行裁切。 */
function fitTextareaToContent(element: HTMLTextAreaElement | null) {
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${element.scrollHeight + 2}px`
}

// 用于把可选字段转换成受控表单需要的字符串值。
function inputValue(value: string | undefined) {
  return value ?? ''
}

// 用于渲染 EducationEditor 组件。
export default function EducationEditor({ data, onChange }: EducationEditorProps) {
  const [educationList, setEducationList] = useState<Education[]>(Array.isArray(data) ? data : [])
  const editorRootRef = useRef<HTMLDivElement>(null)
  const t = useTranslations('resume.forms.education')
  const degrees = t.raw('degrees') as string[]

  useEffect(() => {
    setEducationList(Array.isArray(data) ? data : [])
  }, [data])

  useLayoutEffect(() => {
    const textareas = editorRootRef.current?.querySelectorAll<HTMLTextAreaElement>('[data-autogrow="education-highlight"]')
    textareas?.forEach(fitTextareaToContent)
  }, [educationList])

  // 用于处理commit。
  const commit = (next: Education[]) => {
    setEducationList(next)
    onChange(next.map(({ description: _description, ...education }) => education))
  }

  // 用于新增教育经历。
  const addEducation = () => {
    const newEducation: Education = {
      id: `edu_${Date.now()}`,
      school: '',
      major: '',
      degree: '',
      duration: '',
      highlights: [{ id: `edu_hl_${Date.now()}`, text: '' }],
      gpa: ''
    }
    commit([...educationList, newEducation])
  }

  // 用于删除教育经历。
  const removeEducation = (id: string) => {
    commit(educationList.filter(edu => edu.id !== id))
  }

  // 用于更新教育经历。
  const updateEducation = (id: string, field: keyof Education, value: string) => {
    const newList = educationList.map(edu =>
      edu.id === id ? { ...edu, [field]: value } : edu
    )
    commit(newList)
  }

  // 用于新增bullet。
  const addBullet = (educationId: string) => {
    const education = educationList.find(item => item.id === educationId)
    if (!education) return
    const next = [...(education.highlights || []), { id: `edu_hl_${Date.now()}`, text: '' }]
    updateEducationList(
      educationList.map(item => item.id === educationId ? { ...item, highlights: next } : item)
    )
  }

  // 用于更新bullet。
  const updateBullet = (educationId: string, index: number, value: string) => {
    const education = educationList.find(item => item.id === educationId)
    if (!education) return
    const next = [...(education.highlights || [])]
    next[index] = { ...next[index], text: value }
    updateEducationList(
      educationList.map(item => item.id === educationId ? { ...item, highlights: next } : item)
    )
  }

  // 用于删除bullet。
  const removeBullet = (educationId: string, index: number) => {
    const education = educationList.find(item => item.id === educationId)
    if (!education) return
    const current = education.highlights || []
    if (current.length <= 1) return
    updateEducationList(
      educationList.map(item =>
        item.id === educationId
          ? { ...item, highlights: current.filter((_, itemIndex) => itemIndex !== index) }
          : item
      )
    )
  }

  // 用于更新教育经历list。
  const updateEducationList = (next: Education[]) => {
    commit(next)
  }

  return (
    <div ref={editorRootRef} className="space-y-6">
      {educationList.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <AcademicCapIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 mb-4">{t('empty')}</p>
          <button
            onClick={addEducation}
            className="btn-primary flex items-center space-x-2 mx-auto"
          >
            <PlusIcon className="w-4 h-4" />
            <span>{t('addFirst')}</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {educationList.map((education, index) => (
            <div key={education.id || index} className="bg-white rounded-lg p-4 border">
              <div className="flex items-center justify-end mb-1">
                {educationList.length > 1 && (
                  <button
                    onClick={() => removeEducation(education.id!)}
                    className="text-gray-400 hover:text-gray-600 p-1 transition-colors"
                    title={t('delete')}
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* 学校名称 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('school')}
                  </label>
                  <input
                    type="text"
                    value={inputValue(education.school)}
                    onChange={(e) => updateEducation(education.id!, 'school', e.target.value)}
                    placeholder={t('schoolPlaceholder')}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                {/* 专业 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('major')}
                  </label>
                  <input
                    type="text"
                    value={inputValue(education.major)}
                    onChange={(e) => updateEducation(education.id!, 'major', e.target.value)}
                    placeholder={t('majorPlaceholder')}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                {/* 学历 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('degree')}
                  </label>
                  <div className="relative">
                    <select
                      value={inputValue(education.degree)}
                      onChange={(e) => updateEducation(education.id!, 'degree', e.target.value)}
                      className="w-full appearance-none bg-white px-3 py-2 pr-10 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    >
                      <option value="">{t('selectDegree')}</option>
                      {degrees.map((degree) => (
                        <option key={degree} value={degree}>{degree}</option>
                      ))}
                    </select>
                    <ChevronDownIcon className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                  </div>
                </div>

                {/* 就读时间 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('duration')}
                  </label>
                  <input
                    type="text"
                    value={inputValue(education.duration)}
                    onChange={(e) => updateEducation(education.id!, 'duration', e.target.value)}
                    placeholder="2018.09 - 2022.06"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                {/* GPA */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('gpa')}
                  </label>
                  <input
                    type="text"
                    value={inputValue(education.gpa)}
                    onChange={(e) => updateEducation(education.id!, 'gpa', e.target.value)}
                    placeholder="3.8/4.0"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div className="mt-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-gray-700">
                    {t('highlights')}
                  </label>
                  <button
                    onClick={() => addBullet(education.id!)}
                    className="text-primary-600 hover:text-primary-800 text-sm flex items-center space-x-1"
                  >
                    <PlusIcon className="w-3 h-3" />
                    <span>{t('addBullet')}</span>
                  </button>
                </div>
                <div className="space-y-2">
                  {(education.highlights || [{ id: `edu_hl_${education.id || '0'}`, text: '' }]).map((highlight, highlightIndex) => (
                    <div key={highlight.id || highlightIndex} className="flex items-center space-x-2">
                      <textarea
                        data-autogrow="education-highlight"
                        ref={fitTextareaToContent}
                        value={inputValue(highlight.text)}
                        onChange={(e) => {
                          updateBullet(education.id!, highlightIndex, e.target.value)
                          fitTextareaToContent(e.currentTarget)
                        }}
                        placeholder={t('highlightPlaceholder')}
                        rows={1}
                        className="min-h-[42px] flex-1 overflow-hidden px-3 py-2 text-sm leading-relaxed border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none [field-sizing:content]"
                      />
                      {(education.highlights || []).length > 1 && (
                        <button
                          onClick={() => removeBullet(education.id!, highlightIndex)}
                          className="text-gray-400 hover:text-gray-600 p-1 transition-colors"
                          title={t('deleteBullet')}
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
          <button
            onClick={addEducation}
            className="w-full py-4 rounded-lg border-2 border-dashed border-gray-300 text-gray-500 hover:text-primary-600 hover:border-primary-400 transition-colors flex items-center justify-center space-x-2"
          >
            <PlusIcon className="w-4 h-4" />
            <span>{t('add')}</span>
          </button>
        </div>
      )}
    </div>
  )
}
