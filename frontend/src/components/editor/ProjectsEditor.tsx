'use client'
// 用于提供 components/editor/ProjectsEditor.tsx 模块。

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  FolderIcon,
  PlusIcon,
  TrashIcon,
  LinkIcon,
  CalendarIcon,
  SparklesIcon
} from '@heroicons/react/24/outline'
import type { Project, ResumeBullet as Bullet } from '@/types/resume'
import { useTranslations } from 'next-intl'

interface ProjectsEditorProps {
  data: Project[]
  onChange: (data: Project[]) => void
  variant?: 'project' | 'openSource'
  onGenerateStory?: (project: Project) => void
  storyGenerationDisabled?: boolean
}

// 用于标准化要点。
function normalizeBullets(project: Project): Bullet[] {
  if (project.highlights && project.highlights.length > 0) {
    return project.highlights
  }
  return [{ id: `${project.id || 'proj'}_hl_0`, text: '' }]
}

/** 按内容高度撑开项目长文本输入框，避免简介和成果被单行裁切。 */
function fitTextareaToContent(element: HTMLTextAreaElement | null) {
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${element.scrollHeight + 2}px`
}

// 用于渲染 ProjectsEditor 组件。
export default function ProjectsEditor({
  data,
  onChange,
  variant = 'project',
  onGenerateStory,
  storyGenerationDisabled = false,
}: ProjectsEditorProps) {
  const [projectsList, setProjectsList] = useState<Project[]>(Array.isArray(data) ? data : [])
  const editorRootRef = useRef<HTMLDivElement>(null)
  const projectT = useTranslations('resume.forms.project')
  const openSourceT = useTranslations('resume.forms.openSource')
  const t = variant === 'openSource' ? openSourceT : projectT

  useEffect(() => {
    const next = Array.isArray(data)
      ? data.map((project, index) => ({
          ...project,
          id: project.id || `proj_${Date.now()}_${index}`,
          overview: project.overview || '',
          highlights: normalizeBullets(project)
        }))
      : []
    setProjectsList(next)
  }, [data])

  useLayoutEffect(() => {
    const textareas = editorRootRef.current?.querySelectorAll<HTMLTextAreaElement>('[data-autogrow="project-text"]')
    textareas?.forEach(fitTextareaToContent)
  }, [projectsList])

  // 用于处理commit。
  const commit = (next: Project[]) => {
    setProjectsList(next)
    onChange(next)
  }

  // 用于新增项目。
  const addProject = () => {
    commit([
      ...projectsList,
      {
        id: `proj_${Date.now()}`,
        name: '',
        overview: '',
        role: '',
        duration: '',
        github_url: '',
        demo_url: '',
        highlights: [{ id: `hl_${Date.now()}`, text: '' }]
      }
    ])
  }

  // 用于删除项目。
  const removeProject = (id: string) => {
    commit(projectsList.filter(project => project.id !== id))
  }

  // 用于更新项目。
  const updateProject = (id: string, field: keyof Project, value: unknown) => {
    commit(projectsList.map(project => (
      project.id === id ? { ...project, [field]: value } : project
    )))
  }

  // 用于新增bullet。
  const addBullet = (projectId: string) => {
    const project = projectsList.find(item => item.id === projectId)
    if (!project) return
    updateProject(projectId, 'highlights', [
      ...(project.highlights || []),
      { id: `hl_${Date.now()}`, text: '' }
    ])
  }

  // 用于更新bullet。
  const updateBullet = (projectId: string, index: number, value: string) => {
    const project = projectsList.find(item => item.id === projectId)
    if (!project) return
    const next = [...(project.highlights || [])]
    next[index] = { ...next[index], text: value }
    updateProject(projectId, 'highlights', next)
  }

  // 用于删除bullet。
  const removeBullet = (projectId: string, index: number) => {
    const project = projectsList.find(item => item.id === projectId)
    if (!project) return
    const current = project.highlights || []
    if (current.length <= 1) return
    updateProject(projectId, 'highlights', current.filter((_, itemIndex) => itemIndex !== index))
  }

  return (
    <div ref={editorRootRef} className="space-y-6">
      {projectsList.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <FolderIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 mb-4">{t('empty')}</p>
          <button
            onClick={addProject}
            className="btn-primary flex items-center space-x-2 mx-auto"
          >
            <PlusIcon className="w-4 h-4" />
            <span>{t('addFirst')}</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {projectsList.map((project, index) => (
            <div key={project.id || index} className="bg-white rounded-lg p-6 border">
              <div className="mb-2 flex items-center justify-between gap-2">
                {onGenerateStory ? (
                  <button
                    type="button"
                    onClick={() => onGenerateStory(project)}
                    disabled={storyGenerationDisabled}
                    className="inline-flex items-center gap-1.5 rounded-full border border-primary-200 bg-primary-50 px-3 py-1.5 text-xs font-semibold text-primary-700 transition-colors hover:border-primary-300 hover:bg-primary-100 disabled:cursor-not-allowed disabled:border-gray-200 disabled:bg-gray-50 disabled:text-gray-400"
                    title={t('generateStory')}
                  >
                    <SparklesIcon className="h-3.5 w-3.5" />
                    <span>{t('generateStory')}</span>
                  </button>
                ) : (
                  <span />
                )}
                {projectsList.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeProject(project.id!)}
                    className="text-gray-400 hover:text-gray-600 p-1 transition-colors"
                    title={t('delete')}
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('name')}
                    </label>
                    <input
                      type="text"
                      value={project.name ?? ''}
                      onChange={(e) => updateProject(project.id!, 'name', e.target.value)}
                      placeholder={t('namePlaceholder')}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('duration')}
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <CalendarIcon className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="text"
                        value={project.duration ?? ''}
                        onChange={(e) => updateProject(project.id!, 'duration', e.target.value)}
                        placeholder="2023.03 - 2023.08"
                        className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('role')}
                    </label>
                    <input
                      type="text"
                      value={project.role ?? ''}
                      onChange={(e) => updateProject(project.id!, 'role', e.target.value)}
                      placeholder={t('rolePlaceholder')}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('github')}
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <LinkIcon className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="url"
                        value={project.github_url || ''}
                        onChange={(e) => updateProject(project.id!, 'github_url', e.target.value)}
                        placeholder={t('githubPlaceholder')}
                        className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('demo')}
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <LinkIcon className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="url"
                        value={project.demo_url || ''}
                        onChange={(e) => updateProject(project.id!, 'demo_url', e.target.value)}
                        placeholder={t('demoPlaceholder')}
                        className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('overview')}
                  </label>
                  <textarea
                    data-autogrow="project-text"
                    ref={fitTextareaToContent}
                    value={project.overview || ''}
                    onChange={(e) => {
                      updateProject(project.id!, 'overview', e.target.value)
                      fitTextareaToContent(e.currentTarget)
                    }}
                    placeholder={t('overviewPlaceholder')}
                    rows={1}
                    className="min-h-[42px] w-full overflow-hidden px-3 py-2 text-sm leading-relaxed border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none [field-sizing:content]"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">
                      {t('highlights')}
                    </label>
                    <button
                      onClick={() => addBullet(project.id!)}
                      className="text-primary-600 hover:text-primary-800 text-sm flex items-center space-x-1"
                    >
                      <PlusIcon className="w-3 h-3" />
                      <span>{t('addBullet')}</span>
                    </button>
                  </div>
                  <div className="space-y-2">
                    {(project.highlights || []).map((highlight, highlightIndex) => (
                      <div key={highlight.id || highlightIndex} className="flex items-center space-x-2">
                        <textarea
                          data-autogrow="project-text"
                          ref={fitTextareaToContent}
                          value={highlight.text ?? ''}
                          onChange={(e) => {
                            updateBullet(project.id!, highlightIndex, e.target.value)
                            fitTextareaToContent(e.currentTarget)
                          }}
                          placeholder={t('highlightPlaceholder')}
                          rows={1}
                          className="min-h-[42px] flex-1 overflow-hidden px-3 py-2 text-sm leading-relaxed border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none [field-sizing:content]"
                        />
                        {(project.highlights || []).length > 1 && (
                          <button
                            onClick={() => removeBullet(project.id!, highlightIndex)}
                            className="text-gray-400 hover:text-gray-600 p-1 transition-colors"
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
            onClick={addProject}
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
