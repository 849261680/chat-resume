/**
 * ASR (自动语音识别) 服务
 * 集成火山引擎端到端实时语音大模型
 */

interface ASRConfig {
  language: string
  sample_rate: number
  format: string
  continuous: boolean
}

interface AudioFormat {
  format: string
  sample_rate: number
  channels: number
  bit_depth: number
  byte_order: string
  encoding: string
}

interface RecognitionResult {
  success: boolean
  text: string
  is_final: boolean
  sequence?: number
  confidence?: number
  word_count?: number
  error?: string
}

interface ASRServiceConfig {
  config: {
    supported_languages: string[]
    audio_format: AudioFormat
    websocket_url: string
    max_duration: number
    streaming_support: boolean
  }
  success: boolean
  message: string
}

class ASRService {
  private apiBase: string
  private websocket: WebSocket | null = null
  private mediaRecorder: MediaRecorder | null = null
  private audioStream: MediaStream | null = null
  private isRecording = false
  private clientId: string
  private audioChunks: Blob[] = []
  private config: ASRServiceConfig | null = null

  constructor() {
    this.apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    this.clientId = this.generateClientId()
  }

  /**
   * 生成客户端ID
   */
  private generateClientId(): string {
    return `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * 获取认证头部
   */
  private getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('access_token')
    return token ? { 'Authorization': `Bearer ${token}` } : {}
  }

  /**
   * 获取ASR配置
   */
  async getConfig(): Promise<ASRServiceConfig> {
    if (this.config) {
      return this.config
    }

    try {
      const response = await fetch(`${this.apiBase}/api/v1/asr/config`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders()
        },
        body: JSON.stringify({
          language: 'zh-CN',
          sample_rate: 16000,
          format: 'pcm',
          continuous: true
        })
      })

      if (!response.ok) {
        throw new Error(`ASR配置获取失败: ${response.status}`)
      }

      this.config = await response.json()
      return this.config!
    } catch (error) {
      console.error('获取ASR配置失败:', error)
      throw error
    }
  }

  /**
   * 检查浏览器支持
   */
  private checkBrowserSupport(): boolean {
    return !!(navigator.mediaDevices && 
              navigator.mediaDevices.getUserMedia && 
              window.MediaRecorder &&
              window.WebSocket)
  }

  /**
   * 请求麦克风权限
   */
  async requestMicrophonePermission(): Promise<boolean> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true
        }
      })
      
      // 测试后立即关闭
      stream.getTracks().forEach(track => track.stop())
      return true
    } catch (error) {
      console.error('麦克风权限请求失败:', error)
      return false
    }
  }

  /**
   * 创建WebSocket连接
   */
  private async createWebSocketConnection(): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      // 正确构建WebSocket URL
      const wsProtocol = this.apiBase.startsWith('https') ? 'wss' : 'ws'
      const wsHost = this.apiBase.replace(/^https?:\/\//, '')
      const wsUrl = `${wsProtocol}://${wsHost}/api/v1/asr/realtime/${this.clientId}`
      
      console.log('尝试连接 WebSocket URL:', wsUrl)
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('ASR WebSocket连接已建立')
        resolve(ws)
      }

      ws.onerror = (error) => {
        console.error('ASR WebSocket连接错误:', error)
        reject(error)
      }

      ws.onclose = () => {
        console.log('ASR WebSocket连接已关闭')
      }

