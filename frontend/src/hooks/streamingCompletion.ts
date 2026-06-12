// 用于收口流式消息结束时 live 状态到历史消息的接力顺序。

// 先提交最终消息，再清理 live 状态，避免 UI 出现一帧空白闪烁。
export function commitCompletedStreamMessage<TMessage>(
  message: TMessage,
  appendMessage: ((message: TMessage) => void) | undefined,
  clearLiveState: () => void,
) {
  appendMessage?.(message)
  clearLiveState()
}
