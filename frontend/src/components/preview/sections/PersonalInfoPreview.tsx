'use client'
// 用于提供 components/preview/sections/PersonalInfoPreview.tsx 模块。

import type { PersonalInfo } from '@/types/resume'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'
import { useTranslations } from 'next-intl'
import { normalizeResumePhotoUrl } from '@/lib/resumePhoto'
import {
  getCenteredPersonalInfoLayout,
  getEmeraldPersonalInfoLayout,
  getFormalPersonalInfoLayout,
} from './personalInfoLayout'

interface PersonalInfoPreviewProps {
  data: PersonalInfo
  renderLines?: number[]
  templateStyle?: ResumeTemplateStyle
}

/* 图标包装器：使用 flex 对齐，避免导出时基线计算偏差 */
const iconWrap: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 12,
  height: 12,
  marginRight: 3,
  flexShrink: 0,
}

// 用于渲染 EmailIcon 组件。
const EmailIcon = () => (
  <span style={iconWrap}>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="2" y="4" width="20" height="16" rx="2"/>
      <path d="m2 7 10 7 10-7"/>
    </svg>
  </span>
)

// 用于渲染 PhoneIcon 组件。
const PhoneIcon = () => (
  <span style={iconWrap}>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 1.27h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.9a16 16 0 0 0 6 6l.92-.92a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 21.73 16.92z"/>
    </svg>
  </span>
)

// 用于渲染 LocationIcon 组件。
const LocationIcon = () => (
  <span style={iconWrap}>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>
      <circle cx="12" cy="10" r="3"/>
    </svg>
  </span>
)

// 用于渲染 GithubIcon 组件。
const GithubIcon = () => (
  <span style={iconWrap}>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z"/>
    </svg>
  </span>
)

// 用于渲染 LinkedinIcon 组件。
const LinkedinIcon = () => (
  <span style={iconWrap}>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6zM2 9h4v12H2z"/>
      <circle cx="4" cy="4" r="2"/>
    </svg>
  </span>
)

// 用于渲染 WebsiteIcon 组件。
const WebsiteIcon = () => (
  <span style={iconWrap}>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10"/>
      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  </span>
)

// 用于渲染简历个人照片。
function ResumePhoto({ alt, className, src }: { alt: string; className: string; src: string }) {
  return (
    <img
      src={src}
      alt={alt}
      className={className}
      style={{ objectFit: 'cover' }}
    />
  )
}

