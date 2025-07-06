import os
import json
import asyncio
from typing import Dict, Any, Optional
import httpx
from app.services.file_service import FileService


class AIResumeParser:
    """基于DEEPSEEK大模型的智能简历解析器"""
    
    def __init__(self):
        self.file_service = FileService()
        self.api_key = os.getenv('DEEPSEEK_API_KEY', '')
        self.api_base = os.getenv('DEEPSEEK_API_BASE', 'https://api.deepseek.com/v1')
        self.model = 'deepseek-chat'
        self.max_retries = 3
        self.timeout = 30
        
        if not self.api_key:
            print("[WARNING] DEEPSEEK_API_KEY not found in environment variables")
    
    def parse_resume_text(self, text: str) -> Dict[str, Any]:
        """解析简历文本并结构化 - 主入口方法"""
        try:
            # 检查是否已有运行中的事件循环
            try:
                loop = asyncio.get_running_loop()
                # 如果有运行中的循环，使用同步方式调用
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._run_async_parse, text)
                    result = future.result()
                return result
            except RuntimeError:
                # 没有运行中的循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self._parse_with_ai(text))
                loop.close()
                return result
        except Exception as e:
            print(f"[ERROR] AI解析失败: {e}")
            # 如果AI解析失败，返回基础结构
            return self._create_fallback_result(text)
    
    def _run_async_parse(self, text: str) -> Dict[str, Any]:
        """在新线程中运行异步解析"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._parse_with_ai(text))
            return result
        finally:
            loop.close()
    
    async def parse_resume_text_async(self, text: str) -> Dict[str, Any]:
        """异步解析简历文本 - 用于FastAPI异步接口"""
        try:
            print(f"[DEBUG] 开始异步AI解析")
            result = await self._parse_with_ai(text)
            return result
        except Exception as e:
            print(f"[ERROR] 异步AI解析失败: {e}")
            # 如果AI解析失败，返回基础结构
            return self._create_fallback_result(text)
    
    async def _parse_with_ai(self, text: str) -> Dict[str, Any]:
        """使用AI解析简历"""
        prompt = self._create_prompt(text)
        
        for attempt in range(self.max_retries):
            try:
                print(f"[DEBUG] AI解析尝试 {attempt + 1}/{self.max_retries}")
                print(f"[DEBUG] API Base: {self.api_base}")
                print(f"[DEBUG] Model: {self.model}")
                print(f"[DEBUG] API Key配置: {'已配置' if self.api_key else '未配置'}")
                print(f"[DEBUG] Prompt长度: {len(prompt)}")
                
                # 配置更详细的超时和连接设置
                # 根据prompt长度动态调整读取超时
                base_read_timeout = 60.0  # 基础读取超时60秒
                if len(prompt) > 3000:
                    read_timeout = 90.0  # 长prompt使用90秒
                elif len(prompt) > 2000:
                    read_timeout = 75.0  # 中等长度prompt使用75秒
                else:
                    read_timeout = base_read_timeout
                
                timeout_config = httpx.Timeout(
                    connect=15.0,      # 连接超时增加到15秒
                    read=read_timeout, # 动态读取超时
                    write=15.0,        # 写入超时增加到15秒
                    pool=read_timeout  # 连接池超时与读取超时一致
                )
                
                print(f"[DEBUG] 动态超时配置: 连接{timeout_config.connect}s, 读取{timeout_config.read}s")
                
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    response = await client.post(
                        f"{self.api_base}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "你是一个专业的简历解析助手，擅长将简历文本转换为结构化的JSON数据。"
                                },
                                {
                                    "role": "user", 
                                    "content": prompt
                                }
                            ],
                            "temperature": 0.1,
                            "max_tokens": 4000
                        }
                    )
                
                print(f"[DEBUG] HTTP状态码: {response.status_code}")
                print(f"[DEBUG] 响应头: {dict(response.headers)}")
                
                if response.status_code == 200:
                    result = response.json()
                    ai_content = result['choices'][0]['message']['content']
                    print(f"[DEBUG] AI响应长度: {len(ai_content)}")
                    
                    # 解析AI返回的JSON
                    parsed_data = self._parse_ai_response(ai_content)
                    
                    # 验证和增强数据
                    validated_data = self._validate_and_enhance(parsed_data, text)
                    
                    print(f"[SUCCESS] AI解析成功")
                    return validated_data
                else:
                    print(f"[ERROR] API请求失败: {response.status_code} - {response.text}")
                    
            except httpx.TimeoutException as e:
                print(f"[ERROR] 第 {attempt + 1} 次尝试超时: {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"API请求超时，已重试{self.max_retries}次")
                await asyncio.sleep(2)  # 超时后等待更长时间
            except httpx.ConnectError as e:
                print(f"[ERROR] 第 {attempt + 1} 次连接失败: {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"无法连接到DEEPSEEK API服务器: {e}")
                await asyncio.sleep(2)
            except httpx.HTTPStatusError as e:
                print(f"[ERROR] 第 {attempt + 1} 次HTTP错误: {e.response.status_code}")
                print(f"[ERROR] 响应内容: {e.response.text[:500]}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"API返回错误状态码: {e.response.status_code}")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"[ERROR] 第 {attempt + 1} 次尝试失败: {type(e).__name__}: {e}")
                import traceback
                print(f"[DEBUG] 详细错误信息: {traceback.format_exc()}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"解析失败: {type(e).__name__}: {e}")
                await asyncio.sleep(1)  # 等待后重试
        
        raise Exception("所有重试尝试失败")
    
    def _create_prompt(self, text: str) -> str:
        """创建解析prompt"""
        return f"""解析以下简历为JSON格式：

