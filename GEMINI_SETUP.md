# Google Gemini API 集成说明

## 概述

Chat Resume 现已升级使用 Google Gemini API 作为主要的AI引擎，提供更智能的简历优化建议。系统支持智能回退机制：Gemini → DeepSeek → 模拟模式。

## 配置步骤

### 1. 获取 Google Gemini API Key

1. 访问 [Google AI Studio](https://aistudio.google.com/app/apikey)
2. 使用Google账号登录
3. 点击 "Create API Key"
4. 选择现有项目或创建新项目
5. 复制生成的API Key

### 2. 配置环境变量

在 `frontend/.env.local` 文件中设置您的 API Key：

```bash
# Google Gemini API 配置 (主要使用)
NEXT_PUBLIC_GEMINI_API_URL=https://generativelanguage.googleapis.com
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-pro

# DeepSeek API 配置 (备用)
NEXT_PUBLIC_DEEPSEEK_API_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

**注意：** 请将 `your_actual_gemini_api_key_here` 替换为您实际的 Gemini API Key。

### 3. 重启开发服务器

配置完成后，重启 Next.js 开发服务器：

```bash
cd frontend
npm run dev
```

## 功能特性

### ✨ Gemini 优势

- **强大的多语言能力**：对中文的理解和生成能力优秀
- **上下文理解**：更好的简历内容分析和建议生成
- **安全性**：内置安全过滤机制
- **性能**：快速响应和高并发支持

### 🔄 智能回退机制

系统会按以下优先级选择AI服务：

1. **Gemini API** (主要) - 如果配置且可用
2. **DeepSeek API** (备用) - Gemini不可用时
3. **模拟模式** (最后) - 所有API都不可用时

### 🎯 专业简历优化能力

AI助手专门针对简历优化场景训练，可以提供：

#### **核心优化服务**
1. **内容优化** - 改进表达方式，使用行业术语和关键词
2. **结构调整** - 优化信息层次，提高可读性
3. **亮点突出** - 识别并强化核心竞争力
4. **匹配度提升** - 针对目标职位定制内容
5. **专业建议** - 基于行业标准提供改进方案

#### **高级功能**
- **针对性职位分析**：基于JD提供定制化建议
- **技能关键词优化**：提升ATS系统通过率
- **量化成果建议**：帮助添加具体数据和指标
- **行业最佳实践**：遵循中国职场文化和习惯

## 状态显示

在 AI 助手界面中，您会看到不同的状态标签：

- 🔵 **"Gemini已连接"** - Gemini API 正常工作
- 🟢 **"DeepSeek备用"** - Gemini未配置，使用DeepSeek
- 🟡 **"模拟模式"** - 所有API都未配置，使用模拟响应

## 使用示例

### 典型对话场景

**场景1：整体优化建议**
```
用户：请帮我分析一下简历的整体结构，有什么需要改进的地方？

AI助手：基于您的简历分析，我发现以下几个优化点：

🎯 **结构优化建议**：
1. **技能部分** - 建议按照重要性重新排序，将最核心的技术技能放在前面
2. **项目经验** - 可以添加具体的技术指标和业务成果
3. **工作描述** - 使用STAR法则重新组织内容

💡 **具体改进方案**：
- 在项目描述中添加"实现了XX%的性能提升"
- 技能分类：编程语言 → 框架/工具 → 软技能
- 每段工作经验控制在3-4个要点内...
```

**场景2：针对特定职位优化**
```
用户：我想申请高级前端工程师，简历应该如何调整？

AI助手：针对高级前端工程师职位，建议重点优化以下方面：

🚀 **技术栈匹配**：
1. 突出React/Vue等主流框架经验
2. 强调性能优化和工程化能力
3. 添加团队协作和技术分享经验

📊 **量化成果示例**：
- "优化组件渲染，页面加载速度提升40%"
- "搭建自动化测试，代码覆盖率达到85%"
- "主导技术选型，团队开发效率提升30%"...
```

## API参数配置

### Gemini 配置参数

```typescript
generationConfig: {
  temperature: 0.7,        // 创造性平衡
  topK: 40,               // 候选词数量
  topP: 0.8,              // 核心采样概率
  maxOutputTokens: 1000   // 最大输出长度
}
```

### 安全设置

```typescript
safetySettings: [
  {
    category: 'HARM_CATEGORY_HARASSMENT',
    threshold: 'BLOCK_MEDIUM_AND_ABOVE'
  },
  // ... 其他安全类别
]
```

## 常见问题

### Q: Gemini API 有使用限制吗？

A: 是的，Gemini API 有以下限制：
- 免费层：每分钟15个请求
- 付费层：根据套餐不同有相应限制
- 建议查看最新的 [Google AI 定价页面](https://ai.google.dev/pricing)

### Q: 如何提高响应质量？

A: 
1. **详细描述**：提供具体的问题和需求
2. **上下文**：确保简历信息完整
3. **分步骤**：大问题拆分成小问题
4. **反馈迭代**：根据回复进一步提问

### Q: API 调用失败怎么办？

A: 系统有智能回退机制：
1. 首先尝试 Gemini API
2. 失败后自动切换到 DeepSeek
3. 最后回退到模拟模式
4. 界面会显示相应的错误提示

### Q: 数据隐私安全吗？

A: 
- ✅ API Key 存储在服务器环境变量中
- ✅ 简历数据仅在会话期间使用
- ✅ 不会持久化存储个人信息
- ✅ 遵循 Google 的数据使用政策

## 性能优化建议

### 1. API 调用优化
- 避免频繁请求
- 合理设置超时时间
- 使用适当的 temperature 值

### 2. 成本控制
- 监控 API 使用量
- 优化 prompt 长度
- 考虑使用缓存机制

## 技术支持

如遇到问题，请检查：

1. ✅ Gemini API Key 是否正确设置
2. ✅ 网络连接是否正常
3. ✅ API 配额是否充足
4. ✅ 开发服务器是否已重启

## 更新日志

- **v2.0.0** - 升级为 Gemini API 主引擎
- 优化prompt适配Gemini特性
- 实现智能回退机制 (Gemini → DeepSeek → Mock)
- 增强中文简历优化能力
- 添加针对性职位匹配功能
- 改进安全性和错误处理

## 从 DeepSeek 迁移

如果您之前使用的是 DeepSeek，迁移步骤：

1. **保留原配置** - DeepSeek 配置会作为备用保留
2. **添加 Gemini Key** - 在 `.env.local` 中添加 Gemini 配置
3. **重启服务** - 系统会自动优先使用 Gemini
4. **测试功能** - 验证 AI 助手工作正常

迁移完成后，您将获得更好的AI体验！