// 用于渲染 PersonalInfoPreview 组件。
export default function PersonalInfoPreview({ data, renderLines, templateStyle = 'classic' }: PersonalInfoPreviewProps) {
  const t = useTranslations('resume.preview')
  const photoUrl = normalizeResumePhotoUrl(data?.photo_url)
  if (!data || (!data.name && !data.email && !data.phone && !photoUrl)) {
    return null
  }

  // 用于处理shouldrender行。
  const shouldRenderLine = (lineIndex: number) => {
    return !renderLines || renderLines.includes(lineIndex)
  }

  const itemClassName = 'inline-flex items-center'
  const isFormal = templateStyle === 'formal'
  const isEmerald = templateStyle === 'emerald'

  if (isEmerald) {
    const layout = getEmeraldPersonalInfoLayout(Boolean(photoUrl))
    return (
      <div className={layout.containerClassName} style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 28px)' }}>
        {shouldRenderLine(0) && (
          <div data-line-index={0} className={layout.nameBlockClassName}>
            <div className={layout.textClassName}>
              <h1 className="text-2xl font-bold">
                {data.name || t('nameFallback')}
              </h1>
              {data.position && (
                <p className="resume-emerald-position">
                  {data.position}
                </p>
              )}
            </div>
            {photoUrl && (
              <div className={layout.photoWrapClassName}>
                <ResumePhoto
                  src={photoUrl}
                  alt={data.name || t('nameFallback')}
                  className="resume-photo h-[88px] w-[72px] border border-white/40 bg-white/10"
                />
              </div>
            )}
          </div>
        )}

        {shouldRenderLine(1) && (
          <div data-line-index={1} className={`resume-emerald-contact ${layout.contactClassName}`}>
            <div className="resume-emerald-contact-col">
              {data.email && (
                <span className={itemClassName}><EmailIcon />{data.email}</span>
              )}
              {data.github && (
                <span className={itemClassName}>
                  <GithubIcon />
                  <a href={data.github} target="_blank" rel="noopener noreferrer">GitHub</a>
                </span>
              )}
              {data.address && (
                <span className={itemClassName}><LocationIcon />{data.address}</span>
              )}
            </div>
            <div className="resume-emerald-contact-col resume-emerald-contact-right">
              {data.phone && (
                <span className={itemClassName}><PhoneIcon />{data.phone}</span>
              )}
              {data.website && (
                <span className={itemClassName}>
                  <WebsiteIcon />
                  <a href={data.website} target="_blank" rel="noopener noreferrer">{t('website')}</a>
                </span>
              )}
              {data.linkedin && (
                <span className={itemClassName}>
                  <LinkedinIcon />
                  <a href={data.linkedin} target="_blank" rel="noopener noreferrer">LinkedIn</a>
                </span>
              )}
            </div>
          </div>
        )}

        {(data.github || data.linkedin || data.website) && shouldRenderLine(2) && (
          <div data-line-index={2} className="hidden" />
        )}
      </div>
    )
  }

  if (isFormal) {
    const contactItems = [data.phone, data.email].filter(Boolean)
    const linkItems = [
      data.github ? { label: 'GitHub', url: data.github } : null,
      data.linkedin ? { label: 'LinkedIn', url: data.linkedin } : null,
      data.website ? { label: t('website'), url: data.website } : null,
    ].filter((item): item is { label: string; url: string } => Boolean(item))
    const layout = getFormalPersonalInfoLayout(Boolean(photoUrl))

    return (
      <div className={layout.containerClassName} style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 22px)' }}>
        {shouldRenderLine(0) && (
          <div data-line-index={0} className={layout.headerClassName} style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 12px)' }}>
            <div className={layout.textClassName}>
              <h1 className="text-2xl font-bold text-gray-900 mb-3">
                {data.name || t('nameFallback')}
              </h1>
              {data.position && (
                <p className="text-base text-gray-900 font-semibold">
                  {t('targetIntent')}: {data.position}
                </p>
              )}
            </div>
            {photoUrl && (
              <div className={layout.photoWrapClassName}>
                <ResumePhoto
                  src={photoUrl}
                  alt={data.name || t('nameFallback')}
                  className="resume-photo h-[88px] w-[72px] border border-gray-300 bg-gray-50"
                />
              </div>
            )}
          </div>
        )}

        {shouldRenderLine(1) && (
          <div data-line-index={1} className={`resume-formal-contact text-sm text-gray-900 ${layout.contactClassName}`}>
            {contactItems.length > 0 && (
              <div>{contactItems.join(' | ')}</div>
            )}
            {linkItems.length > 0 && (
              <div>
                {linkItems.map((item, index) => (
                  <span key={item.label}>
                    {index > 0 && ' | '}
                    {item.label}: <a href={item.url} target="_blank" rel="noopener noreferrer">{item.url}</a>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {(data.github || data.linkedin || data.website) && shouldRenderLine(2) && (
          <div data-line-index={2} className="hidden" />
        )}
      </div>
    )
  }

  const layout = getCenteredPersonalInfoLayout(Boolean(photoUrl))
  return (
    <div className={layout.containerClassName} style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 20px)' }}>
      {/* 姓名和职位 */}
      {shouldRenderLine(0) && (
        <div
          data-line-index={0}
          className={layout.headerClassName}
          style={{
            ...layout.headerStyle,
            marginBottom: 'calc(var(--spacing-scale, 1) * 12px)',
          }}
        >
          <div className={layout.textClassName}>
            <h1 className="text-2xl font-bold text-gray-900 mb-1">
              {data.name || t('nameFallback')}
            </h1>
            {data.position && (
              <p className="text-lg text-gray-600 font-medium">
                {data.position}
              </p>
            )}
          </div>
          {photoUrl && (
            <div className={layout.photoWrapClassName}>
              <ResumePhoto
                src={photoUrl}
                alt={data.name || t('nameFallback')}
                className="resume-photo h-[88px] w-[72px] border border-gray-300 bg-gray-50"
              />
            </div>
          )}
        </div>
      )}

      {/* 联系方式 */}
      {shouldRenderLine(1) && (
        <div data-line-index={1} className={`flex flex-wrap justify-center gap-4 text-xs text-gray-600 pb-3 ${layout.contactClassName}`}>
          {data.email && (
            <span className={itemClassName}><EmailIcon />{data.email}</span>
          )}

          {data.phone && (
            <span className={itemClassName}><PhoneIcon />{data.phone}</span>
          )}

          {data.address && (
            <span className={itemClassName}><LocationIcon />{data.address}</span>
          )}

          {data.github && (
            <span className={`${itemClassName} text-blue-600`}>
              <GithubIcon />
              <a href={data.github} target="_blank" rel="noopener noreferrer" className="hover:underline">GitHub</a>
            </span>
          )}

          {data.linkedin && (
            <span className={`${itemClassName} text-blue-600`}>
              <LinkedinIcon />
              <a href={data.linkedin} target="_blank" rel="noopener noreferrer" className="hover:underline">LinkedIn</a>
            </span>
          )}

          {data.website && (
            <span className={`${itemClassName} text-blue-600`}>
              <WebsiteIcon />
              <a href={data.website} target="_blank" rel="noopener noreferrer" className="hover:underline">{t('website')}</a>
            </span>
          )}
        </div>
      )}

      {/* 在线链接占位行保留，避免分页引用 */}
      {(data.github || data.linkedin || data.website) && shouldRenderLine(2) && (
        <div data-line-index={2} className="hidden" />
      )}
    </div>
  )
}