简历内容：
{text}

输出JSON格式：
{{
  "personal_info": {{"name": "", "email": "", "phone": "", "position": "", "github": "", "linkedin": "", "website": "", "address": ""}},
  "education": [{{"school": "", "major": "", "degree": "", "duration": "", "description": ""}}],
  "work_experience": [{{"company": "", "position": "", "duration": "", "description": ""}}],
  "skills": [{{"name": "", "level": "", "category": ""}}],
  "projects": [{{"name": "", "description": "", "technologies": [], "role": "", "duration": "", "github_url": "", "demo_url": "", "achievements": []}}]
}}

要求：
1. 准确提取所有项目信息
2. 技能按类别分组（编程语言/框架/工具等）
3. 保持JSON格式正确
4. 时间格式统一"""
    
    def _parse_ai_response(self, ai_content: str) -> Dict[str, Any]:
        """解析AI返回的JSON内容"""
        try:
            # 提取JSON部分（去除可能的多余文字）
            start_idx = ai_content.find('{')
            end_idx = ai_content.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = ai_content[start_idx:end_idx]
                parsed_data = json.loads(json_str)
                print(f"[DEBUG] JSON解析成功")
                return parsed_data
            else:
                raise ValueError("无法找到有效的JSON格式")
                
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON解析失败: {e}")
            print(f"[DEBUG] AI响应内容: {ai_content[:500]}...")
            raise
    
    def _validate_and_enhance(self, data: Dict[str, Any], original_text: str) -> Dict[str, Any]:
        """验证和增强数据"""
        print(f"[DEBUG] 开始数据验证和增强")
        
        # 确保基本结构存在
        validated_data = {
            "personal_info": data.get("personal_info", {}),
            "education": data.get("education", []),
            "work_experience": data.get("work_experience", []),
            "skills": data.get("skills", []),
            "projects": data.get("projects", []),
            "other_info": {},
            "raw_text": original_text
        }
        
        # 验证个人信息
        personal_info = validated_data["personal_info"]
        if not isinstance(personal_info, dict):
            validated_data["personal_info"] = {}
        
        # 验证技能格式
        skills = validated_data["skills"]
        if isinstance(skills, list):
            validated_skills = []
            for skill in skills:
                if isinstance(skill, dict) and skill.get("name"):
                    validated_skills.append({
                        "name": str(skill.get("name", "")),
                        "level": str(skill.get("level", "熟练")),
                        "category": str(skill.get("category", "其他"))
                    })
                elif isinstance(skill, str):
                    # 纯字符串格式的技能
                    validated_skills.append({
                        "name": skill,
                        "level": "熟练",
                        "category": "其他"
                    })
            validated_data["skills"] = validated_skills
        
        # 验证项目格式
        projects = validated_data["projects"]
        if isinstance(projects, list):
            validated_projects = []
            for project in projects:
                if isinstance(project, dict) and project.get("name"):
                    validated_project = {
                        "name": str(project.get("name", "")),
                        "description": str(project.get("description", "")),
                        "technologies": project.get("technologies", []) if isinstance(project.get("technologies"), list) else [],
                        "role": str(project.get("role", "")),
                        "duration": str(project.get("duration", "")),
                        "github_url": str(project.get("github_url", "")),
                        "demo_url": str(project.get("demo_url", "")),
                        "achievements": project.get("achievements", []) if isinstance(project.get("achievements"), list) else []
                    }
                    validated_projects.append(validated_project)
            validated_data["projects"] = validated_projects
        
        # 计算解析质量分
        quality_score = self._calculate_parsing_quality(validated_data)
        validated_data["parsing_quality"] = quality_score
        
        print(f"[DEBUG] 数据验证完成，质量分: {quality_score:.2f}")
        return validated_data
    
    def _calculate_parsing_quality(self, resume_data: Dict[str, Any]) -> float:
        """计算解析质量分 (0-1)"""
        score = 0.0
        
        # 个人信息完整度 (40%)
        personal_info = resume_data.get("personal_info", {})
        personal_score = 0
        if personal_info.get("name"): personal_score += 4
        if personal_info.get("email"): personal_score += 3
        if personal_info.get("phone"): personal_score += 3
        score += min(personal_score / 10, 1.0) * 0.4
        
        # 技能完整度 (25%)
        skills = resume_data.get("skills", [])
        if skills and len(skills) > 0:
            skills_score = min(len(skills) / 8, 1.0)  # 8个技能满分
            score += skills_score * 0.25
        
        # 项目完整度 (25%)
        projects = resume_data.get("projects", [])
        if projects and len(projects) > 0:
            projects_score = min(len(projects) / 3, 1.0)  # 3个项目满分
            score += projects_score * 0.25
        
        # 教育信息完整度 (10%)
        education = resume_data.get("education", [])
        if education and len(education) > 0:
            score += 0.1
        
        return round(score, 2)
    
    def _create_fallback_result(self, text: str) -> Dict[str, Any]:
        """创建备用结果（当AI解析失败时）"""
        print(f"[DEBUG] 创建备用结果")
        
        return {
            "personal_info": {},
            "education": [],
            "work_experience": [],
            "skills": [],
            "projects": [],
            "other_info": {},
            "raw_text": text,
            "parsing_quality": 0.0,
            "parsing_method": "fallback"
        }


# 保持向后兼容性
ResumeParser = AIResumeParser