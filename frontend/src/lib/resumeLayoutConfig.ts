/**
 * 简历布局配置模块
 * 
 * 管理简历的视觉密度、间距、模块顺序等配置
 */

import type { ModuleConfig, ResumeModule, ResumeTemplateStyle } from '@/types/resumeLayout'
import { apiUrl } from '@/lib/httpClient'
import { clampResumeSpacingScale } from './resumeSpacingScale'

export type { ModuleConfig, ResumeModule, ResumeTemplateStyle } from '@/types/resumeLayout'

export type LayoutDensity = 'comfortable' | 'normal' | 'compact' | 'custom'
export type ResumeEditorTranslate = (key: string) => string

export interface ResumeEditorSection {
  key: string
  label: string
}

/**
 * 三档预设对应的 spacingScale 值
 */
export const DENSITY_SPACING_SCALE: Record<Exclude<LayoutDensity, 'custom'>, number> = {
  comfortable: 1.3,
  normal: 1.0,
  compact: 0.7
}

/**
 * 默认模块顺序
 */
const DEFAULT_MODULE_ORDER: ResumeModule[] = [
  'personal',
  'summary',
  'education',
  'work',
  'projects',
  'open_source',
  'skills'
]

/**
 * 模块显示名称
 */
const MODULE_LABELS: Record<ResumeModule, string> = {
  personal: 'Personal info',
  summary: 'Summary',
  education: 'Education',
  work: 'Work experience',
  skills: 'Skills',
  projects: 'Projects',
  open_source: 'Open source',
}

export const EDITOR_SECTION_TO_MODULE: Partial<Record<string, ResumeModule>> = {
  personal: 'personal',
  summary: 'summary',
  education: 'education',
  work: 'work',
  projects: 'projects',
  open_source: 'open_source',
  skills: 'skills',
}

const MODULE_TO_EDITOR_SECTION: Record<ResumeModule, string> = {
  personal: 'personal',
  summary: 'summary',
  education: 'education',
  work: 'work',
  projects: 'projects',
  open_source: 'open_source',
  skills: 'skills',
}

const SECTION_LABEL_KEYS: Record<string, string> = {
  job_application: 'sections.job',
  personal: 'sections.personal',
  summary: 'sections.summary',
  education: 'sections.education',
  work: 'sections.work',
  projects: 'sections.projects',
  open_source: 'sections.openSource',
  skills: 'sections.skills',
}

// 用于补齐旧布局配置缺失的新模块，同时过滤无效模块。
function normalizeModuleOrder(rawOrder: unknown): ResumeModule[] {
  const rawModules = Array.isArray(rawOrder) ? rawOrder : DEFAULT_MODULE_ORDER
  const modules = rawModules.filter((module): module is ResumeModule => (
    DEFAULT_MODULE_ORDER.includes(module as ResumeModule)
  ))
  const missing = DEFAULT_MODULE_ORDER.filter((module) => !modules.includes(module))
  return [...modules, ...missing]
}

// 用于补齐旧布局配置的可见模块集合。
function normalizeVisibleModules(rawVisible: unknown): Set<ResumeModule> {
  if (!Array.isArray(rawVisible)) return new Set(DEFAULT_MODULE_ORDER)
  const visible = rawVisible.filter((module): module is ResumeModule => (
    DEFAULT_MODULE_ORDER.includes(module as ResumeModule)
  ))
  return new Set(visible)
}

/**
 * 将布局配置转换成预览和编辑器共用的模块列表。
 */
// 用于构建模块配置。
export function buildModuleConfig(
  moduleOrder: ResumeModule[],
  visibleModules: Set<ResumeModule>,
): ModuleConfig[] {
  return moduleOrder.map((module, index) => ({
    type: module,
    visible: visibleModules.has(module),
    order: index,
    label: MODULE_LABELS[module],
  }))
}

// 用于返回按布局顺序过滤后的可见简历模块配置。
export function buildVisibleModuleConfig(config: ResumeLayoutConfig): ModuleConfig[] {
  return buildModuleConfig(config.moduleOrder, config.visibleModules)
    .filter((module) => module.visible)
    .sort((a, b) => a.order - b.order)
}

