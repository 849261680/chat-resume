// 用于提供简历要点文本过滤工具。
import type { ResumeBullet } from '@/types/resume'

// 用于返回可在预览中展示的非空要点文本。
export function visibleHighlightTexts(highlights: Array<Partial<ResumeBullet>> | undefined) {
  return (highlights || [])
    .map(item => typeof item.text === 'string' ? item.text.trim() : '')
    .filter(Boolean)
}
