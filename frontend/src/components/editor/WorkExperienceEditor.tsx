'use client'
// 用于提供 components/editor/WorkExperienceEditor.tsx 模块。

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  BriefcaseIcon,
  ChevronDownIcon,
  PlusIcon,
  TrashIcon
} from '@heroicons/react/24/outline'
import type { ResumeBullet as Bullet, WorkExperience } from '@/types/resume'
import { useTranslations } from 'next-intl'

interface WorkExperienceEditorProps {
  data: WorkExperience[]
  onChange: (data: WorkExperience[]) => void
}

// 用于标准化要点。
function normalizeBullets(work: WorkExperience): Bullet[] {
  if (work.highlights && work.highlights.length > 0) {
    return work.highlights
  }
  return [{ id: `${work.id || 'work'}_hl_0`, text: '' }]
}

/** 按内容高度撑开主要成果输入框，避免长文本被单行裁切。 */
function fitTextareaToContent(element: HTMLTextAreaElement | null) {
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${element.scrollHeight + 2}px`
}

// 用于渲染 WorkExperienceEditor 组件。
export default function WorkExperienceEditor({ data, onChange }: WorkExperienceEditorProps) {
  const [workList, setWorkList] = useState<WorkExperience[]>(Array.isArray(data) ? data : [])
  const editorRootRef = useRef<HTMLDivElement>(null)
  const t = useTranslations('resume.forms.work')
  const employmentTypes = t.raw('employmentTypes') as string[]

  useEffect(() => {
    const next = Array.isArray(data)
      ? data.map((work, index) => ({
          ...work,
          id: work.id || `work_${Date.now()}_${index}`,
          highlights: normalizeBullets(work)
        }))
      : []
    setWorkList(next)
  }, [data])

  useLayoutEffect(() => {
    const textareas = editorRootRef.current?.querySelectorAll<HTMLTextAreaElement>('[data-autogrow="work-highlight"]')
    textareas?.forEach(fitTextareaToContent)
  }, [workList])

  // 用于处理commit。
  const commit = (next: WorkExperience[]) => {
    setWorkList(next)
    onChange(next)
  }

  // 用于新增工作。
  const addWork = () => {
    commit([
      ...workList,
      {
        id: `work_${Date.now()}`,
        company: '',
        position: '',
        duration: '',
        location: '',
        employment_type: employmentTypes[0],
        highlights: [{ id: `hl_${Date.now()}`, text: '' }]
      }
    ])
  }

  // 用于删除工作。
  const removeWork = (id: string) => {
    commit(workList.filter(work => work.id !== id))
  }

  // 用于更新工作。
  const updateWork = (id: string, field: keyof WorkExperience, value: unknown) => {
    commit(workList.map(work => (
      work.id === id ? { ...work, [field]: value } : work
    )))
  }

  // 用于新增bullet。
  const addBullet = (workId: string) => {
    const work = workList.find(item => item.id === workId)
    if (!work) return
    updateWork(workId, 'highlights', [...(work.highlights || []), { id: `hl_${Date.now()}`, text: '' }])
  }

  // 用于更新bullet。
  const updateBullet = (workId: string, index: number, value: string) => {
    const work = workList.find(item => item.id === workId)
    if (!work) return
    const next = [...(work.highlights || [])]
    next[index] = { ...next[index], text: value }
    updateWork(workId, 'highlights', next)
  }

  // 用于删除bullet。
  const removeBullet = (workId: string, index: number) => {
    const work = workList.find(item => item.id === workId)
    if (!work) return
    const current = work.highlights || []
    if (current.length <= 1) return
    updateWork(workId, 'highlights', current.filter((_, itemIndex) => itemIndex !== index))
  }

  return (
    <div ref={editorRootRef} className="space-y-6">
      {workList.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <BriefcaseIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 mb-4">{t('empty')}</p>
          <button
            onClick={addWork}
            className="btn-primary flex items-center space-x-2 mx-auto"
          >
            <PlusIcon className="w-4 h-4" />
            <span>{t('addFirst')}</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {workList.map((work, index) => (
            <div key={work.id || index} className="bg-white rounded-lg p-4 border">
              <div className="flex items-center justify-end mb-1">
                {workList.length > 1 && (
                  <button
                    onClick={() => removeWork(work.id!)}
                    className="text-gray-400 hover:text-gray-600 p-1 transition-colors"
                    title={t('delete')}
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('company')}
                    </label>
                    <input
                      type="text"
                      value={work.company ?? ''}
                      onChange={(e) => updateWork(work.id!, 'company', e.target.value)}
                      placeholder={t('companyPlaceholder')}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('position')}
                    </label>
                    <input
                      type="text"
                      value={work.position ?? ''}
                      onChange={(e) => updateWork(work.id!, 'position', e.target.value)}
                      placeholder={t('positionPlaceholder')}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('duration')}
                    </label>
                    <input
                      type="text"
                      value={work.duration ?? ''}
                      onChange={(e) => updateWork(work.id!, 'duration', e.target.value)}
                      placeholder="2022.07 - 2024.06"
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('location')}
                    </label>
                    <input
                      type="text"
                      value={work.location || ''}
                      onChange={(e) => updateWork(work.id!, 'location', e.target.value)}
                      placeholder={t('locationPlaceholder')}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('employmentType')}
                    </label>
                    <div className="relative">
                      <select
                        value={work.employment_type || employmentTypes[0]}
                        onChange={(e) => updateWork(work.id!, 'employment_type', e.target.value)}
                        className="w-full appearance-none bg-white px-3 py-2 pr-10 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      >
                        {employmentTypes.map((type) => (
                          <option key={type} value={type}>{type}</option>
                        ))}
                      </select>
                      <ChevronDownIcon className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                    </div>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">
                      {t('highlights')}
                    </label>
                    <button
                      onClick={() => addBullet(work.id!)}
                      className="text-primary-600 hover:text-primary-800 text-sm flex items-center space-x-1"
                    >
                      <PlusIcon className="w-3 h-3" />
                      <span>{t('addBullet')}</span>
                    </button>
                  </div>
                  <div className="space-y-2">
                    {(work.highlights || []).map((highlight, highlightIndex) => (
                      <div key={highlight.id || highlightIndex} className="flex items-center space-x-2">
                        <textarea
                          data-autogrow="work-highlight"
                          ref={fitTextareaToContent}
                          value={highlight.text ?? ''}
                          onChange={(e) => {
                            updateBullet(work.id!, highlightIndex, e.target.value)
                            fitTextareaToContent(e.currentTarget)
                          }}
                          placeholder={t('highlightPlaceholder')}
                          rows={1}
                          className="min-h-[42px] flex-1 overflow-hidden px-3 py-2 text-sm leading-relaxed border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none [field-sizing:content]"
                        />
                        {(work.highlights || []).length > 1 && (
                          <button
                            onClick={() => removeBullet(work.id!, highlightIndex)}
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
            </div>
          ))}
          <button
            onClick={addWork}
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
