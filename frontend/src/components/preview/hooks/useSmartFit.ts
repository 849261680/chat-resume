'use client'
// 用于提供 useSmartFit.ts 对应的前端状态逻辑。

import { useCallback, useRef, useState } from 'react'
import {
  applyTooMuchContentFallback,
  calculateSmartFitScale,
} from './smartFitCore'
import type { RenderableLine } from './useLineBasedPagination'
import type { SmartFitCoreResult, TooMuchContentResult } from './smartFitCore'

export type SmartFitResult =
  | { status: 'already_fits' }
  | TooMuchContentResult
  | { status: 'success'; oldScale: number; newScale: number }
  | { status: 'failed' }

interface UseSmartFitOptions {
  currentScale: number
  fullBleed?: boolean
  onComplete: (newScale: number) => void
  // 通过 React state 驱动测量容器 scale，避免直接操控 DOM 与 React 冲突
  setMeasureScale: (scale: number) => void
  // 等待 React 将测量容器渲染到指定 scale 后 resolve
  waitForMeasureScale: (targetScale: number) => Promise<void>
  // 与真实页面盒模型一致的行测量逻辑
  measureLines: () => RenderableLine[]
}

// 将核心算法结果转换为 hook 对外暴露的结果。
function toSmartFitResult(result: SmartFitCoreResult): SmartFitResult {
  if (result.status === 'success') {
    return { status: 'success', oldScale: result.oldScale, newScale: result.newScale }
  }
  if (result.status === 'too_much_content') {
    return { status: 'too_much_content', pages: result.pages, appliedScale: result.appliedScale }
  }
  return { status: result.status }
}

// 用于封装智能适配相关状态和行为。
export function useSmartFit({
  currentScale,
  fullBleed = false,
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
      const result = await calculateSmartFitScale({
        currentScale,
        fullBleed,
        measureContentBottom,
        shouldAbort: () => abortRef.current,
      })
      finalMeasureScale = result.finalMeasureScale

      if (result.status === 'success') {
        onComplete(result.newScale)
      }
      if (result.status === 'too_much_content') {
        return applyTooMuchContentFallback(result.pages, onComplete)
      }

      return toSmartFitResult(result)
    } finally {
      // 保持试算容器停在最后一次已渲染的 scale，避免 finally 再触发一次过期 scale 测量。
      setMeasureScale(finalMeasureScale)
      setIsRunning(false)
    }
  }, [currentScale, fullBleed, isRunning, onComplete, setMeasureScale, waitForMeasureScale, measureLines])

  const abort = useCallback(() => {
    abortRef.current = true
  }, [])

  return { isRunning, runSmartFit, abort }
}
