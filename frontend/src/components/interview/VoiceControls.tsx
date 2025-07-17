/**
 * 面试语音控制组件
 * 提供语音播放、暂停、音色选择等功能
 */

import React, { useState, useEffect, useCallback } from 'react'
import { 
  SpeakerWaveIcon, 
  SpeakerXMarkIcon, 
  ArrowPathIcon,
  Cog6ToothIcon 
} from '@heroicons/react/24/outline'
import { ttsService } from '@/lib/tts'

interface VoiceConfig {
  voice_id: string
  emotion: string
  description: string
}

interface VoiceControlsProps {
  questionText: string
  isVisible?: boolean
  autoPlay?: boolean
  onVoiceStart?: () => void
  onVoiceEnd?: () => void
  onVoiceError?: (error: Error) => void
}

export default function VoiceControls({
  questionText,
  isVisible = true,
  autoPlay = false,
  onVoiceStart,
  onVoiceEnd,
  onVoiceError
}: VoiceControlsProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [voiceConfigs, setVoiceConfigs] = useState<Record<string, VoiceConfig>>({})
  const [selectedVoice, setSelectedVoice] = useState<string>('professional')
  const [showSettings, setShowSettings] = useState(false)

  // 获取面试官音色配置
  useEffect(() => {
    const loadVoiceConfigs = async () => {
      try {
        const configs = await ttsService.getInterviewerVoices()
        setVoiceConfigs(configs)
      } catch (error) {
        console.error('加载音色配置失败:', error)
      }
    }
    
    loadVoiceConfigs()
  }, [])

  // 自动播放逻辑
  const [lastAutoPlayedText, setLastAutoPlayedText] = useState<string>('')
  
  useEffect(() => {
    if (autoPlay && 
        questionText && 
        questionText.trim() && 
        questionText !== lastAutoPlayedText && 
        !isPlaying && 
        !isLoading) {
      // 延迟500ms开始播放，避免与其他操作冲突
      const timer = setTimeout(async () => {
        // 直接调用播放逻辑，避免依赖循环
        if (!questionText.trim()) return

        setIsLoading(true)
        setIsPlaying(true)
        onVoiceStart?.()

        try {
          const voiceConfig = voiceConfigs[selectedVoice]
          
          const response = await ttsService.generateInterviewQuestionSpeech(
            questionText,
            voiceConfig
          )

          if (response.success && response.data.audio_url) {
            await ttsService.playAudio(response.data.audio_url)
          } else if (response.success && response.data.audio_base64) {
            await ttsService.playBase64Audio(response.data.audio_base64, response.data.format)
          } else {
            throw new Error('语音生成失败')
          }

          onVoiceEnd?.()
          setLastAutoPlayedText(questionText)
        } catch (error) {
          console.error('自动播放语音错误:', error)
          onVoiceError?.(error as Error)
        } finally {
          setIsLoading(false)
          setIsPlaying(false)
        }
      }, 500)
      
      return () => clearTimeout(timer)
    }
  }, [autoPlay, questionText, isPlaying, isLoading, lastAutoPlayedText, voiceConfigs, selectedVoice, onVoiceStart, onVoiceEnd, onVoiceError])

  // 播放语音
  const handlePlayVoice = useCallback(async () => {
    if (isPlaying) {
      // 停止播放
      ttsService.stopAudio()
      setIsPlaying(false)
      onVoiceEnd?.()
      return
    }

    if (!questionText.trim()) {
      return
    }

    setIsLoading(true)
    setIsPlaying(true)
    onVoiceStart?.()

    try {
      const voiceConfig = voiceConfigs[selectedVoice]
      
      // 生成语音
      const response = await ttsService.generateInterviewQuestionSpeech(
        questionText,
        voiceConfig
      )

      if (response.success && response.data.audio_url) {
        // 播放语音
        await ttsService.playAudio(response.data.audio_url)
      } else if (response.success && response.data.audio_base64) {
        // 播放Base64音频
        await ttsService.playBase64Audio(response.data.audio_base64, response.data.format)
      } else {
        throw new Error('语音生成失败')
      }

      onVoiceEnd?.()
    } catch (error) {
      console.error('语音播放错误:', error)
      onVoiceError?.(error as Error)
    } finally {
      setIsLoading(false)
      setIsPlaying(false)
    }
  }, [questionText, voiceConfigs, selectedVoice, onVoiceStart, onVoiceEnd, onVoiceError])

  // 音色选择
  const handleVoiceChange = (voiceType: string) => {
    setSelectedVoice(voiceType)
    setShowSettings(false)
  }

  if (!isVisible) {
    return null
  }

  return (
    <div className="flex items-center space-x-2">
      {/* 播放/停止按钮 */}
      <button
        onClick={handlePlayVoice}
        disabled={isLoading}
        className={`
          p-2 rounded-full transition-colors
          ${isPlaying 
            ? 'bg-red-100 text-red-600 hover:bg-red-200' 
            : 'bg-blue-100 text-blue-600 hover:bg-blue-200'
          }
          ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
        `}
        title={isPlaying ? '停止播放' : '播放语音'}
      >
        {isLoading ? (
          <ArrowPathIcon className="w-5 h-5 animate-spin" />
        ) : isPlaying ? (
          <SpeakerXMarkIcon className="w-5 h-5" />
        ) : (
          <SpeakerWaveIcon className="w-5 h-5" />
        )}
      </button>

      {/* 音色设置 */}
      <div className="relative">
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="p-2 rounded-full bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
          title="音色设置"
        >
          <Cog6ToothIcon className="w-5 h-5" />
        </button>

        {/* 音色选择下拉菜单 */}
        {showSettings && (
          <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 z-10">
            <div className="py-1">
              <div className="px-3 py-2 text-xs font-medium text-gray-500 border-b border-gray-200">
                选择面试官音色
              </div>
              {Object.entries(voiceConfigs).map(([key, config]) => (
                <button
                  key={key}
                  onClick={() => handleVoiceChange(key)}
                  className={`
                    w-full text-left px-3 py-2 text-sm hover:bg-gray-50 transition-colors
                    ${selectedVoice === key ? 'bg-blue-50 text-blue-600' : 'text-gray-700'}
                  `}
                >
                  <div className="font-medium">{config.description}</div>
                  <div className="text-xs text-gray-500">
                    {config.emotion === 'neutral' ? '中性' : 
                     config.emotion === 'happy' ? '友好' : 
                     config.emotion === 'sad' ? '严肃' : config.emotion}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 当前音色指示 */}
      {voiceConfigs[selectedVoice] && (
        <div className="text-xs text-gray-500">
          {voiceConfigs[selectedVoice].description}
        </div>
      )}
    </div>
  )
}