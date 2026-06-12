'use client'
// 用于提供 components/preview/ResumeLayoutControls.tsx 模块。

import { useRef, useState } from 'react'
import { 
  AdjustmentsHorizontalIcon
} from '@heroicons/react/24/outline'
import {
  LayoutDensity,
  ResumeModule,
  ResumeLayoutConfig,
  DENSITY_SPACING_SCALE,
  ResumeTemplateStyle,
} from '@/lib/resumeLayoutConfig'
import {
  MAX_RESUME_SPACING_SCALE,
  MIN_RESUME_SPACING_SCALE,
  RESUME_SPACING_SCALE_STEP,
  clampResumeSpacingScale,
} from '@/lib/resumeSpacingScale'
import { useTranslations } from 'next-intl'

interface ResumeLayoutControlsProps {
  config: ResumeLayoutConfig
  onConfigChange: (config: ResumeLayoutConfig, options?: { persist?: boolean }) => void
  className?: string
}

// 用于渲染模板选择卡片里的缩略预览。
function TemplateStylePreview({ templateStyle }: { templateStyle: ResumeTemplateStyle }) {
  const isModern = templateStyle === 'modern'
  const isFormal = templateStyle === 'formal'
  const isEmerald = templateStyle === 'emerald'
  const accentColor = isEmerald ? '#059669' : isModern ? '#1d4ed8' : isFormal ? '#111827' : '#d1d5db'

  return (
    <span
      aria-hidden="true"
      className="relative h-10 w-7 overflow-hidden rounded-sm border bg-white shadow-sm"
      style={{ borderColor: accentColor }}
    >
      <span
        data-testid="template-preview-header"
        className="block h-2 w-full"
        style={{ backgroundColor: accentColor }}
      />
      <span className="block space-y-1 px-1.5 py-1">
        <span className="block h-1.5 rounded-full" style={{ backgroundColor: accentColor }} />
        <span className="block h-1 rounded-full bg-gray-200" />
        <span className="block h-1 rounded-full bg-gray-200" />
      </span>
    </span>
  )
}