// 用于让编辑器板块顺序跟随简历预览板块顺序。
export function buildResumeEditorSections(
  config: ResumeLayoutConfig,
  t: ResumeEditorTranslate,
): ResumeEditorSection[] {
  const orderedSections = config.moduleOrder
    .filter((module) => config.visibleModules.has(module))
    .map((module) => MODULE_TO_EDITOR_SECTION[module])

  return ['job_application', ...orderedSections].map((key) => ({
    key,
    label: t(SECTION_LABEL_KEYS[key]),
  }))
}

/**
 * 默认模块配置列表。
 */
export const DEFAULT_MODULE_CONFIG: ModuleConfig[] = buildModuleConfig(
  DEFAULT_MODULE_ORDER,
  new Set(DEFAULT_MODULE_ORDER),
)

/**
 * 简历布局配置接口
 */
export interface ResumeLayoutConfig {
  density: LayoutDensity
  moduleOrder: ResumeModule[]
  visibleModules: Set<ResumeModule>
  spacingScale: number  // 连续间距缩放，范围 0.5–1.8，默认 1.0
  templateStyle: ResumeTemplateStyle
}

/**
 * 默认布局配置
 */
export const DEFAULT_LAYOUT_CONFIG: ResumeLayoutConfig = {
  density: 'normal',
  moduleOrder: DEFAULT_MODULE_ORDER,
  visibleModules: new Set(DEFAULT_MODULE_ORDER),
  spacingScale: 1.0,
  templateStyle: 'classic',
}

// 用于复制布局配置，避免调用方重复手写 Set 和数组拷贝规则。
function cloneLayoutConfig(config: ResumeLayoutConfig): ResumeLayoutConfig {
  return {
    density: config.density,
    moduleOrder: [...config.moduleOrder],
    visibleModules: new Set(config.visibleModules),
    spacingScale: config.spacingScale,
    templateStyle: config.templateStyle,
  }
}

// 用于切换简历模板样式。
export function setResumeTemplateStyle(
  config: ResumeLayoutConfig,
  templateStyle: ResumeTemplateStyle,
): ResumeLayoutConfig {
  return { ...cloneLayoutConfig(config), templateStyle }
}

// 用于应用密度预设并同步 spacingScale。
export function setResumeLayoutDensity(
  config: ResumeLayoutConfig,
  density: LayoutDensity,
): ResumeLayoutConfig {
  const spacingScale = DENSITY_SPACING_SCALE[density as Exclude<LayoutDensity, 'custom'>] ?? config.spacingScale
  return { ...cloneLayoutConfig(config), density, spacingScale }
}

// 用于把连续间距调整转换成自定义密度配置。
export function setResumeSpacingScale(
  config: ResumeLayoutConfig,
  spacingScale: number,
): ResumeLayoutConfig {
  return {
    ...cloneLayoutConfig(config),
    density: 'custom',
    spacingScale: clampResumeSpacingScale(spacingScale),
  }
}

// 用于重置间距为 normal。
export function resetResumeSpacingScale(config: ResumeLayoutConfig): ResumeLayoutConfig {
  return {
    ...cloneLayoutConfig(config),
    density: 'normal',
    spacingScale: 1.0,
  }
}

// 用于切换简历模块显隐。
export function toggleResumeModuleVisibility(
  config: ResumeLayoutConfig,
  module: ResumeModule,
): ResumeLayoutConfig {
  const nextConfig = cloneLayoutConfig(config)
  if (nextConfig.visibleModules.has(module)) {
    nextConfig.visibleModules.delete(module)
  } else {
    nextConfig.visibleModules.add(module)
  }
  return nextConfig
}

// 用于按方向移动简历模块。
export function moveResumeModule(
  config: ResumeLayoutConfig,
  module: ResumeModule,
  direction: 'up' | 'down',
): ResumeLayoutConfig {
  const nextConfig = cloneLayoutConfig(config)
  const currentIndex = nextConfig.moduleOrder.indexOf(module)
  if (currentIndex === -1) return nextConfig
  const targetIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1
  if (targetIndex < 0 || targetIndex >= nextConfig.moduleOrder.length) return nextConfig
  ;[nextConfig.moduleOrder[currentIndex], nextConfig.moduleOrder[targetIndex]] =
    [nextConfig.moduleOrder[targetIndex], nextConfig.moduleOrder[currentIndex]]
  return nextConfig
}

