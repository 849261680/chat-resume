// 提供智能一页算法中可独立测试的核心常量和结果构造。
import {
  MAX_RESUME_SPACING_SCALE,
  MIN_RESUME_SPACING_SCALE,
  RESUME_SPACING_SCALE_STEP,
} from '../../../lib/resumeSpacingScale'

export const MIN_SPACING_SCALE = MIN_RESUME_SPACING_SCALE
export const MAX_SPACING_SCALE = MAX_RESUME_SPACING_SCALE
export const SPACING_SCALE_STEP = RESUME_SPACING_SCALE_STEP
export const SMART_FIT_TARGET_BOTTOM_GAP = 36
export const SMART_FIT_TARGET_TOLERANCE = 4

export type TooMuchContentResult = {
  status: 'too_much_content'
  pages: number
  appliedScale: number
}

// 在内容仍超页时应用最小间距，并返回带有已应用 scale 的失败结果。
export function applyTooMuchContentFallback(
  pages: number,
  onComplete: (newScale: number) => void,
): TooMuchContentResult {
  onComplete(MIN_SPACING_SCALE)
  return {
    status: 'too_much_content',
    pages,
    appliedScale: MIN_SPACING_SCALE,
  }
}
