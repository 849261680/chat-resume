// 提供智能一页算法中可独立测试的核心常量和结果构造。
import {
  MAX_RESUME_SPACING_SCALE,
  MIN_RESUME_SPACING_SCALE,
  RESUME_SPACING_SCALE_STEP,
} from '../../../lib/resumeSpacingScale'
import { getPageContentHeight } from './useLineBasedPagination'

export const MIN_SPACING_SCALE = MIN_RESUME_SPACING_SCALE
export const MAX_SPACING_SCALE = MAX_RESUME_SPACING_SCALE
export const SPACING_SCALE_STEP = RESUME_SPACING_SCALE_STEP
export const SMART_FIT_PAGE_TOLERANCE = 4
const SPACING_SCALE_PRECISION = (String(SPACING_SCALE_STEP).split('.')[1] ?? '').length

export type TooMuchContentResult = {
  status: 'too_much_content'
  pages: number
  appliedScale: number
}

export type SmartFitCoreResult =
  | { status: 'already_fits'; finalMeasureScale: number }
  | { status: 'failed'; finalMeasureScale: number }
  | { status: 'success'; oldScale: number; newScale: number; finalMeasureScale: number }
  | (TooMuchContentResult & { finalMeasureScale: number })

interface SmartFitCoreOptions {
  currentScale: number
  fullBleed?: boolean
  measureContentBottom: (scale: number) => Promise<number>
  shouldAbort?: () => boolean
}

// 用于计算当前模板页面允许的内容底线。
export function getSmartFitPageBottom(fullBleed = false): number {
  return getPageContentHeight({ fullBleed })
}

// 将试算结果落到可控步长，避免布局滑块出现过细的小数。
function roundToSpacingStep(scale: number) {
  return Math.round(scale / SPACING_SCALE_STEP) * SPACING_SCALE_STEP
}

// 向下对齐到可控步长，避免取整后把最后一行推过目标底线。
function floorToSpacingStep(scale: number) {
  return Math.floor(scale / SPACING_SCALE_STEP) * SPACING_SCALE_STEP
}

// 将 scale 限制在简历密度允许范围内。
function clampSpacingScale(scale: number) {
  return Math.max(MIN_SPACING_SCALE, Math.min(MAX_SPACING_SCALE, scale))
}

// 将 scale 对齐到滑块步长的小数精度。
function normalizeSpacingScale(scale: number) {
  return Number(scale.toFixed(SPACING_SCALE_PRECISION))
}

// 计算下一个可尝试的滑块步长。
function getNextSpacingStep(scale: number) {
  return clampSpacingScale(normalizeSpacingScale(scale + SPACING_SCALE_STEP))
}

// 判断两个 scale 是否已经落在同一个滑块步长内。
function isSameSpacingStep(scale: number, currentScale: number) {
  return Math.abs(scale - currentScale) < SPACING_SCALE_STEP / 2
}

// 在区间内搜索不超过页面底线的最大 scale。
async function searchLargestFittingScale(
  loScale: number,
  hiScale: number,
  limitBottom: number,
  measure: (scale: number) => Promise<number>,
  shouldAbort: () => boolean,
) {
  let lo = loScale
  let hi = hiScale
  let bestScale = loScale

  for (let i = 0; i < 8; i++) {
    if (shouldAbort()) return null
    const mid = (lo + hi) / 2
    const height = await measure(mid)
    if (height <= limitBottom) {
      bestScale = mid
      lo = mid
      continue
    }
    hi = mid
  }

  return bestScale
}

// 为当前已经一页的内容寻找更接近底线的宽松 scale。
async function findScaleForFittingContent(
  currentScale: number,
  currentContentBottom: number,
  pageBottom: number,
  measure: (scale: number) => Promise<number>,
  shouldAbort: () => boolean,
) {
  if (Math.abs(currentContentBottom - pageBottom) <= SMART_FIT_PAGE_TOLERANCE) {
    return currentScale
  }

  const minContentBottom = await measure(MIN_SPACING_SCALE)
  if (shouldAbort()) return null

  const maxContentBottom = await measure(MAX_SPACING_SCALE)
  if (shouldAbort()) return null

  if (maxContentBottom <= pageBottom) {
    return MAX_SPACING_SCALE
  }
  if (minContentBottom > pageBottom) {
    return MIN_SPACING_SCALE
  }

  const bestScale = await searchLargestFittingScale(
    MIN_SPACING_SCALE,
    MAX_SPACING_SCALE,
    pageBottom,
    measure,
    shouldAbort,
  )
  return bestScale === null ? null : bestScale
}

