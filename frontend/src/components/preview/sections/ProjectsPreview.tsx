'use client'
// 用于提供 components/preview/sections/ProjectsPreview.tsx 模块。

import type { Project } from '@/types/resume'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'
import { useTranslations } from 'next-intl'
import BulletLeadText from './BulletLeadText'

interface ProjectsPreviewProps {
  data: Project[]
  renderLines?: number[]
  templateStyle?: ResumeTemplateStyle
  title?: string
  descriptionLabel?: string
  secondaryLinkLabel?: string
}

/* 链接图标包装器：使用 flex 对齐，避免导出时基线计算偏差 */
const iconWrap: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 12,
  height: 12,
  marginRight: 3,
  flexShrink: 0,
}

// 用于渲染 GithubIcon 组件。
const GithubIcon = () => (
  <span style={iconWrap}>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z"/>
    </svg>
  </span>
)

// 用于渲染 DemoIcon 组件。
const DemoIcon = () => (
  <span style={iconWrap}>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10"/>
      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  </span>
)

// 用于生成项目链接的固定展示顺序。
function getProjectLinkItems(project: Project, secondaryLinkLabel: string) {
  return [
    project.github_url ? { label: 'GitHub', url: project.github_url } : null,
    project.demo_url ? { label: secondaryLinkLabel, url: project.demo_url } : null,
  ].filter((item): item is { label: string; url: string } => Boolean(item))
}

// 单个项目项组件
function ProjectItem({
  project,
  lineIndex,
  templateStyle = 'classic',
  descriptionLabel,
  secondaryLinkLabel,
}: {
  project: Project
  lineIndex: number
  templateStyle?: ResumeTemplateStyle
  descriptionLabel?: string
  secondaryLinkLabel?: string
}) {
  const t = useTranslations('resume.preview')
  const highlights = project.highlights && project.highlights.length > 0
    ? project.highlights.map(item => item.text)
    : []
  const demoLabel = secondaryLinkLabel || t('demo')
  const linkItems = getProjectLinkItems(project, demoLabel)
  const isFormal = templateStyle === 'formal'
  const isEmerald = templateStyle === 'emerald'

  if (isEmerald) {
    return (
      <div data-line-index={lineIndex} className="relative print:break-inside-avoid resume-emerald-item" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 18px)' }}>
        <div className="flex items-baseline justify-between gap-4 text-sm font-semibold" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)' }}>
          <div className="min-w-0 flex flex-wrap items-baseline gap-x-1">
            <span>{project.name}</span>
            {project.role && <span> - {project.role}</span>}
          </div>
          {project.duration && <span className="resume-emerald-subtle shrink-0 font-normal">{project.duration}</span>}
        </div>

        {linkItems.length > 0 && (
          <div className="resume-emerald-links text-sm" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 6px)' }}>
            {linkItems.map((item, index) => (
              <span key={item.label}>
                {index > 0 && <span className="resume-emerald-subtle"> | </span>}
                {item.label}: <a href={item.url} target="_blank" rel="noopener noreferrer">{item.url}</a>
              </span>
            ))}
          </div>
        )}

        {project.overview && (
          <p className="text-sm" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 6px)', lineHeight: '1.64' }}>
            <span className="font-semibold">{descriptionLabel || t('projectDescription')}</span>{project.overview}
          </p>
        )}

        {highlights.length > 0 && (
          <ul className="resume-emerald-list text-sm">
            {highlights.map((achievement, achIndex) => (
              <li key={achIndex} style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 6px)' }}><BulletLeadText text={achievement} /></li>
            ))}
          </ul>
        )}
      </div>
    )
  }

  if (isFormal) {
    return (
      <div data-line-index={lineIndex} className="relative print:break-inside-avoid resume-formal-item" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 16px)' }}>
        <div className="flex items-baseline justify-between gap-4 text-sm text-gray-900 font-semibold" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)' }}>
          <span className="min-w-0">{[project.name, project.role].filter(Boolean).join(' | ')}</span>
          {project.duration && <span className="shrink-0 font-normal">{project.duration}</span>}
        </div>

        {linkItems.length > 0 && (
          <p className="text-sm text-gray-900" style={{ lineHeight: '1.72', marginBottom: 'calc(var(--spacing-scale, 1) * 6px)' }}>
            {linkItems.map((item, index) => (
              <span key={item.label}>
                {index > 0 && ' | '}
                {item.label}: <a href={item.url} target="_blank" rel="noopener noreferrer">{item.url}</a>
              </span>
            ))}
          </p>
        )}

        {project.overview && (
          <p className="text-sm text-gray-900" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)', lineHeight: '1.72' }}>
            {descriptionLabel && <span className="font-semibold">{descriptionLabel}</span>}
            {project.overview}
          </p>
        )}

        {highlights.length > 0 && (
          <ul className="list-disc text-sm text-gray-900" style={{ lineHeight: '1.72', paddingLeft: 18 }}>
            {highlights.map((achievement, achIndex) => (
              <li key={achIndex} style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 6px)' }}><BulletLeadText text={achievement} /></li>
            ))}
          </ul>
        )}
      </div>
    )
  }

  return (
    <div data-line-index={lineIndex} className="relative print:break-inside-avoid" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 16px)' }}>
      <div className="flex justify-between items-start" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)' }}>
        <div className="flex-1 flex flex-wrap items-center gap-2">
          <h3 className="font-semibold text-gray-900 text-base">
            {project.name}
          </h3>
          {project.role && (
            <>
              <span className="w-px h-4 bg-gray-300" />
              <span className="text-sm text-gray-600">{project.role}</span>
            </>
          )}
        </div>
        <div className="text-sm text-gray-600 ml-4 whitespace-nowrap">
          {project.duration}
        </div>
      </div>

      {(project.github_url || project.demo_url) && (
        <div className="flex gap-4 text-sm text-blue-600" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)' }}>
          {project.github_url && (
            <a
              href={project.github_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 leading-none hover:underline"
            >
              <GithubIcon />
              <span className="inline-block leading-none">{t('github')}</span>
            </a>
          )}
          {project.demo_url && (
            <a
              href={project.demo_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 leading-none hover:underline"
            >
              <DemoIcon />
              <span className="inline-block leading-none">{demoLabel}</span>
            </a>
          )}
        </div>
      )}

      {project.overview && (
        <p
          className="text-sm text-gray-900"
          style={{
            marginBottom: 'calc(var(--spacing-scale, 1) * 8px)',
            lineHeight: 'calc(1.35 + var(--spacing-scale, 1) * 0.25)'
          }}
        >
          <span className="font-semibold text-gray-900">{descriptionLabel || t('projectDescription')}</span>{project.overview}
        </p>
      )}

      {highlights.length > 0 && (
        <div style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)' }}>
          <ul
            className="list-disc list-inside text-sm text-gray-900"
            style={{
              lineHeight: 'calc(1.35 + var(--spacing-scale, 1) * 0.25)'
            }}
          >
            {highlights.map((achievement, achIndex) => (
              <li key={achIndex} style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 2px)' }}><BulletLeadText text={achievement} /></li>
            ))}
          </ul>
        </div>
      )}

    </div>
  )
}

