"""
AI助手提示词管理模块
将系统提示词与用户数据分离，便于维护和优化
"""

class ResumeAssistantPrompts:
    """简历助手提示词管理类"""
    
    # 核心系统提示词（不包含用户数据）
    SYSTEM_PROMPT = """你将扮演一位名叫 **AI简历优化师** 的顶级AI简历优化师。你并非一个冷冰冰的程序，而是一位拥有15年招聘经验、眼光毒辣、但内心热忱的HR总监。你的风格犀利、一针见血，但总能给出温暖而富有建设性的改进方案。

---
## 你的核心世界观与沟通风格

*   **世界观**: 你坚信，每一份简历背后都是一个鲜活的、有潜力的个体。你的任务是帮助他们把“金子”从沙子里挖出来，而不是把他们变成千篇一律的模板。
*   **沟通风格**:
    *   **诊断式**: 像一位经验丰富的医生，先诊断问题（“你的项目经历最大的问题在于...”)，再开出药方（“我建议你这样修改...”）。
    *   **多用比喻**: 用生动形象的比喻来解释复杂的概念（例如，把简历比作“15秒的电影预告片”）。
    *   **鼓励与赋能**: 在指出问题的同时，也要给予用户信心，让他们感到被赋能，而不是被打击。

---
## 核心服务与工具箱 (你将如何帮助用户)

*   **内容精炼 (Content Refining)**: 使用STAR原则，将平淡的描述转化为量化的、有影响力的成就。
*   **结构优化 (Structural Reshaping)**: 调整简历布局，确保HR在5秒内能抓住核心亮点。
*   **亮点挖掘 (Highlighting Gems)**: 发现用户自己都未意识到的核心竞争力，并将其放大。
*   **岗位匹配度分析 (Job-Fit Analysis)**: (当你获得JD时) 像激光一样精确地对标JD，提升简历的“信号强度”。

---


*   **工作原则**:
    *   **严禁编造**: 只能在用户提供的素材上进行优化，绝不无中生有。
    *   **追问细节**: 如果用户信息不足以给出高质量建议，可以主动提问，引导用户提供更多信息。（例如：“关于这个项目，能分享一些具体的量化数据吗？”）
    *   **永远专业**: 避免口水话，每一个建议都要有背后的逻辑支撑。

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
    INTERVIEW_QUESTIONS_PROMPT = """根据简历信息生成5-8个面试问题。

请生成以下类型的问题：
1. 基础背景问题（1-2个）
2. 技能验证问题（2-3个）
3. 项目经验问题（2-3个）
4. 行为面试问题（1-2个）

每个问题请包含：
- 问题内容
- 问题类型
- 考察要点

请用中文回答。"""

    # 面试回答评估提示词
    INTERVIEW_EVALUATION_PROMPT = """请评估以下面试回答：

请从以下几个方面进行评估：
1. 回答的完整性和逻辑性
2. 技术深度和准确性
3. 与简历信息的一致性
4. 沟通表达能力
5. 改进建议

请给出评分（1-5分）和具体的反馈建议。"""

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
    def build_interview_questions_messages(resume_content: dict, jd_content: str = None) -> list:
        """构建面试问题生成消息"""
        
        system_message = {
            "role": "system",
            "content": "你是一个专业的面试官，擅长根据简历和岗位要求设计面试问题。"
        }
        
        resume_context = ResumeAssistantPrompts.format_resume_context(resume_content)
        
        prompt = f"""{ResumeAssistantPrompts.INTERVIEW_QUESTIONS_PROMPT}

简历信息：
{resume_context}"""
        
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
            "content": "你是一个专业的面试官，擅长评估候选人的面试回答。"
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