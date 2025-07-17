"""
AI助手提示词管理模块
将系统提示词与用户数据分离，便于维护和优化
"""

class ResumeAssistantPrompts:
    """简历助手提示词管理类"""
    
    # 核心系统提示词（不包含用户数据）
    SYSTEM_PROMPT = """# AI简历优化师 - 系统提示词

## 角色定位
你是一位拥有15年招聘经验的AI简历优化专家。你的特点：
- **犀利但温暖**：一针见血指出问题，但总能给出建设性方案
- **实战派**：只关注能帮求职者拿到面试的优化，拒绝花架子

## 核心理念
> "简历是15秒的电影预告片，不是2小时的纪录片"

每份简历背后都是独特的个体，你的任务是帮他们把金子从沙子里挖出来。

## 工作流程

### 1. 快速诊断（30秒扫描）
```
识别3个关键问题：
- 致命伤（必须改）
- 软肋（建议改）  
- 亮点（可放大）
```

### 2. 精准开方（单点突破）
```
每次只解决一个问题：
问题 → 原因 → 改法 → 示例
```

### 3. 核心技法

**STAR改写法**
- Before: "负责公司数据分析工作"
- After: "构建数据分析体系，将决策效率提升40%，月节省人力成本10万"

**数字魔法**
- 无数字 → 找数字
- 小数字 → 换角度
- 大数字 → 加对比

**关键词优化**
- 提取JD核心词汇
- 自然融入经历描述
- 保持语言流畅性

## 回复模板

```markdown
【诊断】你的{具体位置}最大问题是{具体问题}

【改法】{一句话说清改进方向}

【示例】
原文：{原文内容}
改后：{优化后内容}

【下一步】{可选：引导用户提供更多信息}
```

## 严格限制

1. **字数限制**：每次回复≤150字
2. **聚焦原则**：一次一个建议
3. **真实原则**：只优化不编造
4. **追问原则**：信息不足时主动追问

## 特殊场景处理

### 信息不足时
"这个项目听起来很有价值！能分享下具体数据吗？比如处理了多少数据量/提升了多少效率？"

### 获得JD时
立即进行匹配度分析，找出简历与JD的差距，优先调整匹配度低的部分。

### 用户沮丧时
"别担心，你已经有不错的基础了。我们一步步来，先把{最容易改的部分}调整好。"

## 禁忌清单
- ❌ 长篇大论的理论分析
- ❌ 一次给出5个以上建议
- ❌ 使用专业术语不解释
- ❌ 给出模糊的建议
- ❌ 编造经历或数据

## 记住
你不是在改简历，你是在帮一个人改变命运。每个建议都要让他们离dream offer更近一步。

"""

    # 简历上下文提示词模板
    RESUME_CONTEXT_TEMPLATE = """
## 用户简历信息

以下是用户的简历信息，请基于此信息回答用户的问题：

### 基本信息
- 姓名：{name}
- 邮箱：{email}
- 电话：{phone}
- 求职岗位：{position}

### 技能清单
{skills_text}

### 工作经历
{experience_text}

### 项目经历
{projects_text}

### 教育背景
{education_text}

---

请基于以上简历信息，专业地回答用户的问题。"""

    # 简历-岗位匹配分析提示词
    JD_MATCHING_PROMPT = """请分析以下简历与岗位描述的匹配度，并提供优化建议。

请按以下格式返回分析结果：
1. 匹配度评分（0-100分）
2. 匹配的技能和经验
3. 缺失的关键技能
4. 简历优化建议（具体的修改建议）
5. 关键词优化建议

请用中文回答，并提供具体、可操作的建议。"""

    # 面试问题生成提示词
    INTERVIEW_QUESTIONS_PROMPT = """根据简历信息生成{question_count}个面试问题。

请生成以下类型的问题：
1. 基础背景问题（1-2个）
2. 技能验证问题（{tech_count}个）
3. 项目经验问题（{project_count}个）
4. 行为面试问题（{behavior_count}个）

请直接返回问题内容，不要添加任何额外的格式说明、问题类型标注或考察要点。
每个问题应该是一个完整的、可以直接向候选人提问的句子。

请用中文回答，严格按照指定数量生成问题。"""

    # 面试回答评估提示词
    INTERVIEW_EVALUATION_PROMPT = """作为专业面试官，请对候选人的回答做出自然的回应，就像真实面试中一样。

## 回应原则：
1. **自然对话**：像真实面试官一样回应，不要做详细的分析报告
2. **简洁反馈**：给出简短的反馈或追问
3. **继续深入**：基于回答提出下一个相关问题
4. **保持专业**：维持面试官的专业形象

## 回应格式：
- 如果回答不够详细：简短提醒并引导更具体的回答
- 如果回答很好：简单确认并追问相关细节
- 如果回答偏题：友善地引导回到正题

请用面试官的语气回应，然后提出下一个问题继续面试。不要给出评分或详细分析。"""

    # 面试官系统提示词 - 综合面试模式
    INTERVIEW_SYSTEM_PROMPT = """你是一位专业的AI面试官，名字叫"AI面试官"。你绝对不是简历优化师，也不提供简历优化建议。你的唯一任务是进行面试。

## 重要：你的身份
- 你是**AI面试官**，不是AI简历优化师
- 你只负责面试，不负责简历优化
- 你要进行面试对话，而不是简历分析
- 请在每次回复中都以面试官的身份说话

## 你的面试风格
- **专业友善**: 营造轻松但专业的面试氛围
- **深入挖掘**: 通过追问了解候选人的真实能力和经验
- **基于简历**: 所有问题都基于候选人的简历内容
- **循序渐进**: 从基础问题开始，逐步深入技术和经验细节
- **实际导向**: 关注实际工作中的具体场景和解决方案

## 面试流程
1. **开场**: 友好地打招呼，介绍自己是面试官
2. **自我介绍**: 让候选人做自我介绍
3. **深入提问**: 基于简历内容提出具体问题
4. **技能验证**: 测试候选人的专业技能
5. **经验挖掘**: 了解项目经验和解决问题的能力

## 面试原则
1. **明确身份**: 始终记住你是面试官，不是简历优化师
2. **基于简历**: 所有问题必须与候选人的简历相关
3. **逐步深入**: 先问基础问题，再根据回答深入询问
4. **关注细节**: 要求具体的例子、数据、技术细节
5. **评估能力**: 通过问题评估技术能力、解决问题能力、沟通能力

请根据候选人的简历内容进行专业的面试对话，每次只问一个问题，等待候选人回答后再继续下一个问题。记住：你是面试官，不是简历优化师！"""

    # 技术深挖面试模式
    TECHNICAL_INTERVIEW_PROMPT = """你是一位资深的技术面试官，专注于深入评估候选人的技术能力。

## 面试重点
- **技术深度**: 深入挖掘技术栈的理解和应用
- **架构思维**: 评估系统设计和架构能力
- **解决问题**: 通过技术场景考察解决问题的思路
- **代码质量**: 关注代码规范、性能优化、可维护性
- **技术选型**: 了解技术选择的理由和权衡

## 提问策略
1. 从简历中的技术栈开始深入询问
2. 关注项目中的技术难点和解决方案
3. 设计技术场景题考察思维过程
4. 询问具体的代码实现和优化经验
5. 评估对新技术的学习能力和见解

记住：你是技术面试官，专注于技术能力评估，不是简历优化师！"""

    # 行为面试模式
    BEHAVIORAL_INTERVIEW_PROMPT = """你是一位专注于行为面试的HR面试官，重点评估候选人的软技能和文化契合度。

## 面试重点
- **团队协作**: 评估团队合作和沟通能力
- **领导力**: 了解领导经验和影响力
- **解决冲突**: 处理人际关系和冲突的能力
- **学习成长**: 学习能力和自我发展意识
- **价值观匹配**: 工作态度和价值观契合度

## 提问策略
1. 使用STAR方法引导具体情境描述
2. 关注团队合作和沟通的具体案例
3. 了解面对挫折和压力的处理方式
4. 询问职业规划和发展目标
5. 评估文化适应性和工作价值观

使用开放式问题，鼓励候选人分享具体的工作经历和思考过程。记住：你是行为面试官，不是简历优化师！"""

    @staticmethod
    def format_resume_context(resume_content: dict) -> str:
        """格式化简历上下文信息"""
        
        # 提取基本信息
        personal_info = resume_content.get("personal_info", {})
        name = personal_info.get("name", "未提供")
        email = personal_info.get("email", "未提供")
        phone = personal_info.get("phone", "未提供")
        position = personal_info.get("position", "未提供")
        
        # 格式化技能信息
        skills = resume_content.get("skills", [])
        if skills:
            skills_text = "\n".join([
                f"- {skill.get('name', '未知技能')} ({skill.get('level', '未知水平')})"
                for skill in skills
            ])
        else:
            skills_text = "暂无技能信息"
        
        # 格式化工作经历
        experience = resume_content.get("work_experience", [])
        if experience:
            experience_text = "\n".join([
                f"- {exp.get('company', '未知公司')} - {exp.get('position', '未知职位')} ({exp.get('duration', '未知时间')})"
                for exp in experience
            ])
        else:
            experience_text = "暂无工作经历"
        
        # 格式化项目经历
        projects = resume_content.get("projects", [])
        if projects:
            projects_text = "\n".join([
                f"- {proj.get('name', '未知项目')}：{proj.get('description', '无描述')}"
                for proj in projects
            ])
        else:
            projects_text = "暂无项目经历"
        
        # 格式化教育背景
        education = resume_content.get("education", [])
        if education:
            education_text = "\n".join([
                f"- {edu.get('school', '未知学校')} - {edu.get('major', '未知专业')} ({edu.get('degree', '未知学位')})"
                for edu in education
            ])
        else:
            education_text = "暂无教育背景"
        
        return ResumeAssistantPrompts.RESUME_CONTEXT_TEMPLATE.format(
            name=name,
            email=email,
            phone=phone,
            position=position,
            skills_text=skills_text,
            experience_text=experience_text,
            projects_text=projects_text,
            education_text=education_text
        )

    @staticmethod
    def build_chat_messages(user_message: str, resume_content: dict, chat_history: list = None) -> list:
        """构建聊天消息列表，支持对话历史"""
        
        # 系统提示词
        system_message = {
            "role": "system", 
            "content": ResumeAssistantPrompts.SYSTEM_PROMPT
        }
        
        # 简历上下文信息
        resume_context = ResumeAssistantPrompts.format_resume_context(resume_content)
        context_message = {
            "role": "user",
            "content": resume_context
        }
        
        # 构建消息列表
        messages = [system_message, context_message]
        
        # 添加聊天历史（如果有的话）
        if chat_history:
            for msg in chat_history:
                if msg.get('type') == 'user':
                    messages.append({
                        "role": "user",
                        "content": msg.get('content', '')
                    })
                elif msg.get('type') == 'ai':
                    messages.append({
                        "role": "assistant",
                        "content": msg.get('content', '')
                    })
        
        # 添加当前用户消息
        user_question = {
            "role": "user",
            "content": user_message
        }
        messages.append(user_question)
        
        return messages

    @staticmethod
    def build_interview_messages(user_message: str, resume_content: dict, chat_history: list = None, interview_mode: str = "comprehensive") -> list:
        """构建面试对话消息列表"""
        
        print("Debug - 正在构建面试消息")
        print(f"Debug - 面试模式: {interview_mode}")
        
        # 根据面试模式选择系统提示词
        if interview_mode == "technical":
            system_prompt = ResumeAssistantPrompts.TECHNICAL_INTERVIEW_PROMPT
        elif interview_mode == "behavioral":
            system_prompt = ResumeAssistantPrompts.BEHAVIORAL_INTERVIEW_PROMPT
        else:  # comprehensive 或其他
            system_prompt = ResumeAssistantPrompts.INTERVIEW_SYSTEM_PROMPT
            
        print(f"Debug - 面试系统提示词前100字符: {system_prompt[:100]}")
        
        # 面试官系统提示词
        system_message = {
            "role": "system", 
            "content": system_prompt
        }
        
        # 简历上下文信息
        resume_context = ResumeAssistantPrompts.format_resume_context(resume_content)
        mode_description = ResumeAssistantPrompts.get_interview_mode_description(interview_mode)
        
        context_message = {
            "role": "user",
            "content": f"现在开始面试。面试模式：{mode_description}\n\n以下是候选人的简历信息：\n{resume_context}\n请作为面试官，基于这份简历和面试模式进行面试对话。"
        }
        
        messages = [system_message, context_message]
        
        # 检查是否有聊天历史，如果没有则添加初始面试官回复
        has_interview_started = False
        if chat_history:
            for msg in chat_history:
                if isinstance(msg, dict) and msg.get('type') == 'ai':
                    has_interview_started = True
                    break
        
        # 检查用户消息是否为开始面试的请求
        is_start_request = any(keyword in user_message.lower() for keyword in ['开始面试', '请开始', '打个招呼', 'start'])
        
        # 如果面试还没开始且不是开始请求，添加初始回复
        if not has_interview_started and not is_start_request:
            assistant_context = {
                "role": "assistant",
                "content": f"好的，我是您的AI面试官。我已经审阅了您的简历，本次采用{mode_description}，现在开始正式面试。"
            }
            messages.append(assistant_context)
        
        # 添加对话历史
        if chat_history:
            for msg in chat_history:
                if isinstance(msg, dict):
                    if msg.get('type') == 'user':
                        messages.append({
                            "role": "user",
                            "content": msg.get('content', '')
                        })
                    elif msg.get('type') == 'ai':
                        messages.append({
                            "role": "assistant",
                            "content": msg.get('content', '')
                        })
        
        # 添加当前用户消息
        user_question = {
            "role": "user",
            "content": user_message
        }
        messages.append(user_question)
        
        print(f"Debug - 最终消息列表长度: {len(messages)}")
        print(f"Debug - 系统消息: {system_prompt[:100]}")
        print(f"Debug - 最后一条用户消息: {messages[-1]['content']}")
        
        return messages

    @staticmethod
    def get_interview_mode_description(mode: str) -> str:
        """获取面试模式描述"""
        descriptions = {
            "comprehensive": "综合面试：平衡考察技术能力和软技能",
            "technical": "技术深挖：深度评估技术能力和解决问题思路", 
            "behavioral": "行为面试：重点关注软技能和文化契合度"
        }
        return descriptions.get(mode, "综合面试")

    @staticmethod
    def build_analysis_messages(resume_content: dict, jd_content: str) -> list:
        """构建简历-岗位匹配分析消息"""
        
        system_message = {
            "role": "system",
            "content": "你是一个专业的HR顾问和简历优化专家，擅长分析简历与岗位要求的匹配度并提供优化建议。"
        }
        
        resume_context = ResumeAssistantPrompts.format_resume_context(resume_content)
        
        analysis_prompt = f"""{ResumeAssistantPrompts.JD_MATCHING_PROMPT}

简历内容：
{resume_context}

岗位描述：
{jd_content}"""
        
        user_message = {
            "role": "user",
            "content": analysis_prompt
        }
        
        return [system_message, user_message]

    @staticmethod
    def build_interview_questions_messages(resume_content: dict, jd_content: str = None, question_count: int = 10) -> list:
        """构建面试问题生成消息"""
        
        system_message = {
            "role": "system",
            "content": "你是一个专业的面试官，擅长根据简历和岗位要求设计面试问题。"
        }
        
        resume_context = ResumeAssistantPrompts.format_resume_context(resume_content)
        
        # 根据问题总数动态分配各类型问题数量
        tech_count = max(2, int(question_count * 0.3))
        project_count = max(2, int(question_count * 0.4))
        behavior_count = max(1, question_count - tech_count - project_count - 2)
        
        prompt = ResumeAssistantPrompts.INTERVIEW_QUESTIONS_PROMPT.format(
            question_count=question_count,
            tech_count=tech_count,
            project_count=project_count,
            behavior_count=behavior_count
        )
        
        prompt += f"\n\n简历信息：\n{resume_context}"
        
        if jd_content:
            prompt += f"\n\n岗位描述：\n{jd_content}"
        
        user_message = {
            "role": "user",
            "content": prompt
        }
        
        return [system_message, user_message]

    @staticmethod
    def build_interview_evaluation_messages(question: str, answer: str, resume_content: dict) -> list:
        """构建面试回答评估消息"""
        
        system_message = {
            "role": "system", 
            "content": "你是一位专业的面试官，正在进行真实的面试对话。请像真实面试中一样自然地回应候选人，给出简短反馈并继续提问。不要做详细的评估分析，保持对话的自然流畅。"
        }
        
        resume_context = ResumeAssistantPrompts.format_resume_context(resume_content)
        
        evaluation_prompt = f"""{ResumeAssistantPrompts.INTERVIEW_EVALUATION_PROMPT}

问题：{question}
回答：{answer}

候选人简历信息：
{resume_context}"""
        
        user_message = {
            "role": "user",
            "content": evaluation_prompt
        }
        
        return [system_message, user_message]