'use client'
// 用于渲染显隐板块工具的开关样式确认卡片，替代不适合开关语义的内容 diff 格式。

interface SectionVisibilityConfirmCardProps {
  toolName: string
  isShow: boolean
  sectionLabel: string
  stateLabel: string
  reason?: string
  isActivePending: boolean
  expiredLabel: string
  confirmLabel: string
  cancelLabel: string
  onConfirm: () => void
  onReject: () => void
}

// 用于把"显示/隐藏"渲染成只读开关视觉。
function VisibilityToggle({ on }: { on: boolean }) {
  return (
    <span
      className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors"
      style={{ backgroundColor: on ? '#0052ff' : '#cbd5e1' }}
    >
      <span
        className="absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all"
        style={{ left: on ? '18px' : '2px' }}
      />
    </span>
  )
}

// 用于以开关样式确认一次板块显隐操作。
export default function SectionVisibilityConfirmCard({
  toolName,
  isShow,
  sectionLabel,
  stateLabel,
  reason,
  isActivePending,
  expiredLabel,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onReject,
}: SectionVisibilityConfirmCardProps) {
  return (
    <div className="mb-2 rounded-2xl border border-gray-200 bg-white overflow-hidden text-xs shadow-sm">
      <div className="px-4 py-3 bg-white flex items-center gap-2 border-b border-gray-200">
        <span className="font-medium text-gray-900">{toolName}</span>
        <span className="ml-auto" />
        {isActivePending ? (
          <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
        ) : (
          <span className="text-[11px] text-gray-400">{expiredLabel}</span>
        )}
      </div>
      <div className="px-4 py-3 bg-white">
        <div className="font-semibold text-gray-900">{sectionLabel}</div>
        <div className="mt-2 flex items-center justify-between gap-3">
          <span className="text-gray-600">{stateLabel}</span>
          <VisibilityToggle on={isShow} />
        </div>
        {reason ? (
          <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 italic text-amber-700">💡 {reason}</div>
        ) : null}
      </div>
      <div className="px-4 py-3 bg-white border-t border-gray-200 flex gap-2">
        <button
          disabled={!isActivePending}
          onClick={onConfirm}
          className="flex-1 py-1.5 text-xs font-semibold text-white transition-colors disabled:cursor-not-allowed disabled:opacity-50"
          style={{ borderRadius: '56px', backgroundColor: isActivePending ? '#0052ff' : '#94a3b8' }}
        >
          {confirmLabel}
        </button>
        <button
          disabled={!isActivePending}
          onClick={onReject}
          className="flex-1 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50"
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
    </div>
  )
}
