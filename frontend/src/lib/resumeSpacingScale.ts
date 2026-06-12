// 提供简历间距缩放的可用范围和夹取工具。

export const MIN_RESUME_SPACING_SCALE = 0.5
export const MAX_RESUME_SPACING_SCALE = 1.3
export const RESUME_SPACING_SCALE_STEP = 0.01

// 用于把旧数据或外部输入限制在专业可读的简历密度范围内。
export function clampResumeSpacingScale(value: number): number {
  if (!Number.isFinite(value)) return 1
  return Math.min(MAX_RESUME_SPACING_SCALE, Math.max(MIN_RESUME_SPACING_SCALE, value))
}
