/**
 * 语音录制组件
 * 集成火山引擎ASR实现语音转文字功能
 */

import React, { useState, useEffect, useRef, forwardRef, useImperativeHandle } from 'react'
import { 
  MicrophoneIcon, 
  StopIcon, 
  SpeakerWaveIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline'
import { asrService } from '@/lib/asr'
import toast from 'react-hot-toast'

interface VoiceRecorderProps {
  onTranscriptionComplete?: (text: string) => void
  onRecordingStateChange?: (isRecording: boolean) => void
  onError?: (error: string) => void
  disabled?: boolean
  className?: string
}

export interface VoiceRecorderRef {
  startRecording: () => Promise<void>
  stopRecording: () => Promise<void>
  isRecording: boolean
}

interface RecordingState {
  isRecording: boolean
  isProcessing: boolean
  hasPermission: boolean
  isSupported: boolean
  audioLevel: number
  recordingTime: number
}

const VoiceRecorder = forwardRef<VoiceRecorderRef, VoiceRecorderProps>(({
  onTranscriptionComplete,
  onRecordingStateChange,
  onError,
  disabled = false,
  className = ''
}, ref) => {
  const [state, setState] = useState<RecordingState>({
    isRecording: false,
    isProcessing: false,
    hasPermission: false,
    isSupported: false,
    audioLevel: 0,
    recordingTime: 0
  })
  
  const [transcriptionText, setTranscriptionText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const recordingTimer = useRef<NodeJS.Timeout | null>(null)
  const audioLevelInterval = useRef<NodeJS.Timeout | null>(null)

  // 检查浏览器支持和权限
  useEffect(() => {
    const checkSupport = async () => {
      // 更详细的浏览器支持检查
      const checks = {
        mediaDevices: !!(navigator.mediaDevices),
        getUserMedia: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia),
        mediaRecorder: !!(window.MediaRecorder),
        isSecureContext: window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost'
      }
      
      console.log('浏览器功能检查:', checks)
      
      const isSupported = checks.mediaDevices && checks.getUserMedia && checks.mediaRecorder
      
      if (!checks.isSecureContext) {
        console.warn('警告: 需要HTTPS环境才能使用麦克风功能')
      }
      
      setState(prev => ({ ...prev, isSupported }))
      
      if (isSupported) {
        // 预先请求麦克风权限
        try {
          console.log('VoiceRecorder: 开始请求麦克风权限...')
          const hasPermission = await asrService.requestMicrophonePermission()
          console.log('VoiceRecorder: 麦克风权限结果:', hasPermission)
          setState(prev => ({ ...prev, hasPermission }))
        } catch (error) {
          console.error('VoiceRecorder: 权限检查失败:', error)
          setState(prev => ({ ...prev, hasPermission: false }))
        }
      } else {
        // 详细的不支持原因
        const reasons = []
        if (!checks.mediaDevices) reasons.push('navigator.mediaDevices')
        if (!checks.getUserMedia) reasons.push('getUserMedia')
        if (!checks.mediaRecorder) reasons.push('MediaRecorder')
        if (!checks.isSecureContext) reasons.push('HTTPS/安全上下文')
        
        console.error('浏览器不支持录音功能，缺少:', reasons.join(', '))
      }
    }

    checkSupport()
  }, [])

  // 清理计时器
  useEffect(() => {
    return () => {
      if (recordingTimer.current) {
        clearInterval(recordingTimer.current)
      }
      if (audioLevelInterval.current) {
        clearInterval(audioLevelInterval.current)
      }
    }
  }, [])

  // 暴露方法给父组件
  useImperativeHandle(ref, () => ({
    startRecording,
    stopRecording,
    isRecording: state.isRecording
  }), [state.isRecording])

  // 开始录音
  const startRecording = async () => {
    console.log('VoiceRecorder: 开始录音被调用', { 
      isSupported: state.isSupported, 
      hasPermission: state.hasPermission 
    })
    
    try {
      setState(prev => ({ ...prev, isRecording: true, recordingTime: 0 }))
      setError(null)
      setTranscriptionText('')
      
      console.log('VoiceRecorder: 调用ASR服务开始录音...')
      // 直接调用ASR服务，让它进行详细的兼容性检查
      await asrService.startRecording()
      console.log('VoiceRecorder: ASR服务开始录音成功')
      
      // 开始计时
      recordingTimer.current = setInterval(() => {
        setState(prev => ({ ...prev, recordingTime: prev.recordingTime + 1 }))
      }, 1000)
      
      // 模拟音频级别变化（实际应用中应该从真实音频流获取）
      audioLevelInterval.current = setInterval(() => {
        const level = Math.random() * 0.8 + 0.2 // 0.2-1.0
        setState(prev => ({ ...prev, audioLevel: level }))
      }, 100)
      
      onRecordingStateChange?.(true)
      toast.success('开始录音')
      
    } catch (error) {
      console.error('开始录音失败:', error)
      let errorMsg = '开始录音失败'
      
      if (error instanceof Error) {
        if (error.name === 'NotAllowedError') {
          errorMsg = '麦克风权限被拒绝，请在浏览器设置中允许访问麦克风'
        } else if (error.name === 'NotFoundError') {
          errorMsg = '未找到可用的麦克风设备'
        } else if (error.name === 'NotSupportedError') {
          errorMsg = '浏览器不支持当前的录音格式'
        } else if (error.name === 'NotReadableError') {
          errorMsg = '麦克风设备正在被其他应用程序使用'
        } else {
          errorMsg = error.message
        }
      }
      
      setError(errorMsg)
      onError?.(errorMsg)
      setState(prev => ({ ...prev, isRecording: false }))
      toast.error(errorMsg)
    }
  }

  // 停止录音并识别
  const stopRecording = async () => {
    if (!state.isRecording) return

    try {
      setState(prev => ({ 
        ...prev, 
        isRecording: false, 
        isProcessing: true,
        audioLevel: 0
      }))
      
      // 清理计时器
      if (recordingTimer.current) {
        clearInterval(recordingTimer.current)
        recordingTimer.current = null
      }
      if (audioLevelInterval.current) {
        clearInterval(audioLevelInterval.current)
        audioLevelInterval.current = null
      }
      
      onRecordingStateChange?.(false)
      
      // 停止录音并获取音频数据
      const audioBlob = await asrService.stopRecording()
      
      if (audioBlob) {
        // 执行语音识别
        const result = await asrService.recognizeAudio(audioBlob)
        
        if (result.success && result.text) {
          setTranscriptionText(result.text)
          onTranscriptionComplete?.(result.text)
          toast.success('语音识别完成')
        } else {
          const errorMsg = result.error || '语音识别失败'
          setError(errorMsg)
          onError?.(errorMsg)
          toast.error(errorMsg)
        }
      } else {
        const errorMsg = '录音数据获取失败'
        setError(errorMsg)
        onError?.(errorMsg)
        toast.error(errorMsg)
      }
      
    } catch (error) {
      console.error('停止录音失败:', error)
      const errorMsg = error instanceof Error ? error.message : '停止录音失败'
      setError(errorMsg)
      onError?.(errorMsg)
      toast.error(errorMsg)
    } finally {
      setState(prev => ({ ...prev, isProcessing: false }))
    }
  }

  // 格式化录音时间
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  // 权限提示 - 只在明确不支持时显示警告，但不阻止功能
  const showCompatibilityWarning = !state.isSupported && (
    !window.isSecureContext && location.protocol !== 'https:' && location.hostname !== 'localhost'
  )
  
  if (showCompatibilityWarning) {
    // 只在非HTTPS环境下显示警告，但仍然允许尝试使用
    return (
      <div className={`space-y-4 ${className}`}>
        <div className="flex flex-col space-y-2 p-3 bg-yellow-50 rounded-lg border border-yellow-200">
          <div className="flex items-center space-x-2">
            <ExclamationTriangleIcon className="w-5 h-5 text-yellow-500" />
            <span className="text-sm text-yellow-700">检测到浏览器兼容性问题</span>
          </div>
          <div className="text-xs text-yellow-600 pl-7">
            当前非HTTPS环境，麦克风功能可能受限。建议使用HTTPS访问或更新浏览器。
          </div>
        </div>
        {/* 仍然显示录音界面，让用户可以尝试 */}
        {renderRecordingInterface()}
      </div>
    )
  }

  // 权限棐示，但不阻止使用
  const showPermissionWarning = state.isSupported && !state.hasPermission
  
  // 渲染录音界面的函数
  const renderRecordingInterface = () => (

    <div className={`space-y-4 ${className}`}>
      {/* 权限警告 */}
      {showPermissionWarning && (
        <div className="flex flex-col space-y-2 p-3 bg-yellow-50 rounded-lg border border-yellow-200">
          <div className="flex items-center space-x-2">
            <ExclamationTriangleIcon className="w-5 h-5 text-yellow-500" />
            <span className="text-sm text-yellow-700">需要麦克风权限</span>
          </div>
          <div className="text-xs text-yellow-600 pl-7">
            点击录音按钮时会请求麦克风权限，请在浏览器弹窗中选择"允许"
          </div>
        </div>
      )}
    
      {/* 录音控制区域 */}
      {/* 录音控制区域 */}
      <div className="flex items-center space-x-4">
        {/* 录音按钮 */}
        <button
          onClick={state.isRecording ? stopRecording : startRecording}
          disabled={disabled || state.isProcessing}
          className={`
            relative flex items-center justify-center w-12 h-12 rounded-full transition-all duration-200
            ${state.isRecording 
              ? 'bg-red-500 hover:bg-red-600 text-white' 
              : 'bg-blue-500 hover:bg-blue-600 text-white'
            }
            ${disabled || state.isProcessing ? 'opacity-50 cursor-not-allowed' : ''}
          `}
        >
          {state.isProcessing ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : state.isRecording ? (
            <StopIcon className="w-6 h-6" />
          ) : (
            <MicrophoneIcon className="w-6 h-6" />
          )}
          
          {/* 录音时的脉冲动画 */}
          {state.isRecording && (
            <div className="absolute inset-0 rounded-full bg-red-500 animate-ping opacity-75" />
          )}
        </button>

        {/* 录音状态信息 */}
        <div className="flex-1">
          {state.isRecording && (
            <div className="flex items-center space-x-3">
              {/* 音频级别指示器 */}
              <div className="flex items-center space-x-1">
                {[...Array(5)].map((_, i) => (
                  <div
                    key={i}
                    className={`w-1 h-6 rounded-full transition-all duration-100 ${
                      i < state.audioLevel * 5 ? 'bg-red-500' : 'bg-gray-300'
                    }`}
                  />
                ))}
              </div>
              
              {/* 录音时间 */}
              <span className="text-sm font-mono text-gray-600">
                {formatTime(state.recordingTime)}
              </span>
              
              <span className="text-sm text-red-600">正在录音...</span>
            </div>
          )}
          
          {state.isProcessing && (
            <div className="flex items-center space-x-2">
              <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-blue-600">正在识别语音...</span>
            </div>
          )}
          
          {!state.isRecording && !state.isProcessing && (
            <span className="text-sm text-gray-500">
              准备就绪
            </span>
          )}
        </div>
      </div>

      {/* 识别结果显示 */}
      {transcriptionText && (
        <div className="p-4 bg-green-50 rounded-lg border border-green-200">
          <div className="flex items-start space-x-2">
            <CheckCircleIcon className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <div className="text-sm font-medium text-green-800 mb-1">
                识别结果：
              </div>
              <div className="text-sm text-green-700 leading-relaxed">
                {transcriptionText}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div className="p-3 bg-red-50 rounded-lg border border-red-200">
          <div className="flex items-center space-x-2">
            <ExclamationTriangleIcon className="w-5 h-5 text-red-500" />
            <span className="text-sm text-red-700">{error}</span>
          </div>
        </div>
      )}

    </div>
  )
  
  // 返回主界面
  return renderRecordingInterface()
})

VoiceRecorder.displayName = 'VoiceRecorder'

export default VoiceRecorder