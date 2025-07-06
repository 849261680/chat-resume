import httpx
from typing import Dict, Any, List
from app.core.config import settings

class DeepSeekService:
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.api_base = settings.DEEPSEEK_API_BASE
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def chat_completion(self, messages: List[Dict[str, str]], model: str = "deepseek-chat") -> Dict[str, Any]:
        """调用 DeepSeek Chat API"""
        url = f"{self.api_base}/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": False
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
    
    async def analyze_resume_jd_match(self, resume_content: Dict[str, Any], jd_content: str) -> Dict[str, Any]:
        """分析简历与JD的匹配度"""
        
        # 构建提示词
        prompt = f"""
        请分析以下简历与岗位描述的匹配度，并提供优化建议。

        简历内容：
        {self._format_resume_content(resume_content)}

        岗位描述：
        {jd_content}

        请按以下格式返回分析结果：
        1. 匹配度评分（0-100分）
        2. 匹配的技能和经验
        3. 缺失的关键技能
        4. 简历优化建议（具体的修改建议）
        5. 关键词优化建议

        请用中文回答，并提供具体、可操作的建议。
        """
        
        messages = [
            {"role": "system", "content": "你是一个专业的HR顾问和简历优化专家，擅长分析简历与岗位要求的匹配度并提供优化建议。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat_completion(messages)
        return self._parse_optimization_response(response)
    
    async def generate_interview_questions(self, resume_content: Dict[str, Any], jd_content: str = "") -> List[Dict[str, str]]:
        """根据简历和JD生成面试问题"""
        
        resume_text = self._format_resume_content(resume_content)
        
        prompt = f"""
        根据以下简历信息{"和岗位描述" if jd_content else ""}，生成5-8个面试问题。

        简历信息：
        {resume_text}

        {"岗位描述：" + jd_content if jd_content else ""}

        请生成以下类型的问题：
        1. 基础背景问题（1-2个）
        2. 技能验证问题（2-3个）
        3. 项目经验问题（2-3个）
        4. 行为面试问题（1-2个）

        每个问题请包含：
        - 问题内容
        - 问题类型
        - 考察要点

        请用中文回答。
        """
        
        messages = [
            {"role": "system", "content": "你是一个专业的面试官，擅长根据简历和岗位要求设计面试问题。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat_completion(messages)
        return self._parse_interview_questions(response)
    
    async def evaluate_interview_answer(self, question: str, answer: str, resume_content: Dict[str, Any]) -> Dict[str, Any]:
        """评估面试回答"""
        
        prompt = f"""
        请评估以下面试回答：

        问题：{question}
        回答：{answer}

        候选人简历信息：
        {self._format_resume_content(resume_content)}

        请从以下几个方面进行评估：
        1. 回答的完整性和逻辑性
        2. 技术深度和准确性
        3. 与简历信息的一致性
        4. 沟通表达能力
        5. 改进建议

        请给出评分（1-5分）和具体的反馈建议。
        """
        
        messages = [
            {"role": "system", "content": "你是一个专业的面试官，擅长评估候选人的面试回答。"},
            {"role": "user", "content": prompt}
        ]
        
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
                for resp in work.get("responsibilities", []):
                    formatted.append(f"    - {resp}")
        
        # 技能
        if resume_content.get("skills"):
            formatted.append(f"\n技能：{', '.join(resume_content['skills'])}")
        
        # 项目经验
        if resume_content.get("projects"):
            formatted.append("\n项目经验：")
            for proj in resume_content["projects"]:
                formatted.append(f"  {proj.get('name', '')} - {proj.get('description', '')}")
        
        return "\n".join(formatted)
    
    def _parse_optimization_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """解析优化建议响应"""
        content = response["choices"][0]["message"]["content"]
        
        # 简单的文本解析，实际应用中可能需要更复杂的解析逻辑
        return {
            "content": content,
            "suggestions": self._extract_suggestions(content),
            "score": self._extract_score(content),
            "missing_skills": self._extract_missing_skills(content)
        }
    
    def _parse_interview_questions(self, response: Dict[str, Any]) -> List[Dict[str, str]]:
        """解析面试问题响应"""
        content = response["choices"][0]["message"]["content"]
        
        # 简单的文本解析，提取问题
        questions = []
        lines = content.split('\n')
        current_question = ""
        
        for line in lines:
            line = line.strip()
            if line and ('?' in line or '？' in line):
                if current_question:
                    questions.append({
                        "question": current_question,
                        "type": "general"
                    })
                current_question = line
            elif current_question and line:
                current_question += " " + line
        
        if current_question:
            questions.append({
                "question": current_question,
                "type": "general"
            })
        
        return questions
    
    def _parse_evaluation_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """解析评估响应"""
        content = response["choices"][0]["message"]["content"]
        
        return {
            "content": content,
            "score": self._extract_score(content),
            "feedback": content,
            "suggestions": self._extract_suggestions(content)
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