// 用于生成布局配置缓存 key。
function getLayoutConfigStorageKey(resumeId: number): string {
  return `resume_layout_${resumeId}`
}

// 用于生成布局配置脏标记 key。
function getLayoutConfigDirtyStorageKey(resumeId: number): string {
  return `resume_layout_${resumeId}_dirty`
}

/**
 * 将服务端返回的 layout_config 原始对象转换为 ResumeLayoutConfig
 */
// 用于反序列化布局配置。
export function deserializeLayoutConfig(raw: Record<string, unknown> | null | undefined): ResumeLayoutConfig {
  if (!raw) return DEFAULT_LAYOUT_CONFIG
  try {
    const rawTemplateStyle = raw.templateStyle
    const templateStyle: ResumeTemplateStyle =
      rawTemplateStyle === 'modern' || rawTemplateStyle === 'formal' || rawTemplateStyle === 'emerald'
        ? rawTemplateStyle
        : 'classic'
    return {
      density: (raw.density as LayoutDensity) || 'normal',
      moduleOrder: normalizeModuleOrder(raw.moduleOrder),
      spacingScale: typeof raw.spacingScale === 'number' ? clampResumeSpacingScale(raw.spacingScale) : 1.0,
      visibleModules: normalizeVisibleModules(raw.visibleModules),
      templateStyle,
    }
  } catch {
    return DEFAULT_LAYOUT_CONFIG
  }
}

/**
 * 将 ResumeLayoutConfig 序列化为可存 JSON 的对象（Set → Array）
 */
// 用于序列化布局配置。
export function serializeLayoutConfig(config: ResumeLayoutConfig) {
  return {
    density: config.density,
    moduleOrder: config.moduleOrder,
    visibleModules: Array.from(config.visibleModules),
    spacingScale: config.spacingScale,
    templateStyle: config.templateStyle,
  }
}

/**
 * 保存布局配置到 localStorage（作为离线缓存）
 */
// 用于保存布局配置。
export function saveLayoutConfig(
  resumeId: number,
  config: ResumeLayoutConfig,
  options: { dirty?: boolean } = {},
): void {
  localStorage.setItem(getLayoutConfigStorageKey(resumeId), JSON.stringify(serializeLayoutConfig(config)))
  localStorage.setItem(getLayoutConfigDirtyStorageKey(resumeId), options.dirty ? '1' : '0')
}

/**
 * 从 localStorage 加载布局配置（用于首次渲染前的占位，避免闪烁）
 */
// 用于加载布局配置。
export function loadLayoutConfig(resumeId: number): ResumeLayoutConfig {
  const stored = localStorage.getItem(getLayoutConfigStorageKey(resumeId))
  if (!stored) return DEFAULT_LAYOUT_CONFIG
  try {
    const parsed = JSON.parse(stored)
    return deserializeLayoutConfig(parsed)
  } catch {
    return DEFAULT_LAYOUT_CONFIG
  }
}

/**
 * 判断本地布局缓存是否还有未确认同步到服务端的更改。
 */
// 用于读取布局配置脏标记。
export function isLayoutConfigDirty(resumeId: number): boolean {
  return localStorage.getItem(getLayoutConfigDirtyStorageKey(resumeId)) === '1'
}

/**
 * 将布局配置持久化到服务端，同时更新 localStorage 缓存
 * debounce 由调用方控制（edit/page.tsx 中 800ms）
 */
// 用于保存布局配置to服务端。
export async function saveLayoutConfigToServer(
  resumeId: number,
  config: ResumeLayoutConfig,
  options: { keepalive?: boolean } = {},
): Promise<void> {
  // 同步更新本地缓存
  saveLayoutConfig(resumeId, config, { dirty: true })

  const response = await fetch(apiUrl(`/api/resumes/${resumeId}/layout`), {
    method: 'PUT',
    credentials: 'include',
    keepalive: options.keepalive,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(serializeLayoutConfig(config)),
  })
  if (response.ok) {
    saveLayoutConfig(resumeId, config, { dirty: false })
  }
  // 不抛错误——布局配置保存失败不应中断用户操作
}
