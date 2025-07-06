'use client'

import { useState, useEffect } from 'react'
import { 
  FolderIcon,
  PlusIcon,
  TrashIcon,
  LinkIcon,
  CalendarIcon
} from '@heroicons/react/24/outline'

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

interface ProjectsEditorProps {
  data: Project[]
  onChange: (data: Project[]) => void
}

export default function ProjectsEditor({ data, onChange }: ProjectsEditorProps) {
  const [projectsList, setProjectsList] = useState<Project[]>(data || [])

  useEffect(() => {
    setProjectsList(data || [])
  }, [data])

  const addProject = () => {
    const newProject: Project = {
      id: Date.now(),
      name: '',
      description: '',
      technologies: [],
      role: '',
      duration: '',
      github_url: '',
      demo_url: '',
      achievements: ['']
    }
    const newList = [...projectsList, newProject]
    setProjectsList(newList)
    onChange(newList)
  }

  const removeProject = (id: number) => {
    const newList = projectsList.filter(project => project.id !== id)
    setProjectsList(newList)
    onChange(newList)
  }

  const updateProject = (id: number, field: keyof Project, value: any) => {
    const newList = projectsList.map(project => 
      project.id === id ? { ...project, [field]: value } : project
    )
    setProjectsList(newList)
    onChange(newList)
  }

  const addTechnology = (projectId: number) => {
    const project = projectsList.find(p => p.id === projectId)
    if (project) {
      const newTechnologies = [...project.technologies, '']
      updateProject(projectId, 'technologies', newTechnologies)
    }
  }

  const updateTechnology = (projectId: number, techIndex: number, value: string) => {
    const project = projectsList.find(p => p.id === projectId)
    if (project) {
      const newTechnologies = [...project.technologies]
      newTechnologies[techIndex] = value
      updateProject(projectId, 'technologies', newTechnologies)
    }
  }

  const removeTechnology = (projectId: number, techIndex: number) => {
    const project = projectsList.find(p => p.id === projectId)
    if (project && project.technologies.length > 1) {
      const newTechnologies = project.technologies.filter((_, index) => index !== techIndex)
      updateProject(projectId, 'technologies', newTechnologies)
    }
  }

  const addAchievement = (projectId: number) => {
    const project = projectsList.find(p => p.id === projectId)
    if (project) {
      const newAchievements = [...project.achievements, '']
      updateProject(projectId, 'achievements', newAchievements)
    }
  }

  const updateAchievement = (projectId: number, achievementIndex: number, value: string) => {
    const project = projectsList.find(p => p.id === projectId)
    if (project) {
      const newAchievements = [...project.achievements]
      newAchievements[achievementIndex] = value
      updateProject(projectId, 'achievements', newAchievements)
    }
  }

  const removeAchievement = (projectId: number, achievementIndex: number) => {
    const project = projectsList.find(p => p.id === projectId)
    if (project && project.achievements.length > 1) {
      const newAchievements = project.achievements.filter((_, index) => index !== achievementIndex)
      updateProject(projectId, 'achievements', newAchievements)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center">
          <FolderIcon className="w-5 h-5 mr-2" />
          项目经验
        </h3>
        <button
          onClick={addProject}
          className="btn-secondary flex items-center space-x-1 text-sm"
        >
          <PlusIcon className="w-4 h-4" />
          <span>添加项目</span>
        </button>
      </div>

      {projectsList.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <FolderIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 mb-4">还没有添加项目经验</p>
          <button
            onClick={addProject}
            className="btn-primary flex items-center space-x-2 mx-auto"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加第一个项目</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {projectsList.map((project, index) => (
            <div key={project.id || index} className="bg-gray-50 rounded-lg p-6 border">
              <div className="flex items-center justify-between mb-6">
                <h4 className="font-medium text-gray-900">项目 {index + 1}</h4>
                {projectsList.length > 1 && (
                  <button
                    onClick={() => removeProject(project.id!)}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="删除此项目"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="space-y-6">
                {/* 基本信息 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      项目名称 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={project.name}
                      onChange={(e) => updateProject(project.id!, 'name', e.target.value)}
                      placeholder="智能简历生成系统"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      项目周期 <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <CalendarIcon className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="text"
                        value={project.duration}
                        onChange={(e) => updateProject(project.id!, 'duration', e.target.value)}
                        placeholder="2023.03 - 2023.08"
                        className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      项目角色 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={project.role}
                      onChange={(e) => updateProject(project.id!, 'role', e.target.value)}
                      placeholder="前端开发工程师"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      GitHub 地址
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <LinkIcon className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="url"
                        value={project.github_url || ''}
                        onChange={(e) => updateProject(project.id!, 'github_url', e.target.value)}
                        placeholder="https://github.com/username/project"
                        className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      演示地址
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <LinkIcon className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="url"
                        value={project.demo_url || ''}
                        onChange={(e) => updateProject(project.id!, 'demo_url', e.target.value)}
                        placeholder="https://your-project-demo.com"
                        className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                  </div>
                </div>

                {/* 项目描述 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    项目描述 <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={project.description}
                    onChange={(e) => updateProject(project.id!, 'description', e.target.value)}
                    placeholder="简要描述项目背景、目标和主要功能..."
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                  />
                </div>

                {/* 技术栈 */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">
                      技术栈 <span className="text-red-500">*</span>
                    </label>
                    <button
                      onClick={() => addTechnology(project.id!)}
                      className="text-primary-600 hover:text-primary-800 text-sm flex items-center space-x-1"
                    >
                      <PlusIcon className="w-3 h-3" />
                      <span>添加技术</span>
                    </button>
                  </div>
                  <div className="space-y-2">
                    {project.technologies.map((tech, techIndex) => (
                      <div key={techIndex} className="flex items-center space-x-2">
                        <input
                          type="text"
                          value={tech}
                          onChange={(e) => updateTechnology(project.id!, techIndex, e.target.value)}
                          placeholder="React"
                          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                        />
                        {project.technologies.length > 1 && (
                          <button
                            onClick={() => removeTechnology(project.id!, techIndex)}
                            className="text-red-600 hover:text-red-800 p-1"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    建议填写具体的技术栈，如：React、Node.js、MongoDB等
                  </p>
                </div>

                {/* 项目成果 */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">
                      项目成果与亮点 <span className="text-red-500">*</span>
                    </label>
                    <button
                      onClick={() => addAchievement(project.id!)}
                      className="text-primary-600 hover:text-primary-800 text-sm flex items-center space-x-1"
                    >
                      <PlusIcon className="w-3 h-3" />
                      <span>添加成果</span>
                    </button>
                  </div>
                  <div className="space-y-2">
                    {project.achievements && project.achievements.map((achievement, achievementIndex) => (
                      <div key={achievementIndex} className="flex items-start space-x-2">
                        <span className="text-gray-400 mt-2">•</span>
                        <textarea
                          value={achievement}
                          onChange={(e) => updateAchievement(project.id!, achievementIndex, e.target.value)}
                          placeholder="实现了用户友好的拖拽式简历编辑界面，提升编辑效率50%"
                          rows={2}
                          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                        />
                        {project.achievements && project.achievements.length > 1 && (
                          <button
                            onClick={() => removeAchievement(project.id!, achievementIndex)}
                            className="text-red-600 hover:text-red-800 p-1 mt-1"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    💡 建议包含具体数据和指标，突出个人贡献和技术难点
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}