// 用于渲染 ResumeLayoutControls 组件。
export default function ResumeLayoutControls({
  config,
  onConfigChange,
  className = ''
}: ResumeLayoutControlsProps) {
  const [showControls, setShowControls] = useState(false)
  const [activeTab, setActiveTab] = useState<'template' | 'density' | 'modules'>('template')
  const pendingSpacingConfigRef = useRef<ResumeLayoutConfig | null>(null)
  const t = useTranslations('resume.layout')

  // 用于处理templatestylechange。
  const handleTemplateStyleChange = (templateStyle: ResumeTemplateStyle) => {
    onConfigChange({
      density: config.density,
      moduleOrder: [...config.moduleOrder],
      visibleModules: new Set(config.visibleModules),
      spacingScale: config.spacingScale,
      templateStyle,
    })
  }

  // 用于处理密度change。
  const handleDensityChange = (density: LayoutDensity) => {
    const spacingScale = DENSITY_SPACING_SCALE[density as Exclude<LayoutDensity, 'custom'>] ?? config.spacingScale
    onConfigChange({
      density,
      moduleOrder: [...config.moduleOrder],
      visibleModules: new Set(config.visibleModules),
      spacingScale,
      templateStyle: config.templateStyle,
    })
  }

  // 用于构建细调间距对应的布局配置。
  const buildSpacingScaleConfig = (value: number): ResumeLayoutConfig => ({
    density: 'custom',
    moduleOrder: [...config.moduleOrder],
    visibleModules: new Set(config.visibleModules),
    spacingScale: clampResumeSpacingScale(value),
    templateStyle: config.templateStyle,
  })

  // 用于处理间距缩放change。
  const handleSpacingScaleChange = (value: number) => {
    const nextConfig = buildSpacingScaleConfig(value)
    pendingSpacingConfigRef.current = nextConfig
    onConfigChange(nextConfig, { persist: false })
  }

  // 用于在拖动结束后持久化最后一次间距细调。
  const commitPendingSpacingScale = () => {
    const pendingConfig = pendingSpacingConfigRef.current
    if (!pendingConfig) return
    pendingSpacingConfigRef.current = null
    onConfigChange(pendingConfig)
  }

  // 用于处理间距缩放reset。
  const handleSpacingScaleReset = () => {
    onConfigChange({
      density: 'normal',
      moduleOrder: [...config.moduleOrder],
      visibleModules: new Set(config.visibleModules),
      spacingScale: 1.0,
      templateStyle: config.templateStyle,
    })
  }

  // 用于切换模块可见性。
  const toggleModuleVisibility = (module: ResumeModule) => {
    const newVisible = new Set(config.visibleModules)
    if (newVisible.has(module)) {
      newVisible.delete(module)
    } else {
      newVisible.add(module)
    }
    onConfigChange({
      density: config.density,
      moduleOrder: [...config.moduleOrder],
      visibleModules: newVisible,
      spacingScale: config.spacingScale,
      templateStyle: config.templateStyle,
    })
  }

  // 用于移动模块。
  const moveModule = (module: ResumeModule, direction: 'up' | 'down') => {
    const currentIndex = config.moduleOrder.indexOf(module)
    if (currentIndex === -1) return

    const newOrder = [...config.moduleOrder]
    const targetIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1

    if (targetIndex < 0 || targetIndex >= newOrder.length) return

    ;[newOrder[currentIndex], newOrder[targetIndex]] =
    [newOrder[targetIndex], newOrder[currentIndex]]

    onConfigChange({
      density: config.density,
      moduleOrder: newOrder,
      visibleModules: new Set(config.visibleModules),
      spacingScale: config.spacingScale,
      templateStyle: config.templateStyle,
    })
  }

  return (
    <div className={`relative ${className}`}>
      {/* 触发按钮 — 56px pill，ghost 样式 */}
      <button
        onClick={() => setShowControls(!showControls)}
        className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold transition-colors"
        style={{
          borderRadius: '56px',
          backgroundColor: '#ffffff',
          border: '1px solid rgba(91,97,110,0.25)',
          color: '#0a0b0d',
        }}
        onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
        onMouseLeave={e => (e.currentTarget.style.backgroundColor = '#ffffff')}
      >
        <AdjustmentsHorizontalIcon className="w-4 h-4" />
        <span>{t('settings')}</span>
      </button>

      {/* 控制面板 */}
      {showControls && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setShowControls(false)} />

          <div
            className="absolute right-0 mt-2 w-80 bg-white z-50"
            style={{
              borderRadius: '16px',
              border: '1px solid rgba(91,97,110,0.18)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.08)',
            }}
          >
            {/* 标签页 */}
            <div className="flex" style={{ borderBottom: '1px solid rgba(91,97,110,0.12)' }}>
              {(['template', 'density', 'modules'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className="flex-1 px-4 py-3 text-sm font-semibold transition-colors relative"
                  style={{ color: activeTab === tab ? '#0052ff' : '#5b616e' }}
                >
                  {t(`tabs.${tab}`)}
                  {activeTab === tab && (
                    <div className="absolute bottom-0 left-4 right-4 h-0.5" style={{ backgroundColor: '#0052ff', borderRadius: '2px 2px 0 0' }} />
                  )}
                </button>
              ))}
            </div>

            <div className="p-4">
              {activeTab === 'template' && (
                <div className="space-y-3">
                  {(['classic', 'modern', 'formal', 'emerald'] as ResumeTemplateStyle[]).map((templateStyle) => {
                    const active = config.templateStyle === templateStyle
                    const isEmerald = templateStyle === 'emerald'
                    return (
                      <button
                        key={templateStyle}
                        type="button"
                        onClick={() => handleTemplateStyleChange(templateStyle)}
                        className="w-full p-3 text-left transition-colors"
                        style={{
                          borderRadius: '12px',
                          border: `1px solid ${active ? '#0052ff' : 'rgba(91,97,110,0.18)'}`,
                          backgroundColor: active ? 'rgba(0,82,255,0.05)' : '#ffffff',
                        }}
                      >
                        <span className="block text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                          {t(`templates.${templateStyle}`)}
                        </span>
                        <span className="mt-2 flex h-10 items-center gap-2">
                          <TemplateStylePreview templateStyle={templateStyle} />
                          <span className="flex-1 space-y-1">
                            <span
                              className="block h-1.5 rounded-full"
                              style={{ backgroundColor: templateStyle === 'modern' ? '#1d4ed8' : isEmerald ? '#059669' : '#111827' }}
                            />
                            <span className="block h-1 rounded-full bg-gray-200" />
                            <span className="block h-1 rounded-full bg-gray-200" />
                          </span>
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}

              {activeTab === 'density' && (
                <div className="space-y-4">
                  <div className="space-y-2">
                    {(['comfortable', 'normal', 'compact'] as Exclude<LayoutDensity, 'custom'>[]).map((density) => (
                      <label
                        key={density}
                        className="flex items-center gap-3 p-3 cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          border: `1px solid ${config.density === density ? '#0052ff' : 'rgba(91,97,110,0.18)'}`,
                          backgroundColor: config.density === density ? 'rgba(0,82,255,0.05)' : '#ffffff',
                        }}
                      >
                        <input
                          type="radio"
                          name="density"
                          checked={config.density === density}
                          onChange={() => handleDensityChange(density)}
                          style={{ accentColor: '#0052ff' }}
                        />
                        <span className="text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                          {t(`density.${density}`)}
                        </span>
                      </label>
                    ))}
                  </div>

                  <div className="pt-3" style={{ borderTop: '1px solid rgba(91,97,110,0.1)' }}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold" style={{ color: '#0a0b0d' }}>{t('density.fine')}</span>
                      <button
                        onClick={handleSpacingScaleReset}
                        className="text-xs font-semibold"
                        style={{ color: '#0052ff' }}
                      >
                        {t('density.reset')}
                      </button>
                    </div>
                    <input
                      type="range"
                      min={MIN_RESUME_SPACING_SCALE}
                      max={MAX_RESUME_SPACING_SCALE}
                      step={RESUME_SPACING_SCALE_STEP}
                      value={clampResumeSpacingScale(config.spacingScale ?? 1)}
                      onChange={(e) => handleSpacingScaleChange(parseFloat(e.target.value))}
                      onBlur={commitPendingSpacingScale}
                      onKeyUp={commitPendingSpacingScale}
                      onPointerCancel={commitPendingSpacingScale}
                      onPointerUp={commitPendingSpacingScale}
                      className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                      style={{ accentColor: '#0052ff', backgroundColor: '#eef0f3' }}
                    />
                    <div className="flex justify-between items-center mt-1.5">
                      <span className="text-xs" style={{ color: '#9ca3af' }}>{t('density.tight')}</span>
                      <span className="text-xs font-semibold" style={{ color: '#0a0b0d' }}>
                        {t('density.spacing', { value: (config.spacingScale ?? 1).toFixed(2) })}
                      </span>
                      <span className="text-xs" style={{ color: '#9ca3af' }}>{t('density.loose')}</span>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'modules' && (
                <div className="space-y-2">
                  {config.moduleOrder.map((module, index) => (
                    <div
                      key={module}
                      className="flex items-center gap-3 p-3 transition-colors"
                      style={{
                        borderRadius: '12px',
                        border: '1px solid rgba(91,97,110,0.15)',
                        backgroundColor: '#ffffff',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={config.visibleModules.has(module)}
                        onChange={() => toggleModuleVisibility(module)}
                        style={{ accentColor: '#0052ff' }}
                      />
                      <div className="flex-1 text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                        {t(`modules.${module}`)}
                      </div>
                      <div className="flex gap-1">
                        <button
                          onClick={() => moveModule(module, 'up')}
                          disabled={index === 0}
                          className="p-1 transition-colors disabled:opacity-30"
                          style={{ borderRadius: '8px', color: '#5b616e' }}
                          onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                          onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                          </svg>
                        </button>
                        <button
                          onClick={() => moveModule(module, 'down')}
                          disabled={index === config.moduleOrder.length - 1}
                          className="p-1 transition-colors disabled:opacity-30"
                          style={{ borderRadius: '8px', color: '#5b616e' }}
                          onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                          onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