      // 10秒超时
      setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) {
          ws.close()
          reject(new Error('WebSocket连接超时'))
        }
      }, 10000)
    })
  }

  /**
   * 开始录音
   */
  async startRecording(): Promise<void> {
    if (!this.checkBrowserSupport()) {
      throw new Error('浏览器不支持录音功能')
    }

    if (this.isRecording) {
      throw new Error('已在录音中')
    }

    try {
      // 获取麦克风权限
      this.audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true
        }
      })

      // 创建MediaRecorder
      this.mediaRecorder = new MediaRecorder(this.audioStream, {
        mimeType: 'audio/webm;codecs=opus'
      })

      // 清空音频块
      this.audioChunks = []

      // 设置数据处理器
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data)
        }
      }

      // 开始录音
      this.mediaRecorder.start(100) // 每100ms收集一次数据
      this.isRecording = true

      console.log('开始录音')
    } catch (error) {
      console.error('开始录音失败:', error)
      throw error
    }
  }

  /**
   * 停止录音
   */
  async stopRecording(): Promise<Blob | null> {
    if (!this.isRecording || !this.mediaRecorder) {
      return null
    }

    return new Promise((resolve) => {
      this.mediaRecorder!.onstop = () => {
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' })
        this.cleanupRecording()
        resolve(audioBlob)
      }

      this.mediaRecorder!.stop()
      this.isRecording = false
    })
  }

  /**
   * 清理录音资源
   */
  private cleanupRecording(): void {
    if (this.audioStream) {
      this.audioStream.getTracks().forEach(track => track.stop())
      this.audioStream = null
    }

    if (this.mediaRecorder) {
      this.mediaRecorder = null
    }

    this.audioChunks = []
  }

  /**
   * 音频格式转换（WebM转PCM）
   */
  private async convertAudioToPCM(audioBlob: Blob): Promise<ArrayBuffer> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = async () => {
        try {
          const arrayBuffer = reader.result as ArrayBuffer
          const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
          const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
          
          // 转换为16kHz单声道PCM
          const pcmData = this.resampleAudio(audioBuffer, 16000)
          resolve(pcmData)
        } catch (error) {
          reject(error)
        }
      }
      reader.onerror = reject
      reader.readAsArrayBuffer(audioBlob)
    })
  }

  /**
   * 音频重采样
   */
  private resampleAudio(audioBuffer: AudioBuffer, targetSampleRate: number): ArrayBuffer {
    const originalSampleRate = audioBuffer.sampleRate
    const ratio = originalSampleRate / targetSampleRate
    const originalData = audioBuffer.getChannelData(0)
    const resampledLength = Math.round(originalData.length / ratio)
    const resampledData = new Int16Array(resampledLength)

    for (let i = 0; i < resampledLength; i++) {
      const originalIndex = Math.round(i * ratio)
      const sample = originalData[originalIndex] || 0
      resampledData[i] = Math.round(sample * 32767)
    }

    return resampledData.buffer
  }

  /**
   * 一次性语音识别
   */
  async recognizeAudio(audioBlob: Blob): Promise<RecognitionResult> {
    try {
      // 转换音频格式
      const pcmData = await this.convertAudioToPCM(audioBlob)
      const audioBase64 = this.arrayBufferToBase64(pcmData)

      const response = await fetch(`${this.apiBase}/api/v1/asr/interview-recognition`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders()
        },
        body: JSON.stringify({
          audio_data: audioBase64,
          format: 'pcm',
          sample_rate: 16000
        })
      })

      if (!response.ok) {
        throw new Error(`语音识别失败: ${response.status}`)
      }

      const result = await response.json()
      return result
    } catch (error) {
      console.error('语音识别失败:', error)
      return {
        success: false,
        text: '',
        is_final: true,
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  }

  /**
   * ArrayBuffer转Base64
   */
  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    let binary = ''
    const bytes = new Uint8Array(buffer)
    const len = bytes.byteLength
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i])
    }
    return btoa(binary)
  }

  /**
   * 录音并识别
   */
  async recordAndRecognize(): Promise<RecognitionResult> {
    try {
      await this.startRecording()
      
      // 等待用户操作（这里需要外部控制停止）
      return new Promise((resolve) => {
        // 这个方法需要与UI组件配合使用
        (window as any).asrStopRecording = async () => {
          const audioBlob = await this.stopRecording()
          if (audioBlob) {
            const result = await this.recognizeAudio(audioBlob)
            resolve(result)
          } else {
            resolve({
              success: false,
              text: '',
              is_final: true,
              error: '录音失败'
            })
          }
        }
      })
    } catch (error) {
      console.error('录音识别失败:', error)
      return {
        success: false,
        text: '',
        is_final: true,
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  }

  /**
   * 获取录音状态
   */
  getRecordingStatus(): {
    isRecording: boolean
    isSupported: boolean
    hasPermission: boolean
  } {
    return {
      isRecording: this.isRecording,
      isSupported: this.checkBrowserSupport(),
      hasPermission: this.audioStream !== null
    }
  }

  /**
   * 销毁服务
   */
  destroy(): void {
    this.cleanupRecording()
    
    if (this.websocket) {
      this.websocket.close()
      this.websocket = null
    }
  }
}

// 导出单例实例
export const asrService = new ASRService()
export default asrService