# MiniMax TTS 语音功能集成

## 功能概述

本项目已集成 MiniMax TTS API，为面试系统提供语音功能，包括：

- 📢 面试问题文本转语音
- 🎭 多种面试官音色选择
- 🎵 实时语音播放控制
- 🔄 语音缓存优化

## 技术架构

### 后端实现

1. **服务层** (`backend/app/services/minimax_tts_service.py`)
   - MiniMax TTS API 封装
   - 语音生成、语音克隆、音色管理
   - 面试官音色配置

2. **API 端点** (`backend/app/api/api_v1/endpoints/tts.py`)
   - `/api/v1/tts/text-to-speech` - 通用文本转语音
   - `/api/v1/tts/interview-question-speech` - 面试问题专用语音
   - `/api/v1/tts/interviewer-voices` - 获取面试官音色配置
   - `/api/v1/tts/voices` - 获取可用音色列表
   - `/api/v1/tts/clone-voice` - 语音克隆（上传音频文件）

3. **配置** (`backend/app/core/config.py`)
   - MiniMax API 密钥配置
   - API 基础URL配置

### 前端实现

1. **TTS 服务** (`frontend/src/lib/tts.ts`)
   - 语音API调用封装
   - 音频播放管理
   - 语音缓存机制

2. **语音控制组件** (`frontend/src/components/interview/VoiceControls.tsx`)
   - 播放/停止按钮
   - 面试官音色选择
   - 语音设置界面

3. **面试页面集成** (`frontend/src/app/resume/[id]/interview/page.tsx`)
   - 在AI消息中显示语音控制
   - 流式消息语音支持
   - 语音错误处理

## 使用方法

### 环境配置

1. 在 `.env` 文件中配置 MiniMax API 密钥：
   ```bash
   MINIMAX_API_KEY=your_minimax_api_key_here
   MINIMAX_API_BASE=https://api.minimaxi.chat
   ```

2. 启动后端服务：
   ```bash
   cd backend
   pip install -r requirements.txt
   python -m uvicorn app.main:app --reload
   ```

3. 启动前端服务：
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### 功能测试

1. **后端测试**：
   ```bash
   cd backend
   python test_tts.py
   ```

2. **前端测试**：
   - 打开 `test_tts_frontend.html` 在浏览器中测试
   - 或直接在面试页面中测试语音功能

### 面试官音色配置

系统预设了三种面试官音色：

- **professional**: 专业女性面试官 (female-tianmei-jingpin, neutral)
- **friendly**: 友好男性面试官 (male-qinse-jingpin, happy)
- **strict**: 严格女性面试官 (female-zhuanye-jingpin, neutral)

## API 文档

### 文本转语音

```http
POST /api/v1/tts/text-to-speech
Content-Type: application/json
Authorization: Bearer {token}

{
  "text": "您好，这是一个测试。",
  "voice_id": "female-tianmei-jingpin",
  "emotion": "neutral",
  "model": "speech-02-turbo",
  "format": "mp3",
  "sample_rate": 32000
}
```

### 面试问题语音

```http
POST /api/v1/tts/interview-question-speech
Content-Type: application/json
Authorization: Bearer {token}

{
  "text": "请简单介绍一下您自己。",
  "voice_id": "female-tianmei-jingpin",
  "emotion": "neutral"
}
```

### 获取面试官音色

```http
GET /api/v1/tts/interviewer-voices
Authorization: Bearer {token}
```

## 支持的音频格式

- **输出格式**: mp3, wav, flac, pcm
- **采样率**: 8000, 16000, 22050, 24000, 32000, 44100 Hz
- **文件大小**: 最大 20MB（用于语音克隆）

## 错误处理

系统实现了完善的错误处理机制：

- API 密钥验证
- 网络请求超时处理
- 音频播放错误处理
- 用户友好的错误提示

## 性能优化

- 语音缓存：避免重复生成相同文本的语音
- 流式播放：支持边生成边播放
- 异步处理：不阻塞用户界面

## 开发说明

### 添加新的音色

1. 在 `MiniMaxTTSService.get_interviewer_voice_config()` 中添加新配置
2. 在前端 `VoiceControls` 组件中更新音色选择选项
3. 测试新音色的播放效果

### 扩展语音功能

1. 语音识别：可集成语音转文本功能
2. 语音合成优化：支持 SSML 标记
3. 情感分析：根据文本内容自动选择适当的情感

## 注意事项

- 确保 MiniMax API 密钥的安全性
- 监控 API 使用量和费用
- 定期更新音色配置以获得最佳效果
- 测试不同设备和浏览器的语音播放兼容性

## 故障排除

1. **语音无法播放**：
   - 检查 API 密钥是否正确
   - 确认网络连接正常
   - 查看浏览器控制台错误信息

2. **语音质量问题**：
   - 尝试不同的音色和情感设置
   - 调整采样率和格式
   - 检查输入文本的格式

3. **性能问题**：
   - 启用语音缓存
   - 减少同时播放的音频数量
   - 优化网络请求频率