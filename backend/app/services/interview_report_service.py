"""
面试报告生成服务
基于面试对话数据生成详细的分析报告
"""

from typing import Dict, Any, List, Optional
import json
import re
from datetime import datetime
from app.services.openrouter_service import OpenRouterService
from app.models.resume import InterviewSession


class InterviewReportService:
    """面试报告生成服务类"""
    
    def __init__(self):
        self.openrouter_service = OpenRouterService()
    
    def _safe_json_parse(self, content: str, default_value: Dict[str, Any] = None) -> Dict[str, Any]:
        """安全的JSON解析函数"""
        try:
            # 清理可能的非JSON内容
            content = content.strip()
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()
            
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}, 内容前200字符: {content[:200]}...")
            return default_value or {}
        except Exception as e:
            print(f"解析时发生其他错误: {e}")
            return default_value or {}
    
    async def generate_comprehensive_report(self, interview_session: InterviewSession) -> Dict[str, Any]:
        """生成完整的面试报告"""
        
        # 构建对话历史并检查数据完整性
        conversation_history = self._build_conversation_history(interview_session)
        
        if not conversation_history:
            # 对于进行中的面试，如果还没有对话历史，返回基础报告
            if interview_session.status == "active":
                return await self._generate_basic_report(interview_session)
            else:
                # 提供更详细的错误信息
                questions_count = len(interview_session.questions or [])
                answers_count = len(interview_session.answers or [])
                raise ValueError(f"面试数据不完整，无法生成报告。问题数量：{questions_count}，答案数量：{answers_count}。请确保面试已正常进行并保存了问答数据。")
        
        # 并行生成各个部分的分析
        tasks = [
            self._analyze_competency_scores(conversation_history, interview_session),
            self._generate_ai_feedback(conversation_history, interview_session),
            self._analyze_conversation_details(conversation_history, interview_session),
            self._analyze_keywords_coverage(conversation_history, interview_session.jd_content or ""),
            self._analyze_frequent_words(conversation_history),
            self._generate_reference_answers(interview_session)
        ]
        
        # 执行所有分析任务
        competency_scores = await tasks[0]
        ai_feedback = await tasks[1] 
        conversation_details = await tasks[2]
        keyword_analysis = await tasks[3]
        word_frequency = await tasks[4]
        reference_answers = await tasks[5]
        
        # 组装最终报告
        report = {
            "id": interview_session.id,
            "resume_title": getattr(interview_session, 'resume_title', '简历'),
            "job_position": interview_session.job_position or "未指定职位",
            "interview_mode": self._get_interview_mode_name(interview_session.interview_mode),
            "jd_content": interview_session.jd_content or "",
            "overall_score": interview_session.overall_score or 0,
            "performance_level": self._get_performance_level(interview_session.overall_score or 0) if interview_session.status == "completed" else "进行中",
            "interview_date": self._format_date(interview_session.created_at),
            "duration_minutes": self._calculate_duration(interview_session),
            "total_questions": len(interview_session.questions),
            "answered_questions": len(interview_session.answers or []),
            "progress_percentage": self._calculate_progress(interview_session),
            "competency_scores": competency_scores,
            "ai_highlights": ai_feedback.get("highlights", []),
            "ai_improvements": ai_feedback.get("improvements", []),
            "conversation": conversation_details,
            "all_questions": self._format_all_questions(interview_session),
            "reference_answers": reference_answers,
            "jd_keywords": keyword_analysis.get("keywords", []),
            "coverage_rate": keyword_analysis.get("coverage_rate", 0),
            "frequent_words": word_frequency,
            "status": interview_session.status,
            "status_message": "面试已完成" if interview_session.status == "completed" else "面试正在进行中"
        }
        
        return report
    
    def _build_conversation_history(self, interview_session: InterviewSession) -> List[Dict[str, str]]:
        """构建对话历史，兼容新旧数据格式"""
        conversation = []
        
        questions = interview_session.questions or []
        answers = interview_session.answers or []
        
        # 兼容性处理：如果answers为空但有历史数据，尝试从其他地方获取
        if not answers and hasattr(interview_session, 'feedback') and interview_session.feedback:
            # 老版本可能将对话存储在feedback中
            if isinstance(interview_session.feedback, dict) and 'conversation' in interview_session.feedback:
                old_conversation = interview_session.feedback.get('conversation', [])
                for item in old_conversation:
                    if isinstance(item, dict) and 'question' in item and 'answer' in item:
                        conversation.append({
                            "question": item['question'],
                            "answer": item['answer'],
                            "index": len(conversation)
                        })
                return conversation
        
        for i in range(min(len(questions), len(answers))):
            question_data = questions[i]
            answer_data = answers[i]
            
            # 提取问题内容
            if isinstance(question_data, dict):
                question_text = question_data.get("question", "")
            else:
                question_text = str(question_data)
            
            # 提取答案内容
            if isinstance(answer_data, dict):
                answer_text = answer_data.get("answer", "")
            else:
                answer_text = str(answer_data)
            
            if question_text and answer_text:
                conversation.append({
                    "question": question_text,
                    "answer": answer_text,
                    "index": i
                })
        
        return conversation
    
    async def _analyze_competency_scores(self, conversation: List[Dict[str, str]], interview_session: InterviewSession) -> Dict[str, int]:
        """分析能力评分"""
        
        if not conversation:
            return {
                "job_fit": 0,
                "technical_depth": 0, 
                "project_exposition": 0,
                "communication": 0,
                "behavioral": 0
            }
        
        # 构建对话文本
        conversation_text = "\n".join([
            f"问题：{item['question']}\n回答：{item['answer']}"
            for item in conversation
        ])
        
        prompt = f"""
        基于以下面试对话，从五个维度评估候选人的能力，每个维度给出0-100的分数：

        面试对话：
        {conversation_text}

        评估维度：
        1. 岗位匹配度：候选人的经验、技能与目标职位的匹配程度
        2. 技术深度：技术理解的深度和广度，解决技术问题的能力
        3. 项目阐述：项目经验的描述清晰度和价值体现
        4. 沟通表达：表达的逻辑性、清晰度和专业性
        5. 行为表现：团队协作、学习能力、工作态度等软技能

        请只返回JSON格式的分数，格式如下：
        {{
            "job_fit": 85,
            "technical_depth": 90,
            "project_exposition": 80,
            "communication": 88,
            "behavioral": 82
        }}
        """
        
        try:
            messages = [
                {"role": "system", "content": "你是一个专业的面试评估师，能够客观准确地评估候选人的各项能力。"},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.openrouter_service.chat_completion(messages)
            content = response["choices"][0]["message"]["content"].strip()
            
            # 尝试解析JSON
            scores = self._safe_json_parse(content, {
                "job_fit": 75,
                "technical_depth": 75,
                "project_exposition": 75,
                "communication": 75,
                "behavioral": 75
            })
            
            # 验证和规范化分数
            normalized_scores = {}
            for key in ["job_fit", "technical_depth", "project_exposition", "communication", "behavioral"]:
                score = scores.get(key, 0)
                normalized_scores[key] = max(0, min(100, int(score)))
            
            return normalized_scores
            
        except Exception as e:
            print(f"能力评分分析失败: {e}")
            # 基于现有评估数据计算默认分数
            overall_score = interview_session.overall_score or 75
            return {
                "job_fit": min(100, max(60, overall_score - 5)),
                "technical_depth": min(100, max(60, overall_score + 5)),
                "project_exposition": min(100, max(60, overall_score - 10)),
                "communication": min(100, max(60, overall_score)),
                "behavioral": min(100, max(60, overall_score - 8))
            }
    
    async def _generate_ai_feedback(self, conversation: List[Dict[str, str]], interview_session: InterviewSession) -> Dict[str, List[str]]:
        """生成AI总体反馈"""
        
        if not conversation:
            return {"highlights": [], "improvements": []}
        
        conversation_text = "\n".join([
            f"问题{i+1}：{item['question']}\n回答{i+1}：{item['answer']}"
            for i, item in enumerate(conversation)
        ])
        
        prompt = f"""
        基于以下完整面试对话，生成专业的面试反馈：

        {conversation_text}

        请生成：
        1. 亮点表现（2-3个具体的优点）
        2. 改进建议（2-3个建设性的建议）

        要求：
        - 反馈要具体、可操作
        - 基于实际对话内容
        - 语言专业但不失温暖
        - 每个点不超过100字

        请返回JSON格式：
        {{
            "highlights": ["亮点1", "亮点2", "亮点3"],
            "improvements": ["建议1", "建议2", "建议3"]
        }}
        """
        
        try:
            messages = [
                {"role": "system", "content": "你是一个经验丰富的面试官，能够给出专业而有建设性的面试反馈。"},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.openrouter_service.chat_completion(messages)
            content = response["choices"][0]["message"]["content"].strip()
            
            feedback = self._safe_json_parse(content, {
                "highlights": [],
                "improvements": []
            })
            return {
                "highlights": feedback.get("highlights", []),
                "improvements": feedback.get("improvements", [])
            }
            
        except Exception as e:
            print(f"AI反馈生成失败: {e}")
            # 基于面试数据生成基础反馈
            job_position = interview_session.job_position or "该职位"
            highlights = [
                f"候选人在{job_position}相关问题的回答中表现出了专业性",
                f"回答了{len(conversation)}个问题，展现了良好的沟通能力"
            ]
            improvements = [
                "可以在技术回答中提供更多具体的项目经验和数据支撑",
                "建议在行为问题的回答中多使用STAR法则来结构化表达"
            ]
            
            return {"highlights": highlights, "improvements": improvements}
    
    async def _analyze_conversation_details(self, conversation: List[Dict[str, str]], interview_session: InterviewSession) -> List[Dict[str, Any]]:
        """分析每个问答的详细反馈"""
        
        details = []
        
        for item in conversation:
            # 为每个问答生成详细评估
            try:
                evaluation = await self._evaluate_single_qa(item["question"], item["answer"])
                
                details.append({
                    "question": item["question"],
                    "answer": item["answer"],
                    "ai_feedback": {
                        "score": evaluation.get("score", 7),
                        "strengths": evaluation.get("strengths", ["回答相关性好"]),
                        "suggestions": evaluation.get("suggestions", ["可以提供更多细节"]),
                        "reference_answer": evaluation.get("reference_answer")
                    }
                })
                
            except Exception as e:
                print(f"单个问答分析失败: {e}")
                # 添加默认评估
                details.append({
                    "question": item["question"],
                    "answer": item["answer"],
                    "ai_feedback": {
                        "score": 7,
                        "strengths": ["回答切题"],
                        "suggestions": ["可以更加具体"],
                        "reference_answer": None
                    }
                })
        
        return details
    
    async def _evaluate_single_qa(self, question: str, answer: str) -> Dict[str, Any]:
        """评估单个问答"""
        
        prompt = f"""
        评估以下面试问答：

        问题：{question}
        回答：{answer}

        请从以下方面评估：
        1. 评分（1-10分）
        2. 回答的优点（2-3个）
        3. 改进建议（2-3个）

        返回JSON格式：
        {{
            "score": 8,
            "strengths": ["优点1", "优点2"],
            "suggestions": ["建议1", "建议2"]
        }}
        """
        
        messages = [
            {"role": "system", "content": "你是一个专业的面试评估师。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.openrouter_service.chat_completion(messages)
        content = response["choices"][0]["message"]["content"].strip()
        
        return self._safe_json_parse(content, {
            "score": 75,
            "analysis": "分析暂时不可用"
        })
    
    async def _analyze_keywords_coverage(self, conversation: List[Dict[str, str]], jd_content: str) -> Dict[str, Any]:
        """分析关键词覆盖率"""
        
        if not jd_content.strip():
            return {"keywords": [], "coverage_rate": 0}
        
        # 从JD中提取关键词
        keywords = self._extract_jd_keywords(jd_content)
        
        # 统计回答中的关键词提及情况
        all_answers = " ".join([item["answer"] for item in conversation])
        
        keyword_analysis = []
        mentioned_count = 0
        
        for keyword in keywords:
            frequency = len(re.findall(rf'\b{re.escape(keyword)}\b', all_answers, re.IGNORECASE))
            mentioned = frequency > 0
            
            keyword_analysis.append({
                "keyword": keyword,
                "mentioned": mentioned,
                "frequency": frequency
            })
            
            if mentioned:
                mentioned_count += 1
        
        coverage_rate = (mentioned_count / len(keywords) * 100) if keywords else 0
        
        return {
            "keywords": keyword_analysis,
            "coverage_rate": round(coverage_rate)
        }
    
    def _extract_jd_keywords(self, jd_content: str) -> List[str]:
        """从JD中提取关键词"""
        
        # 技术关键词
        tech_keywords = [
            "Python", "Java", "JavaScript", "React", "Vue", "Angular", "Node.js",
            "Django", "Flask", "Spring", "MySQL", "PostgreSQL", "MongoDB", "Redis",
            "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "CI/CD",
            "机器学习", "深度学习", "AI", "人工智能", "算法", "数据结构",
            "RAG", "LangChain", "FastAPI", "REST API", "微服务", "分布式",
            "前端", "后端", "全栈", "移动开发", "Web开发"
        ]
        
        # 软技能关键词
        soft_keywords = [
            "团队协作", "沟通能力", "领导力", "项目管理", "问题解决",
            "学习能力", "创新思维", "责任心", "抗压能力", "时间管理"
        ]
        
        found_keywords = []
        jd_lower = jd_content.lower()
        
        # 检查技术关键词
        for keyword in tech_keywords:
            if keyword.lower() in jd_lower:
                found_keywords.append(keyword)
        
        # 检查软技能关键词
        for keyword in soft_keywords:
            if keyword in jd_content:
                found_keywords.append(keyword)
        
        # 如果没有找到关键词，返回默认列表
        if not found_keywords:
            found_keywords = ["技术能力", "项目经验", "团队协作", "学习能力", "沟通表达"]
        
        return found_keywords[:10]  # 最多返回10个关键词
    
    async def _analyze_frequent_words(self, conversation: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """分析高频词"""
        
        if not conversation:
            return []
        
        # 合并所有回答
        all_text = " ".join([item["answer"] for item in conversation])
        
        # 中文分词（简单版本）
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', all_text)
        
        # 过滤停用词
        stop_words = {
            "这个", "那个", "然后", "所以", "因为", "但是", "而且", "或者", "就是",
            "我们", "他们", "她们", "这样", "那样", "可以", "能够", "应该", "需要",
            "比较", "非常", "特别", "一些", "很多", "一直", "已经", "还是", "如果"
        }
        
        # 统计词频
        word_count = {}
        for word in words:
            if word not in stop_words and len(word) >= 2:
                word_count[word] = word_count.get(word, 0) + 1
        
        # 排序并返回前10个
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return [{"word": word, "count": count} for word, count in sorted_words]
    
    def _get_interview_mode_name(self, mode: str) -> str:
        """获取面试模式名称"""
        mode_names = {
            "comprehensive": "综合面试",
            "technical": "技术深挖",
            "behavioral": "行为面试"
        }
        return mode_names.get(mode, "综合面试")
    
    def _get_performance_level(self, score: int) -> str:
        """根据分数获取表现等级"""
        if score >= 90:
            return "表现优秀"
        elif score >= 80:
            return "表现良好"
        elif score >= 70:
            return "表现中等"
        elif score >= 60:
            return "需要改进"
        else:
            return "表现不佳"
    
    def _format_date(self, datetime_obj) -> str:
        """格式化日期"""
        if not datetime_obj:
            return "未知时间"
        
        try:
            if isinstance(datetime_obj, str):
                dt = datetime.fromisoformat(datetime_obj.replace('Z', '+00:00'))
            else:
                dt = datetime_obj
            
            return dt.strftime("%Y年%m月%d日")
        except:
            return "未知时间"
    
    def _calculate_duration(self, interview_session: InterviewSession) -> int:
        """计算面试时长（分钟）"""
        try:
            if interview_session.created_at and interview_session.updated_at:
                delta = interview_session.updated_at - interview_session.created_at
                return max(1, int(delta.total_seconds() // 60))
            else:
                # 根据问题数量估算时长
                return len(interview_session.questions or []) * 5
        except:
            return 25  # 默认25分钟
    
    async def _generate_basic_report(self, interview_session: InterviewSession) -> Dict[str, Any]:
        """为进行中的面试生成基础报告"""
        
        # 为基础报告也生成参考答案
        reference_answers = await self._generate_reference_answers(interview_session)
        
        return {
            "id": interview_session.id,
            "resume_title": getattr(interview_session, 'resume_title', '简历'),
            "job_position": interview_session.job_position or "未指定职位",
            "interview_mode": self._get_interview_mode_name(interview_session.interview_mode),
            "jd_content": interview_session.jd_content or "",
            "overall_score": 0,
            "performance_level": "进行中",
            "interview_date": self._format_date(interview_session.created_at),
            "duration_minutes": self._calculate_duration(interview_session),
            "total_questions": len(interview_session.questions or []),
            "answered_questions": len(interview_session.answers or []),
            "progress_percentage": self._calculate_progress(interview_session),
            "competency_scores": {
                "job_fit": 0,
                "technical_depth": 0,
                "project_exposition": 0,
                "communication": 0,
                "behavioral": 0
            },
            "ai_highlights": [],
            "ai_improvements": ["继续完成面试以获得详细分析"],
            "conversation": self._build_conversation_history(interview_session),
            "all_questions": self._format_all_questions(interview_session),
            "reference_answers": reference_answers,
            "jd_keywords": [],
            "coverage_rate": 0,
            "frequent_words": {},
            "status": "active",
            "status_message": "面试正在进行中，完成后将生成完整报告"
        }
    
    def _calculate_progress(self, interview_session: InterviewSession) -> int:
        """计算面试进度百分比"""
        total_questions = len(interview_session.questions or [])
        answered_questions = len(interview_session.answers or [])
        
        if total_questions == 0:
            return 0
        
        return min(100, int((answered_questions / total_questions) * 100))
    
    def _format_all_questions(self, interview_session: InterviewSession) -> List[Dict[str, Any]]:
        """格式化所有生成的问题，包括已回答和未回答的"""
        all_questions = []
        questions = interview_session.questions or []
        
        for i, question_data in enumerate(questions):
            # 提取问题内容
            if isinstance(question_data, dict):
                question_text = question_data.get("question", "")
                question_type = question_data.get("type", "general")
            else:
                question_text = str(question_data)
                question_type = "general"
            
            if question_text:
                all_questions.append({
                    "question": question_text,
                    "type": question_type,
                    "index": i
                })
        
        return all_questions
    
    async def _generate_reference_answers(self, interview_session: InterviewSession) -> List[Dict[str, Any]]:
        """为所有问题生成AI参考答案"""
        questions = interview_session.questions or []
        reference_answers = []
        
        # 获取简历内容
        resume_content = None
        if hasattr(interview_session, 'resume') and interview_session.resume:
            resume_content = interview_session.resume.content
        
        for i, question_data in enumerate(questions):
            # 提取问题内容
            if isinstance(question_data, dict):
                question_text = question_data.get("question", "")
            else:
                question_text = str(question_data)
            
            if question_text:
                try:
                    # 生成参考答案
                    reference_answer = await self._generate_single_reference_answer(
                        question_text, 
                        interview_session,
                        resume_content
                    )
                    
                    reference_answers.append({
                        "question": question_text,
                        "reference_answer": reference_answer,
                        "index": i
                    })
                except Exception as e:
                    print(f"生成问题 {i+1} 的参考答案失败: {e}")
                    reference_answers.append({
                        "question": question_text,
                        "reference_answer": "参考答案生成失败，请稍后重试。",
                        "index": i
                    })
        
        return reference_answers
    
    async def _generate_single_reference_answer(self, question: str, interview_session: InterviewSession, resume_content: dict = None) -> str:
        """为单个问题生成参考答案"""
        
        # 格式化简历内容
        resume_text = ""
        if resume_content:
            resume_text = self._format_resume_content(resume_content)
        
        # 构建提示词
        prompt = f"""
        作为专业的面试顾问，请基于候选人的简历信息为以下面试问题提供一个优秀的参考答案。

        面试问题：{question}
        
        职位背景：{interview_session.job_position or "通用职位"}
        
        候选人简历信息：
        {resume_text if resume_text else "简历信息不可用"}
        
        参考答案要求：
        1. 必须基于候选人的实际简历背景和经验
        2. 答案应该专业、具体、有说服力
        3. 体现候选人的真实能力和项目经验
        4. 使用STAR法则（情境、任务、行动、结果）
        5. 长度适中，大约100-200字
        6. 语言自然流畅，符合面试场景
        7. 如果简历中有相关经验，请具体引用
        
        请直接返回参考答案内容，不要包含"参考答案："等前缀。
        """
        
        messages = [
            {"role": "system", "content": "你是一位经验丰富的面试顾问，擅长基于候选人的实际简历背景为面试问题提供专业的参考答案。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.openrouter_service.chat_completion(messages)
        return response["choices"][0]["message"]["content"].strip()
    
    def _format_resume_content(self, resume_content: dict) -> str:
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