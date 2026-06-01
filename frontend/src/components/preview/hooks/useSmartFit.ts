'use client'
// 用于提供 useSmartFit.ts 对应的前端状态逻辑。

import { useCallback, useRef, useState } from 'react'
import { applyTooMuchContentFallback, MAX_SPACING_SCALE, MIN_SPACING_SCALE, SPACING_SCALE_STEP } from './smartFitCore'
import { A4_HEIGHT, PAGE_PADDING, SAFETY_MARGIN } from './useLineBasedPagination'
import type { RenderableLine } from './useLineBasedPagination'
import type { TooMuchContentResult } from './smartFitCore'

export type SmartFitResult =
  | { status: 'already_fits' }
  | TooMuchContentResult
  | { status: 'success'; oldScale: number; newScale: number }
  | { status: 'failed' }

interface UseSmartFitOptions {
  currentScale: number
  onComplete: (newScale: number) => void
  // 通过 React state 驱动测量容器 scale，避免直接操控 DOM 与 React 冲突
  setMeasureScale: (scale: number) => void
  // 等待 React 将测量容器渲染到指定 scale 后 resolve
  waitForMeasureScale: (targetScale: number) => Promise<void>
  // 与真实页面盒模型一致的行测量逻辑
  measureLines: () => RenderableLine[]
}

// 对于给定的 scale，计算页面内最后一行允许到达的视觉底线。
function effectivePageBottom(scale: number) {
  return A4_HEIGHT - PAGE_PADDING * scale - SAFETY_MARGIN
}

// 将试算结果落到可控步长，避免布局滑块出现过细的小数。
function roundToSpacingStep(scale: number) {
  return Math.round(scale / SPACING_SCALE_STEP) * SPACING_SCALE_STEP
}

// 用于封装智能适配相关状态和行为。
export function useSmartFit({
  currentScale,
  onComplete,
  setMeasureScale,
  waitForMeasureScale,
  measureLines,
}: UseSmartFitOptions) {
  const [isRunning, setIsRunning] = useState(false)
  const abortRef = useRef(false)

  const runSmartFit = useCallback(async (): Promise<SmartFitResult> => {
    if (isRunning) return { status: 'failed' }

    setIsRunning(true)
    abortRef.current = false
    let finalMeasureScale = currentScale

    // 通过 React state 切换测量容器到指定 scale，等待渲染完成后测量
    const measureContentBottom = async (scale: number): Promise<number> => {
      finalMeasureScale = scale
      setMeasureScale(scale)
      await waitForMeasureScale(scale)
      const lines = measureLines()
      return lines.reduce((bottom, line) => Math.max(bottom, line.bottom), 0)
    }

    try {
      // 当前 scale 下内容在真实页面中的视觉底线
      const currentContentBottom = await measureContentBottom(currentScale)
      const currentPageBottom = effectivePageBottom(currentScale)

      if (abortRef.current) return { status: 'failed' }

      const currentFits = currentContentBottom <= currentPageBottom
      let lo = currentFits ? currentScale : MIN_SPACING_SCALE
      let hi = currentFits ? MAX_SPACING_SCALE : currentScale
      let bestScale = currentFits ? currentScale : MIN_SPACING_SCALE

      if (currentFits) {
        if (currentScale >= MAX_SPACING_SCALE) {
          return { status: 'already_fits' }
        }
        const maxContentBottom = await measureContentBottom(MAX_SPACING_SCALE)
        if (abortRef.current) return { status: 'failed' }
        if (maxContentBottom <= effectivePageBottom(MAX_SPACING_SCALE)) {
          bestScale = MAX_SPACING_SCALE
          onComplete(bestScale)
          finalMeasureScale = bestScale
          return { status: 'success', oldScale: currentScale, newScale: bestScale }
        }
      } else {
        // 检查最小 scale 能否放下；仍放不下时不再尝试布局密度调整。
        const minContentBottom = await measureContentBottom(MIN_SPACING_SCALE)
        const minPageBottom = effectivePageBottom(MIN_SPACING_SCALE)

        if (abortRef.current) return { status: 'failed' }

        if (minContentBottom > minPageBottom) {
          const approxPages = Math.ceil(minContentBottom / minPageBottom)
          const result = applyTooMuchContentFallback(approxPages, onComplete)
          finalMeasureScale = result.appliedScale
          return result
        }
      }

      for (let i = 0; i < 8; i++) {
        if (abortRef.current) return { status: 'failed' }
        const mid = (lo + hi) / 2
        const h = await measureContentBottom(mid)
        if (h <= effectivePageBottom(mid)) {
          bestScale = mid
          lo = mid
        } else {
          hi = mid
        }
      }

      // 取整到 0.05 步长
      bestScale = roundToSpacingStep(bestScale)
      bestScale = Math.max(MIN_SPACING_SCALE, Math.min(MAX_SPACING_SCALE, bestScale))

      // 验证取整后仍能放下
      let verifyBottom = await measureContentBottom(bestScale)
      while (verifyBottom > effectivePageBottom(bestScale) && bestScale > MIN_SPACING_SCALE) {
        bestScale = Math.max(MIN_SPACING_SCALE, bestScale - SPACING_SCALE_STEP)
        verifyBottom = await measureContentBottom(bestScale)
      }

      if (currentFits && bestScale < currentScale) {
        bestScale = currentScale
      }

      if (Math.abs(bestScale - currentScale) < SPACING_SCALE_STEP / 2) {
        finalMeasureScale = currentScale
        return { status: 'already_fits' }
      }

      onComplete(bestScale)
      finalMeasureScale = bestScale
      return { status: 'success', oldScale: currentScale, newScale: bestScale }
    } finally {
      // 保持试算容器停在最后一次已渲染的 scale，避免 finally 再触发一次过期 scale 测量。
      setMeasureScale(finalMeasureScale)
      setIsRunning(false)
    }
  }, [currentScale, isRunning, onComplete, setMeasureScale, waitForMeasureScale, measureLines])

  const abort = useCallback(() => {
    abortRef.current = true
  }, [])

  return { isRunning, runSmartFit, abort }
}