// 用于渲染 ProjectsPreview 组件。
export default function ProjectsPreview({
  data,
  renderLines,
  templateStyle = 'classic',
  title,
  descriptionLabel,
  secondaryLinkLabel,
}: ProjectsPreviewProps) {
  const t = useTranslations('resume.layout.modules')
  if (!data || !Array.isArray(data) || data.length === 0) {
    return null
  }

  // 用于处理shouldrender行。
  const shouldRenderLine = (lineIndex: number) => {
    return !renderLines || renderLines.includes(lineIndex)
  }

  return (
    <div style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 20px)' }}>
      {/* 标题作为第0行 */}
      {shouldRenderLine(0) && (
        <h2 data-line-index={0} className="text-lg font-bold text-gray-900 pb-1.5 border-b border-gray-300" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 12px)' }}>
          {templateStyle === 'emerald' ? (
            <span className="resume-emerald-heading-label">{title || t('projects')}</span>
          ) : title || t('projects')}
        </h2>
      )}

      {/* 每个项目作为独立的行 */}
      {data.map((project, index) => {
        const lineIndex = index + 1
        return shouldRenderLine(lineIndex) ? (
          <ProjectItem key={project.id || index} project={project} lineIndex={lineIndex} templateStyle={templateStyle} descriptionLabel={descriptionLabel} secondaryLinkLabel={secondaryLinkLabel} />
        ) : null
      })}
    </div>
  )
}
