"""
面试回答评分服务
提供多维度的回答质量评估
"""

import re
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from app.services.openrouter_service import OpenRouterService

@dataclass
class ScoringResult:
    """评分结果数据结构"""
    relevance_score: float  # 内容相关性评分 (0-100)
    star_analysis: Dict[str, bool]  # STAR法则分析
    keyword_match: Dict[str, Any]  # 关键词匹配结果
    fluency_score: float  # 语言流畅度评分 (0-100)
    overall_score: float  # 综合评分 (0-100)
    suggestions: List[str]  # 改进建议

class InterviewScoringService:
    """面试回答评分服务"""
    
    def __init__(self):
        # 技术相关关键词库
        self.tech_keywords = {
            "frontend": ["react", "vue", "angular", "javascript", "typescript", "html", "css", "webpack", "vite"],
            "backend": ["python", "java", "nodejs", "golang", "rust", "php", "django", "flask", "fastapi", "spring"],
            "database": ["mysql", "postgresql", "mongodb", "redis", "elasticsearch", "sqlite"],
            "cloud": ["aws", "azure", "gcp", "docker", "kubernetes", "microservices"],
            "ai_ml": ["machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy"],
            "tools": ["git", "jenkins", "docker", "kubernetes", "nginx", "linux"]
        }
        
        # STAR法则关键词
        self.star_keywords = {
            "situation": ["项目", "场景", "情况", "背景", "当时", "在...中", "公司", "团队"],
            "task": ["任务", "目标", "需要", "要求", "负责", "职责", "工作"],
            "action": ["我", "实现", "开发", "设计", "采用", "使用", "解决", "处理", "优化"],
            "result": ["结果", "效果", "提升", "优化", "成功", "完成", "达到", "实现了", "数据", "%", "倍"]
        }
        
        # 初始化OpenRouter服务
        self.openrouter_service = OpenRouterService()
    
    async def score_answer(self, question: str, answer: str, resume_content: dict = None, jd_keywords: List[str] = None) -> ScoringResult:
        """
        对面试回答进行综合评分
        
        Args:
            question: 面试问题
            answer: 候选人回答
            resume_content: 简历内容（用于一致性检查）
            jd_keywords: 职位描述关键词
        
        Returns:
            ScoringResult: 评分结果
        """
        # 1. 内容相关性评分
        relevance_score = self._score_relevance(question, answer)
        
        # 2. STAR法则分析
        star_analysis = self._analyze_star_method(answer)
        
        # 3. 关键词匹配
        keyword_match = self._analyze_keywords(answer, jd_keywords)
        
        # 4. 语言流畅度评分
        fluency_score = self._score_fluency(answer)
        
        # 5. 计算综合评分
        overall_score = self._calculate_overall_score(
            relevance_score, star_analysis, keyword_match, fluency_score
        )
        
        # 6. 生成改进建议
        suggestions = await self._generate_ai_suggestions(
            question, answer, relevance_score, star_analysis, keyword_match, fluency_score
        )
        
        return ScoringResult(
            relevance_score=relevance_score,
            star_analysis=star_analysis,
            keyword_match=keyword_match,
            fluency_score=fluency_score,
            overall_score=overall_score,
            suggestions=suggestions
        )
    
    def _score_relevance(self, question: str, answer: str) -> float:
        """评估回答与问题的相关性"""
        if not answer or len(answer.strip()) < 10:
            return 20.0
        
        # 基础长度评分
        length_score = min(len(answer) / 100, 1.0) * 30
        
        # 关键词重叠度
        question_words = set(re.findall(r'[\u4e00-\u9fff]+', question.lower()))
        answer_words = set(re.findall(r'[\u4e00-\u9fff]+', answer.lower()))
        
        if question_words:
            overlap_ratio = len(question_words.intersection(answer_words)) / len(question_words)
            overlap_score = overlap_ratio * 40
        else:
            overlap_score = 30
        
        # 结构化程度（是否有明确的回答结构）
        structure_indicators = ["首先", "其次", "然后", "最后", "第一", "第二", "另外", "此外"]
        structure_score = 30 if any(indicator in answer for indicator in structure_indicators) else 15
        
        return min(length_score + overlap_score + structure_score, 100)
    
    def _analyze_star_method(self, answer: str) -> Dict[str, bool]:
        """分析回答中STAR法则的应用"""
        star_result = {
            "situation": False,
            "task": False,
            "action": False,
            "result": False
        }
        
        answer_lower = answer.lower()
        
        for component, keywords in self.star_keywords.items():
            for keyword in keywords:
                if keyword in answer_lower:
                    star_result[component] = True
                    break
        
        return star_result
    
    def _analyze_keywords(self, answer: str, jd_keywords: List[str] = None) -> Dict[str, Any]:
        """分析关键词匹配情况"""
        answer_lower = answer.lower()
        
        # 技术关键词匹配
        matched_tech_keywords = []
        all_tech_keywords = []
        
        for category, keywords in self.tech_keywords.items():
            all_tech_keywords.extend(keywords)
            for keyword in keywords:
                if keyword in answer_lower:
                    matched_tech_keywords.append({
                        "keyword": keyword,
                        "category": category
                    })
        
        # JD关键词匹配（如果提供）
        matched_jd_keywords = []
        if jd_keywords:
            for keyword in jd_keywords:
                if keyword.lower() in answer_lower:
                    matched_jd_keywords.append(keyword)
        
        # 计算覆盖率
        tech_coverage = len(matched_tech_keywords) / max(len(all_tech_keywords), 1) * 100
        jd_coverage = len(matched_jd_keywords) / max(len(jd_keywords or []), 1) * 100 if jd_keywords else 0
        
        return {
            "matched_tech_keywords": matched_tech_keywords,
            "matched_jd_keywords": matched_jd_keywords,
            "tech_coverage": min(tech_coverage, 100),
            "jd_coverage": min(jd_coverage, 100),
            "total_matches": len(matched_tech_keywords) + len(matched_jd_keywords)
        }
    
    def _score_fluency(self, answer: str) -> float:
        """评估语言流畅度"""
        if not answer:
            return 0
        
        # 基础分数
        base_score = 50
        
        # 检查填充词
        filler_words = ["嗯", "啊", "那个", "就是", "然后就", "其实就是"]
        filler_count = sum(answer.count(word) for word in filler_words)
        filler_penalty = min(filler_count * 5, 30)
        
        # 检查重复词汇
        words = answer.split()
        unique_words = len(set(words))
        repetition_score = min(unique_words / max(len(words), 1) * 30, 30)
        
        # 句子长度适中性
        sentences = re.split(r'[。！？]', answer)
        avg_sentence_length = sum(len(s) for s in sentences) / max(len(sentences), 1)
        length_score = 20 if 10 <= avg_sentence_length <= 50 else 10
        
        total_score = base_score + repetition_score + length_score - filler_penalty
        return max(min(total_score, 100), 0)
    
    def _calculate_overall_score(self, relevance: float, star_analysis: Dict[str, bool], 
                                keyword_match: Dict[str, Any], fluency: float) -> float:
        """计算综合评分"""
        # 权重分配
        relevance_weight = 0.4
        star_weight = 0.3
        keyword_weight = 0.2
        fluency_weight = 0.1
        
        # STAR评分
        star_score = sum(star_analysis.values()) / 4 * 100
        
        # 关键词评分
        keyword_score = (keyword_match["tech_coverage"] * 0.7 + keyword_match["jd_coverage"] * 0.3)
        
        overall = (
            relevance * relevance_weight +
            star_score * star_weight +
            keyword_score * keyword_weight +
            fluency * fluency_weight
        )
        
        return min(overall, 100)
    
    async def _generate_ai_suggestions(self, question: str, answer: str, relevance: float, 
                                     star_analysis: Dict[str, bool], keyword_match: Dict[str, Any], 
                                     fluency: float) -> List[str]:
        """使用AI生成个性化改进建议"""
        
        # 构建评分上下文
        star_status = []
        for component, completed in star_analysis.items():
            status = "✓" if completed else "✗"
            component_name = {
                "situation": "情境背景",
                "task": "具体任务", 
                "action": "采取行动",
                "result": "最终结果"
            }[component]
            star_status.append(f"{status} {component_name}")
        
        star_status_text = " | ".join(star_status)
        
        # 构建AI提示词
        prompt = f"""你是一位资深的面试教练，请分析以下面试问答并给出3条具体、可执行的优化建议。

面试问题：
{question}

候选人回答：
{answer}

当前评分分析：
- 内容相关性：{relevance:.0f}分
- STAR法则完成度：{star_status_text}
- 技术关键词匹配：{keyword_match.get('total_matches', 0)}个
- 表达流畅度：{fluency:.0f}分

请基于以上分析，给出3条具体的优化建议。要求：
1. 每条建议要针对具体的问题，不要泛泛而谈
2. 给出可执行的改进方法，包含具体的示例或模板
3. 建议要简洁明了，每条不超过50字
4. 按重要性排序，最重要的放在前面

请直接返回3条建议，格式如下：
1. [具体建议内容]
2. [具体建议内容] 
3. [具体建议内容]"""

        try:
            # 调用AI生成建议
            messages = [
                {"role": "system", "content": "你是一位专业的面试教练，擅长分析面试回答并给出针对性的改进建议。"},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.openrouter_service.chat_completion(messages)
            ai_response = response["choices"][0]["message"]["content"]
            
            # 解析AI回复，提取建议
            suggestions = []
            lines = ai_response.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                # 匹配格式：1. 建议内容 或 - 建议内容
                if re.match(r'^[1-3]\.\s', line) or line.startswith('- '):
                    # 移除序号和符号
                    suggestion = re.sub(r'^[1-3]\.\s*', '', line)
                    suggestion = re.sub(r'^-\s*', '', suggestion)
                    
                    if suggestion:
                        suggestions.append(suggestion)
            
            # 如果解析失败，返回备用建议
            if not suggestions:
                suggestions = self._generate_fallback_suggestions(relevance, star_analysis, keyword_match)
            
            return suggestions[:3]  # 确保只返回3条建议
            
        except Exception as e:
            print(f"AI建议生成失败: {e}")
            # 生成备用建议
            return self._generate_fallback_suggestions(relevance, star_analysis, keyword_match)
    
    def _generate_fallback_suggestions(self, relevance: float, star_analysis: Dict[str, bool], 
                                     keyword_match: Dict[str, Any]) -> List[str]:
        """生成备用建议（当AI调用失败时使用）"""
        suggestions = []
        
        # 基于评分生成简单建议
        if relevance < 60:
            suggestions.append("回答需要更直接地回应问题的核心要点")
        
        # STAR法则建议
        missing_star = [k for k, v in star_analysis.items() if not v]
        if missing_star:
            if "situation" in missing_star:
                suggestions.append("建议补充项目背景和具体情境")
            elif "result" in missing_star:
                suggestions.append("建议添加具体的成果和数据")
        
        # 关键词建议
        if keyword_match.get("total_matches", 0) < 2:
            suggestions.append("可以使用更多相关的技术关键词")
        
        # 确保至少有3条建议
        while len(suggestions) < 3:
            suggestions.append("建议进一步完善回答的细节和逻辑结构")
        
        return suggestions[:3]