import httpx
from typing import Dict, Any, List
from app.core.config import settings
from app.core.prompts import ResumeAssistantPrompts

class OpenRouterService:
    """OpenRouter API服务类，用于访问Gemini-2.5-flash模型进行简历分析和优化"""
    
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.api_base = settings.OPENROUTER_API_BASE
        self.model = settings.OPENROUTER_MODEL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://chat-resume.com",  # 可选，用于OpenRouter统计
            "X-Title": "Chat Resume AI Assistant"  # 可选，用于OpenRouter统计
        }
    
    async def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict[str, Any]:
        """调用 OpenRouter Chat API（OpenAI兼容格式）"""
        url = f"{self.api_base}/chat/completions"
        
        # 转换消息格式为OpenAI格式
        openai_messages = []
        
        for message in messages:
            if message["role"] in ["system", "user", "assistant"]:
                openai_messages.append({
                    "role": message["role"],
                    "content": message["content"]
                })
        
        payload = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": 2000,
            "stream": False
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
    
    async def chat_completion_stream(self, messages: List[Dict[str, str]], temperature: float = 0.7):
        """调用 OpenRouter Chat API（流式传输）"""
        url = f"{self.api_base}/chat/completions"
        
        # 转换消息格式为OpenAI格式
        openai_messages = []
        
        for message in messages:
            if message["role"] in ["system", "user", "assistant"]:
                openai_messages.append({
                    "role": message["role"],
                    "content": message["content"]
                })
        
        payload = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": 2000,
            "stream": True
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream('POST', url, json=payload, headers=self.headers) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith('data: '):
                        data_str = line[6:]  # 移除 'data: ' 前缀
                        
                        if data_str.strip() == '[DONE]':
                            break
                            
                        try:
                            import json
                            data = json.loads(data_str)
                            
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    content = delta['content']
                                    if content:
                                        yield content
                        except json.JSONDecodeError:
                            continue
    
    async def analyze_resume_jd_match(self, resume_content: Dict[str, Any], jd_content: str) -> Dict[str, Any]:
        """分析简历与JD的匹配度"""
        
        # 使用新的提示词管理系统
        messages = ResumeAssistantPrompts.build_analysis_messages(resume_content, jd_content)
        
        response = await self.chat_completion(messages)
        return self._parse_optimization_response(response)
    
    async def generate_interview_questions(self, resume_content: Dict[str, Any], jd_content: str = "", question_count: int = 10) -> List[Dict[str, str]]:
        """根据简历和JD生成面试问题"""
        
        # 使用新的提示词管理系统
        messages = ResumeAssistantPrompts.build_interview_questions_messages(resume_content, jd_content if jd_content else None, question_count)
        
        response = await self.chat_completion(messages)
        return self._parse_interview_questions(response)
    
    async def evaluate_interview_answer(self, question: str, answer: str, resume_content: Dict[str, Any]) -> Dict[str, Any]:
        """评估面试回答"""
        
        # 使用新的提示词管理系统
        messages = ResumeAssistantPrompts.build_interview_evaluation_messages(question, answer, resume_content)
        
        response = await self.chat_completion(messages)
        return self._parse_evaluation_response(response)
    
    async def generate_next_interview_question(self, conversation_history: List[Dict[str, str]], resume_content: Dict[str, Any]) -> Dict[str, str]:
        """根据对话历史生成下一个面试问题"""
        
        # 构建对话历史
        history_text = "\n".join([f"问题：{item['question']}\n回答：{item['answer']}" for item in conversation_history])
        
        prompt = f"""
        根据以下面试对话历史和候选人简历，生成一个合适的后续问题。

        对话历史：
        {history_text}

        候选人简历：
        {self._format_resume_content(resume_content)}

        请生成一个能够深入了解候选人能力的问题，避免重复之前的问题内容。

        请只返回问题内容，不要包含其他解释。
        """
        
        messages = [
            {"role": "system", "content": "你是一个专业的面试官，擅长根据对话历史提出深入的后续问题。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat_completion(messages)
        return {
            "question": response["choices"][0]["message"]["content"].strip(),
            "type": "follow_up"
        }
    
    async def chat_with_resume(self, user_message: str, resume_content: Dict[str, Any]) -> str:
        """简历优化聊天功能"""
        
        # 使用新的提示词管理系统
        messages = ResumeAssistantPrompts.build_chat_messages(user_message, resume_content)
        
        response = await self.chat_completion(messages)
        raw_content = response["choices"][0]["message"]["content"]
        return self._clean_ai_response(raw_content)
    
    def _format_resume_content(self, resume_content: Dict[str, Any]) -> str:
        """格式化简历内容用于AI分析"""
        formatted = []
        
        # 个人信息
        if resume_content.get("personal_info"):
            formatted.append("个人信息：")
            for key, value in resume_content["personal_info"].items():
                if value:
                    formatted.append(f"  {key}: {value}")
        
        # 教育背景
        if resume_content.get("education"):
            formatted.append("\n教育背景：")
            for edu in resume_content["education"]:
                formatted.append(f"  {edu.get('school', '')} - {edu.get('degree', '')} - {edu.get('major', '')}")
        
        # 工作经验
        if resume_content.get("work_experience"):
            formatted.append("\n工作经验：")
            for work in resume_content["work_experience"]:
                formatted.append(f"  {work.get('company', '')} - {work.get('position', '')}")
                if work.get("description"):
                    formatted.append(f"    {work['description']}")
        
        # 技能
        if resume_content.get("skills"):
            formatted.append("\n技能：")
            for skill in resume_content["skills"]:
                if isinstance(skill, dict):
                    formatted.append(f"  {skill.get('name', '')} ({skill.get('level', '')}, {skill.get('category', '')})")
                else:
                    formatted.append(f"  {skill}")
        
        # 项目经验
        if resume_content.get("projects"):
            formatted.append("\n项目经验：")
            for proj in resume_content["projects"]:
                formatted.append(f"  {proj.get('name', '')} - {proj.get('description', '')}")
                if proj.get("technologies"):
                    formatted.append(f"    技术栈：{', '.join(proj['technologies'])}")
                if proj.get("achievements"):
                    for achievement in proj["achievements"]:
                        formatted.append(f"    * {achievement}")
        
        return "\n".join(formatted)
    
    def _parse_optimization_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """解析优化建议响应（OpenAI格式）"""
        content = response["choices"][0]["message"]["content"]
        
        # 简单的文本解析，实际应用中可能需要更复杂的解析逻辑
        return {
            "content": content,
            "suggestions": self._extract_suggestions(content),
            "score": self._extract_score(content),
            "missing_skills": self._extract_missing_skills(content)
        }
    
    def _parse_interview_questions(self, response: Dict[str, Any]) -> List[Dict[str, str]]:
        """解析面试问题响应（OpenAI格式）"""
        content = response["choices"][0]["message"]["content"]
        
        # 清理内容，去掉多余的格式化信息
        content = content.strip()
        
        # 简单的文本解析，提取问题
        questions = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # 跳过空行
            if not line:
                continue
                
            # 跳过数字编号（如"1. "、"2. "等）
            if line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.', '11.', '12.', '13.', '14.', '15.', '16.', '17.', '18.', '19.', '20.')):
                line = line.split('.', 1)[1].strip()
            
            # 跳过格式化标签（如"问题内容："、"问题类型："等）
            if any(keyword in line for keyword in ['问题内容：', '问题类型：', '考察要点：', '**问题', '**']):
                # 如果包含"问题内容："，提取冒号后的内容
                if '问题内容：' in line:
                    line = line.split('问题内容：')[1].strip()
                elif '：' in line and any(keyword in line for keyword in ['问题', '内容']):
                    line = line.split('：')[1].strip()
                else:
                    continue
            
            # 清理markdown格式符号
            line = line.replace('**', '').replace('*', '').strip()
            
            # 如果是问题（包含问号），添加到列表中
            if line and ('?' in line or '？' in line):
                questions.append({
                    "question": line,
                    "type": "general"
                })
        
        return questions
    
    def _parse_evaluation_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """解析评估响应（OpenAI格式）- 适配对话式回应"""
        content = response["choices"][0]["message"]["content"]
        
        return {
            "content": content,
            "score": 3,  # 默认给中等分数，因为现在不强调评分
            "feedback": content,  # 直接使用面试官的回应作为反馈
            "suggestions": []  # 不再强制提取建议
        }
    
    def _extract_suggestions(self, content: str) -> List[str]:
        """从内容中提取建议"""
        suggestions = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and ('建议' in line or '优化' in line or '改进' in line):
                suggestions.append(line)
        
        return suggestions
    
    def _extract_score(self, content: str) -> int:
        """从内容中提取评分"""
        import re
        
        # 查找数字评分
        score_patterns = [
            r'(\d+)分',
            r'评分[：:]?\s*(\d+)',
            r'得分[：:]?\s*(\d+)',
            r'(\d+)/100',
            r'(\d+)%'
        ]
        
        for pattern in score_patterns:
            matches = re.findall(pattern, content)
            if matches:
                return int(matches[0])
        
        return 0
    
    def _extract_missing_skills(self, content: str) -> List[str]:
        """从内容中提取缺失的技能"""
        missing_skills = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and ('缺失' in line or '需要' in line or '不足' in line):
                missing_skills.append(line)
        
        return missing_skills
    
    async def calculate_overall_score(self, interview_session: Dict[str, Any]) -> int:
        """计算面试整体分数"""
        try:
            # 从面试会话中提取所有答案的评估分数
            answers = interview_session.get('answers', [])
            if not answers:
                return 0
            
            # 收集所有单题评估分数
            scores = []
            for answer in answers:
                if isinstance(answer, dict) and 'evaluation' in answer:
                    evaluation = answer['evaluation']
                    if isinstance(evaluation, dict) and 'score' in evaluation:
                        scores.append(evaluation['score'])
            
            if not scores:
                # 如果没有单题分数，使用AI生成整体评价
                questions = interview_session.get('questions', [])
                conversation_history = []
                
                for i, answer in enumerate(answers):
                    if i < len(questions) and isinstance(answer, dict):
                        conversation_history.append({
                            "question": questions[i].get("question", ""),
                            "answer": answer.get("answer", "")
                        })
                
                if conversation_history:
                    # 构建整体评估提示
                    history_text = "\n".join([
                        f"问题：{item['question']}\n回答：{item['answer']}\n"
                        for item in conversation_history
                    ])
                    
                    prompt = f"""
                    根据以下完整的面试对话，给出一个0-100的整体评分。
                    
                    面试对话：
                    {history_text}
                    
                    请综合考虑以下因素：
                    1. 回答的完整性和逻辑性
                    2. 专业技能展现
                    3. 沟通能力和表达清晰度
                    4. 对问题的理解和应对能力
                    
                    请只返回一个数字分数（0-100），不要包含其他文字。
                    """
                    
                    messages = [
                        {"role": "system", "content": "你是一个专业的面试评估师，能够客观公正地评估面试表现。"},
                        {"role": "user", "content": prompt}
                    ]
                    
                    response = await self.chat_completion(messages)
                    content = response["choices"][0]["message"]["content"].strip()
                    
                    # 从响应中提取分数
                    import re
                    score_match = re.search(r'\d+', content)
                    if score_match:
                        return min(100, max(0, int(score_match.group())))
                
                return 0
            
            # 计算平均分数
            return round(sum(scores) / len(scores))
            
        except Exception as e:
            print(f"计算整体分数时出错: {e}")
            return 0

    def _clean_ai_response(self, content: str) -> str:
        """清理AI响应格式，优化Markdown显示"""
        import re
        
        # 移除混乱的星号格式符号
        content = re.sub(r'\*\s*\*\*([^*]+)\*\*\s*:', r'**\1**:', content)
        content = re.sub(r'\*\s*\*\*([^*]+)\*\*\s*-', r'**\1** -', content)
        
        # 清理多余的星号
        content = re.sub(r'\*{3,}', '**', content)
        content = re.sub(r'^\*\s+', '- ', content, flags=re.MULTILINE)
        
        # 优化emoji和格式符号
        content = re.sub(r'🎯\s*\*\*([^*]+)\*\*', r'## \1', content)
        content = re.sub(r'💡\s*\*\*([^*]+)\*\*', r'### \1', content)
        content = re.sub(r'✅\s*', r'- ✅ ', content)
        content = re.sub(r'❌\s*', r'- ❌ ', content)
        
        # 优化列表格式
        content = re.sub(r'^\d+\.\s*\*\*([^*]+)\*\*\s*-\s*', r'\1. **\1** - ', content, flags=re.MULTILINE)
        
        # 清理多余的空行
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 确保代码块格式正确
        content = re.sub(r'```([^`]+)```', r'\n```\n\1\n```\n', content)
        
        # 优化段落分隔
        content = content.strip()
        
        return content