// 为当前超页的内容寻找能压回一页的最大 scale。
async function findScaleForOverflowingContent(
  currentScale: number,
  pageBottom: number,
  measure: (scale: number) => Promise<number>,
  shouldAbort: () => boolean,
) {
  const minContentBottom = await measure(MIN_SPACING_SCALE)
  if (shouldAbort()) return null
  if (minContentBottom > pageBottom) {
    return { status: 'too_much_content' as const, pages: Math.ceil(minContentBottom / pageBottom) }
  }

  const bestScale = await searchLargestFittingScale(
    MIN_SPACING_SCALE,
    currentScale,
    pageBottom,
    measure,
    shouldAbort,
  )
  if (bestScale === null) return null

  return { status: 'fits' as const, scale: bestScale }
}

// 确保步长取整后的 scale 不会重新溢出页面。
async function backOffUntilFits(
  scale: number,
  pageBottom: number,
  measure: (scale: number) => Promise<number>,
) {
  let bestScale = scale
  let verifyBottom = await measure(bestScale)

  while (verifyBottom > pageBottom && bestScale > MIN_SPACING_SCALE) {
    bestScale = Math.max(MIN_SPACING_SCALE, bestScale - SPACING_SCALE_STEP)
    verifyBottom = await measure(bestScale)
  }

  return bestScale
}

// 向上补探步长，避免二分搜索的浮点误差少放大一档。
async function advanceUntilLimitExceeded(
  scale: number,
  limitBottom: number,
  measure: (scale: number) => Promise<number>,
  shouldAbort: () => boolean,
) {
  let bestScale = scale

  while (bestScale < MAX_SPACING_SCALE) {
    if (shouldAbort()) return null
    const nextScale = getNextSpacingStep(bestScale)
    if (nextScale <= bestScale) return bestScale
    const nextBottom = await measure(nextScale)
    if (nextBottom > limitBottom) return bestScale
    bestScale = nextScale
  }

  return bestScale
}

// 用于执行智能一页的纯搜索逻辑。
export async function calculateSmartFitScale({
  currentScale,
  fullBleed = false,
  measureContentBottom,
  shouldAbort = () => false,
}: SmartFitCoreOptions): Promise<SmartFitCoreResult> {
  let finalMeasureScale = currentScale
  const measure = async (scale: number) => {
    finalMeasureScale = scale
    return measureContentBottom(scale)
  }

  const currentContentBottom = await measure(currentScale)
  const currentPageBottom = getSmartFitPageBottom(fullBleed)
  if (shouldAbort()) return { status: 'failed', finalMeasureScale }

  if (currentContentBottom <= currentPageBottom) {
    const relaxedScale = await findScaleForFittingContent(
      currentScale,
      currentContentBottom,
      currentPageBottom,
      measure,
      shouldAbort,
    )
    if (relaxedScale === null) return { status: 'failed', finalMeasureScale }

    const steppedScale = clampSpacingScale(floorToSpacingStep(relaxedScale))
    const bestScale = await advanceUntilLimitExceeded(
      steppedScale,
      currentPageBottom,
      measure,
      shouldAbort,
    )
    if (bestScale === null) return { status: 'failed', finalMeasureScale }

    if (isSameSpacingStep(bestScale, currentScale)) {
      finalMeasureScale = currentScale
      return { status: 'already_fits', finalMeasureScale }
    }

    finalMeasureScale = bestScale
    return { status: 'success', oldScale: currentScale, newScale: bestScale, finalMeasureScale }
  }

  const overflowResult = await findScaleForOverflowingContent(
    currentScale,
    currentPageBottom,
    measure,
    shouldAbort,
  )
  if (overflowResult === null) return { status: 'failed', finalMeasureScale }

  if (overflowResult.status === 'too_much_content') {
    return {
      status: 'too_much_content',
      pages: overflowResult.pages,
      appliedScale: MIN_SPACING_SCALE,
      finalMeasureScale: MIN_SPACING_SCALE,
    }
  }

  const roundedScale = clampSpacingScale(roundToSpacingStep(overflowResult.scale))
  const bestScale = await backOffUntilFits(roundedScale, currentPageBottom, measure)

  if (isSameSpacingStep(bestScale, currentScale)) {
    finalMeasureScale = currentScale
    return { status: 'already_fits', finalMeasureScale }
  }

  finalMeasureScale = bestScale
  return { status: 'success', oldScale: currentScale, newScale: bestScale, finalMeasureScale }
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
