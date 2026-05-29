/**
 * 简历布局配置模块
 * 
 * 管理简历的视觉密度、间距、模块顺序等配置
 */

import type { ModuleConfig, ResumeModule, ResumeTemplateStyle } from '@/types/resumeLayout'
import { apiUrl } from '@/lib/httpClient'

export type { ModuleConfig, ResumeModule, ResumeTemplateStyle } from '@/types/resumeLayout'

export type LayoutDensity = 'comfortable' | 'normal' | 'compact' | 'custom'

export const TEMPLATE_STYLE_LABELS: Record<ResumeTemplateStyle, string> = {
  classic: 'Classic',
  modern: 'Modern',
  formal: 'Formal',
  emerald: 'Emerald',
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
  'skills'
]

/**
 * 模块显示名称
 */
export const MODULE_LABELS: Record<ResumeModule, string> = {
  personal: 'Personal info',
  summary: 'Summary',
  education: 'Education',
  work: 'Work experience',
  skills: 'Skills',
  projects: 'Projects'
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
  if (!rawVisible.includes('summary')) visible.push('summary')
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
  spacingScale: number  // 连续间距缩放，范围 0.5–4.0，默认 1.0
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
      spacingScale: typeof raw.spacingScale === 'number' ? raw.spacingScale : 1.0,
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
export function saveLayoutConfig(resumeId: number, config: ResumeLayoutConfig): void {
  const key = `resume_layout_${resumeId}`
  localStorage.setItem(key, JSON.stringify(serializeLayoutConfig(config)))
}

/**
 * 从 localStorage 加载布局配置（用于首次渲染前的占位，避免闪烁）
 */
// 用于加载布局配置。
export function loadLayoutConfig(resumeId: number): ResumeLayoutConfig {
  const key = `resume_layout_${resumeId}`
  const stored = localStorage.getItem(key)
  if (!stored) return DEFAULT_LAYOUT_CONFIG
  try {
    const parsed = JSON.parse(stored)
    return deserializeLayoutConfig(parsed)
  } catch {
    return DEFAULT_LAYOUT_CONFIG
  }
}

/**
 * 将布局配置持久化到服务端，同时更新 localStorage 缓存
 * debounce 由调用方控制（edit/page.tsx 中 800ms）
 */
// 用于保存布局配置to服务端。
export async function saveLayoutConfigToServer(resumeId: number, config: ResumeLayoutConfig): Promise<void> {
  // 同步更新本地缓存
  saveLayoutConfig(resumeId, config)

  await fetch(apiUrl(`/api/resumes/${resumeId}/layout`), {
    method: 'PUT',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(serializeLayoutConfig(config)),
  })
  // 不抛错误——布局配置保存失败不应中断用户操作
}
