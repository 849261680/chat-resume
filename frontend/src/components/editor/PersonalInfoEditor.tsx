'use client'
// 用于提供 components/editor/PersonalInfoEditor.tsx 模块。

import { useState, useEffect, type ChangeEvent } from 'react'
import { 
  EnvelopeIcon, 
  PhoneIcon,
  LinkIcon,
  BriefcaseIcon,
  PhotoIcon,
  TrashIcon
} from '@heroicons/react/24/outline'
import type { PersonalInfo } from '@/types/resume'
import { useTranslations } from 'next-intl'
import { normalizeResumePhotoUrl } from '@/lib/resumePhoto'

interface PersonalInfoEditorProps {
  data: PersonalInfo
  onChange: (data: PersonalInfo) => void
}

// 用于把本地图片文件读取成 data URL。
function readResumePhotoFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

// 用于渲染 PersonalInfoEditor 组件。
export default function PersonalInfoEditor({ data, onChange }: PersonalInfoEditorProps) {
  const [formData, setFormData] = useState<PersonalInfo>(data || {})
  const t = useTranslations('resume.forms.personal')

  useEffect(() => {
    setFormData(data || {})
  }, [data])

  // 用于处理change。
  const handleChange = (field: keyof PersonalInfo, value: string) => {
    const newData = { ...formData, [field]: value }
    setFormData(newData)
    onChange(newData)
  }

  // 用于处理照片文件选择。
  const handlePhotoFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || !file.type.startsWith('image/')) {
      return
    }

    void readResumePhotoFile(file).then((photoUrl) => {
      handleChange('photo_url', normalizeResumePhotoUrl(photoUrl))
    })
  }

  const photoPreviewUrl = normalizeResumePhotoUrl(formData.photo_url)

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        {/* 姓名 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('name')}
          </label>
          <input
            type="text"
            value={formData.name || ''}
            onChange={(e) => handleChange('name', e.target.value)}
            placeholder={t('namePlaceholder')}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        </div>

        {/* 照片 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('photo')}
          </label>
          <div className="flex items-start gap-3">
            <div className="h-16 w-12 shrink-0 overflow-hidden rounded-md border border-gray-200 bg-gray-50">
              {photoPreviewUrl ? (
                <img
                  src={photoPreviewUrl}
                  alt={t('photo')}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-gray-400">
                  <PhotoIcon className="h-6 w-6" />
                </div>
              )}
            </div>
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex flex-wrap gap-2">
                <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50">
                  <PhotoIcon className="h-4 w-4" />
                  {t('photoUpload')}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    onChange={handlePhotoFileChange}
                    className="sr-only"
                  />
                </label>
                {formData.photo_url && (
                  <button
                    type="button"
                    onClick={() => handleChange('photo_url', '')}
                    className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <TrashIcon className="h-4 w-4" />
                    {t('photoRemove')}
                  </button>
                )}
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <LinkIcon className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  type="url"
                  value={formData.photo_url || ''}
                  onChange={(e) => handleChange('photo_url', e.target.value)}
                  onBlur={(e) => handleChange('photo_url', normalizeResumePhotoUrl(e.target.value))}
                  placeholder={t('photoUrlPlaceholder')}
                  aria-label={t('photoUrl')}
                  className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>
        </div>

        {/* 邮箱 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('email')}
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <EnvelopeIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="email"
              value={formData.email || ''}
              onChange={(e) => handleChange('email', e.target.value)}
              placeholder={t('emailPlaceholder')}
              className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* 手机号 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('phone')}
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <PhoneIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="tel"
              value={formData.phone || ''}
              onChange={(e) => handleChange('phone', e.target.value)}
              placeholder="138-0000-0000"
              className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* 期望职位 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('position')}
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <BriefcaseIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              value={formData.position || ''}
              onChange={(e) => handleChange('position', e.target.value)}
              placeholder={t('positionPlaceholder')}
              className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* GitHub */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            GitHub
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <LinkIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="url"
              value={formData.github || ''}
              onChange={(e) => handleChange('github', e.target.value)}
              placeholder={t('githubPlaceholder')}
              className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* LinkedIn */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            LinkedIn
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <LinkIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="url"
              value={formData.linkedin || ''}
              onChange={(e) => handleChange('linkedin', e.target.value)}
              placeholder={t('linkedinPlaceholder')}
              className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* 个人网站 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('website')}
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <LinkIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="url"
              value={formData.website || ''}
              onChange={(e) => handleChange('website', e.target.value)}
              placeholder={t('websitePlaceholder')}
              className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* 地址 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('address')}
          </label>
          <input
            type="text"
            value={formData.address || ''}
            onChange={(e) => handleChange('address', e.target.value)}
            placeholder={t('addressPlaceholder')}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        </div>
      </div>
    </div>
  )
}
