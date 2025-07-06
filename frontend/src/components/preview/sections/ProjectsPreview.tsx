'use client'

import { LinkIcon } from '@heroicons/react/24/outline'

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

interface ProjectsPreviewProps {
  data: Project[]
}

export default function ProjectsPreview({ data }: ProjectsPreviewProps) {
  if (!data || data.length === 0) {
    return null
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-bold text-gray-900 mb-4 pb-2 border-b border-gray-200">
        项目经验
      </h2>
      
      <div className="space-y-6">
        {data.map((project, index) => (
          <div key={project.id || index} className="relative">
            <div className="flex justify-between items-start mb-2">
              <div className="flex-1">
                <h3 className="font-semibold text-gray-900">
                  {project.name}
                </h3>
                <p className="text-gray-700">
                  {project.role}
                </p>
              </div>
              <div className="text-sm text-gray-600 ml-4 whitespace-nowrap">
                {project.duration}
              </div>
            </div>
            
            {project.description && (
              <p className="text-sm text-gray-600 mb-3">
                {project.description}
              </p>
            )}

            {/* 技术栈 */}
            {project.technologies && project.technologies.length > 0 && (
              <div className="mb-3">
                <span className="text-sm font-medium text-gray-700 mr-2">技术栈:</span>
                <div className="inline-flex flex-wrap gap-1">
                  {project.technologies.map((tech, techIndex) => (
                    <span 
                      key={techIndex}
                      className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded"
                    >
                      {tech}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* 项目成果 */}
            {project.achievements && project.achievements.length > 0 && (
              <div className="mb-3">
                <span className="text-sm font-medium text-gray-700">主要成果:</span>
                <ul className="list-disc list-inside text-sm text-gray-600 mt-1">
                  {project.achievements.map((achievement, achIndex) => (
                    <li key={achIndex}>{achievement}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* 项目链接 */}
            {(project.github_url || project.demo_url) && (
              <div className="flex gap-4 text-sm">
                {project.github_url && (
                  <a 
                    href={project.github_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-blue-600 hover:underline"
                  >
                    <LinkIcon className="w-4 h-4" />
                    源码
                  </a>
                )}
                {project.demo_url && (
                  <a 
                    href={project.demo_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-blue-600 hover:underline"
                  >
                    <LinkIcon className="w-4 h-4" />
                    演示
                  </a>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}