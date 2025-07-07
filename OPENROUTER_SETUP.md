# OpenRouter Gemini-2.5-flash 集成指南

## 概述
项目已成功集成 OpenRouter API，使用 Google Gemini-2.5-flash 模型进行简历分析和优化。

## 配置步骤

### 1. 获取 OpenRouter API Key
1. 访问 [OpenRouter 官网](https://openrouter.ai)
2. 注册账户并登录
3. 在设置页面生成 API Key
4. 复制 API Key 备用

### 2. 配置环境变量
在后端目录创建 `.env` 文件：

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件，设置以下变量：

```bash
# OpenRouter API配置（主要）
OPENROUTER_API_KEY=your-openrouter-api-key-here
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemini-2.5-flash
```

### 3. 启动服务
```bash
# 启动后端
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端（新终端）
cd frontend
npm run dev
```

### 4. 验证配置
访问 `http://localhost:3000`，在简历编辑页面查看 AI 助手状态：
- ✅ **OpenRouter已连接** - 配置成功
- ⚠️ **模拟模式** - 需要检查配置

## 可用功能

### 1. 简历优化聊天
- 实时简历内容分析
- 个性化优化建议
- 行业关键词推荐

### 2. 简历-JD匹配分析
- 匹配度评分
- 技能差距分析
- 优化建议

### 3. 面试准备
- 智能面试问题生成
- 回答质量评估
- 后续问题推荐

### 4. 智能简历解析
- 自动结构化处理
- 多格式支持（PDF、Word）
- 高准确度提取

## 模型特性

### Gemini-2.5-flash 优势
- 🚀 **高性能**: 响应速度快，适合实时交互
- 🧠 **强推理**: 优秀的逻辑分析和推理能力
- 📝 **中文优化**: 对中文内容理解和生成效果好
- 💰 **成本友好**: 通过 OpenRouter 获得更优惠的定价

### API 限制
- 免费额度：具体限制请查看 OpenRouter 账户
- 速率限制：避免频繁调用
- 内容长度：单次请求建议控制在合理范围

## 故障排除

### 1. API Key 错误
```
状态：模拟模式
错误：API key not found
```
**解决方案**: 检查 `.env` 文件中的 `OPENROUTER_API_KEY` 配置

### 2. 网络连接问题
```
错误：无法连接到OpenRouter API服务器
```
**解决方案**: 检查网络连接，确认 OpenRouter 服务可访问

### 3. 模型不可用
```
错误：模型 google/gemini-2.5-flash 不可用
```
**解决方案**: 
- 检查 OpenRouter 账户权限
- 尝试其他可用的 Gemini 模型
- 联系 OpenRouter 支持

### 4. 速率限制
```
错误：Rate limit exceeded
```
**解决方案**: 
- 等待限制重置
- 升级 OpenRouter 账户
- 优化请求频率

## 备用方案
项目支持多种 AI 服务，按优先级自动切换：
1. **OpenRouter Gemini-2.5-flash** (主要)
2. **Google Gemini 原生 API** (备用)
3. **DeepSeek API** (备用)
4. **模拟响应** (兜底)

## 监控和日志
- 查看后端日志：`tail -f backend/backend.log`
- API 状态检查：`GET /api/v1/ai/status`
- 服务健康检查：`GET /api/v1/health`

## 支持
如遇问题，请：
1. 检查配置是否正确
2. 查看错误日志
3. 访问 OpenRouter 文档
4. 联系技术支持