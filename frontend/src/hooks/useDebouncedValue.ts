/**
 * 防抖值 Hook
 *
 * 用于延迟响应频繁变化的值（如简历 content），避免每次击键都触发昂贵的下游渲染。
 */

'use client'

import { useEffect, useState } from 'react'

/**
 * 返回一个延迟 delay 毫秒更新的值。
 * 在 delay 时间内输入值频繁变化时，只会在最后一次变化后 delay 毫秒才更新输出。
 */
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => clearTimeout(timer)
  }, [value, delay])

  return debouncedValue
}
