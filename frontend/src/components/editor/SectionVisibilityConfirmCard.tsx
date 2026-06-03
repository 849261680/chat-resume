'use client'
// 显隐板块工具的确认按钮组：仅在等待确认时显示「确认/取消」两个按钮，做出决策后整组消失。

interface SectionVisibilityConfirmCardProps {
  isActivePending: boolean
  confirmLabel: string
  cancelLabel: string
  onConfirm: () => void
  onReject: () => void
}

// 用于以两个按钮确认一次板块显隐操作，不渲染任何额外卡片内容。
export default function SectionVisibilityConfirmCard({
  isActivePending,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onReject,
}: SectionVisibilityConfirmCardProps) {
  if (!isActivePending) return null
  return (
    <div className="mb-2 flex gap-2">
      <button
        onClick={onConfirm}
        className="flex-1 py-1.5 text-xs font-semibold text-white transition-colors"
        style={{ borderRadius: '56px', backgroundColor: '#0052ff' }}
      >
        {confirmLabel}
      </button>
      <button
        onClick={onReject}
        className="flex-1 py-1.5 text-xs font-semibold transition-colors"
        style={{
          borderRadius: '56px',
          border: '1px solid rgba(91,97,110,0.2)',
          backgroundColor: '#ffffff',
          color: '#0a0b0d',
        }}
      >
        {cancelLabel}
      </button>
    </div>
  )
}
