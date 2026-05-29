"""
简历解析服务模块

负责解析上传的简历文件，提取关键信息和结构化数据。
支持多种简历格式（PDF、Word等）的解析处理。
"""

import asyncio
import json
import logging
import os
import re
from time import perf_counter
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

from ..domain.file_service import FileService

logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()


class AIResumeParser:
    """基于 OpenRouter 的智能简历解析器。"""

    def __init__(self):
        """用于初始化当前对象。"""
        self.file_service = FileService()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.api_base = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
        self.model = (
            os.getenv("OPENROUTER_RESUME_PARSER_MODEL", "").strip()
            or os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
        )
        self.max_retries = 3
        self.timeout = 30

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not found in environment variables")

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
            logger.error(f"AI解析失败: {e}")
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
            result = await self._parse_with_ai(text)
            return result
        except Exception as e:
            logger.warning(
                "resume_parser.fallback",
                extra={"model": self.model, "error_type": type(e).__name__},
            )
            # 如果AI解析失败，返回基础结构
            return self._create_fallback_result(text)

    async def _parse_with_ai(self, text: str) -> Dict[str, Any]:
        """使用AI解析简历"""
        # 首先检查API密钥
        if not self.api_key or self.api_key.strip() == "":
            logger.error("OpenRouter API密钥未配置，无法进行AI解析")
            raise Exception("OpenRouter API密钥未配置")

        prompt = self._create_prompt(text)

        for attempt in range(self.max_retries):
            try:
                attempt_started_at = perf_counter()

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
                    connect=15.0,  # 连接超时增加到15秒
                    read=read_timeout,  # 动态读取超时
                    write=15.0,  # 写入超时增加到15秒
                    pool=read_timeout,  # 连接池超时与读取超时一致
                )

                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    response = await client.post(
                        f"{self.api_base}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://chat-resume.com",
                            "X-Title": "Chat Resume Parser",
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": (
                                        "你是一个专业的简历解析助手，"
                                        "擅长将简历文本转换为结构化的JSON数据。"
                                    ),
                                },
                                {"role": "user", "content": prompt},
                            ],
                            "temperature": 0.1,
                            "max_tokens": 8000,
                            "stream": False,
                        },
                    )

                if response.status_code == 200:
                    result = response.json()
                    ai_content = result["choices"][0]["message"]["content"]

                    # 解析AI返回的JSON
                    try:
                        parsed_data = self._parse_ai_response(ai_content)
                    except Exception as e:
                        logger.warning(
                            "resume_parser.json_failed",
                            extra={
                                "model": self.model,
                                "attempt": attempt + 1,
                                "error_type": type(e).__name__,
                                "response_chars": len(ai_content),
                            },
                        )
                        raise e

                    # 验证和增强数据
                    validated_data = self._validate_and_enhance(parsed_data, text)

                    logger.info(
                        (
                            "resume_parser.ai.completed model=%s attempt=%s "
                            "elapsed_ms=%.2f prompt_chars=%s response_chars=%s"
                        ),
                        self.model,
                        attempt + 1,
                        (perf_counter() - attempt_started_at) * 1000,
                        len(prompt),
                        len(ai_content),
                    )
                    return validated_data
                else:
                    logger.warning(
                        "resume_parser.ai.http_failed",
                        extra={
                            "model": self.model,
                            "attempt": attempt + 1,
                            "http_status": response.status_code,
                            "elapsed_ms": round(
                                (perf_counter() - attempt_started_at) * 1000, 2
                            ),
                        },
                    )

            except httpx.TimeoutException:
                logger.warning(
                    "resume_parser.ai.timeout",
                    extra={"model": self.model, "attempt": attempt + 1},
                )
                if attempt == self.max_retries - 1:
                    raise Exception(f"API请求超时，已重试{self.max_retries}次")
                await asyncio.sleep(2)  # 超时后等待更长时间
            except httpx.ConnectError as e:
                logger.warning(
                    "resume_parser.ai.connect_failed",
                    extra={"model": self.model, "attempt": attempt + 1},
                )
                if attempt == self.max_retries - 1:
                    raise Exception(f"无法连接到OpenRouter API服务器: {e}")
                await asyncio.sleep(2)
            except httpx.HTTPStatusError as e:
                logger.warning(
                    "resume_parser.ai.http_error",
                    extra={
                        "model": self.model,
                        "attempt": attempt + 1,
                        "http_status": e.response.status_code,
                    },
                )
                if attempt == self.max_retries - 1:
                    raise Exception(f"API返回错误状态码: {e.response.status_code}")
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(
                    "resume_parser.ai.failed",
                    extra={
                        "model": self.model,
                        "attempt": attempt + 1,
                        "error_type": type(e).__name__,
                    },
                )
                if attempt == self.max_retries - 1:
                    raise Exception(f"解析失败: {type(e).__name__}: {e}")
                await asyncio.sleep(1)  # 等待后重试

        raise Exception("所有重试尝试失败")

    def _create_prompt(self, text: str) -> str:
        """创建解析prompt"""
        return f"""你是一个专业的简历解析专家。请将以下简历内容解析为标准JSON格式。

**重要要求：**
1. 只返回JSON数据，不要包含任何其他文字说明
2. 确保JSON格式完全正确，可以被json.loads()解析
3. 如果某个字段没有信息，使用空字符串""或空数组[]

**简历内容：**
{text}

**请严格按照以下JSON格式返回数据：**
{{
  "personal_info": {{
    "name": "姓名",
    "email": "邮箱地址", 
    "phone": "电话号码",
    "position": "求职岗位",
    "github": "GitHub链接",
    "linkedin": "LinkedIn链接", 
    "website": "个人网站",
    "address": "地址"
  }},
  "education": [
    {{
      "school": "学校名称",
      "major": "专业", 
      "degree": "学位",
      "duration": "时间段",
      "description": "描述"
    }}
  ],
  "work_experience": [
    {{
      "company": "公司名称",
      "position": "职位",
      "duration": "时间段", 
      "description": "工作描述"
    }}
  ],
  "skills": [
    {{
      "category": "技能类别",
      "items": ["技能1", "技能2"]
    }}
  ],
  "projects": [
    {{
      "name": "项目名称",
      "description": "项目描述",
      "technologies": ["技术1", "技术2"],
      "role": "承担角色", 
      "duration": "项目时间",
      "github_url": "代码链接",
      "demo_url": "演示链接",
      "achievements": ["成就1", "成就2"]
    }}
  ]
}}

**再次提醒：只返回JSON数据，不要添加任何解释文字！**"""

    def _parse_ai_response(self, ai_content: str) -> Dict[str, Any]:
        """解析AI返回的JSON内容"""
        try:
            logger.debug(f"开始解析AI响应，长度: {len(ai_content)}")

            # 尝试多种方式提取JSON
            json_str = None

            # 方式1: 寻找完整的JSON对象
            start_idx = ai_content.find("{")
            end_idx = ai_content.rfind("}") + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = ai_content[start_idx:end_idx]
                logger.debug(f"提取的JSON字符串长度: {len(json_str)}")
                logger.debug(f"JSON前200字符: {json_str[:200]}")

            # 方式2: 如果找不到完整JSON，尝试整个内容
            if not json_str:
                json_str = ai_content.strip()
                logger.debug("使用完整响应作为JSON")

            # 尝试解析JSON
            if json_str:
                try:
                    parsed_data = json.loads(json_str)
                    logger.debug(f"JSON解析成功，包含字段: {list(parsed_data.keys())}")
                    return parsed_data
                except json.JSONDecodeError as e:
                    logger.warning(f"第一次JSON解析失败: {e}")

                    # 尝试清理和修复JSON
                    cleaned_json = self._clean_json_string(json_str)
                    logger.debug("尝试清理后的JSON")
                    parsed_data = json.loads(cleaned_json)
                    logger.debug("清理后JSON解析成功")
                    return parsed_data

            raise ValueError("无法找到有效的JSON格式")

        except json.JSONDecodeError as e:
            logger.error(f"最终JSON解析失败: {e}")
            logger.debug(f"失败的JSON内容: {json_str[:1000] if json_str else 'None'}")
            raise
        except Exception as e:
            logger.error(f"解析过程出现异常: {type(e).__name__}: {e}")
            raise

    def _clean_json_string(self, json_str: str) -> str:
        """清理和修复JSON字符串"""
        logger.debug("开始清理JSON字符串")

        # 移除可能的markdown代码块标记
        json_str = json_str.replace("```json", "").replace("```", "")

        # 移除可能的前后空白和换行
        json_str = json_str.strip()

        # 移除可能的BOM标记
        if json_str.startswith("\ufeff"):
            json_str = json_str[1:]

        # 修复JSON字符串内未转义的控制字符（换行、制表符等）
        json_str = self._fix_unescaped_control_chars(json_str)

        logger.debug(f"清理后JSON长度: {len(json_str)}")
        return json_str

    def _fix_unescaped_control_chars(self, json_str: str) -> str:
        """修复JSON字符串中未转义的控制字符（如换行符）"""
        result = []
        in_string = False
        escape_next = False

        for char in json_str:
            if escape_next:
                result.append(char)
                escape_next = False
            elif char == "\\":
                result.append(char)
                escape_next = True
            elif char == '"':
                in_string = not in_string
                result.append(char)
            elif in_string and char == "\n":
                result.append("\\n")
            elif in_string and char == "\r":
                result.append("\\r")
            elif in_string and char == "\t":
                result.append("\\t")
            else:
                result.append(char)

        return "".join(result)

    def _validate_and_enhance(
        self, data: Dict[str, Any], original_text: str
    ) -> Dict[str, Any]:
        """验证和增强数据"""
        logger.debug("开始数据验证和增强")

        # 确保基本结构存在
        validated_data = {
            "personal_info": data.get("personal_info", {}),
            "education": data.get("education", []),
            "work_experience": data.get("work_experience", []),
            "skills": data.get("skills", []),
            "projects": data.get("projects", []),
            "other_info": {},
            "raw_text": original_text,
        }

        # 验证个人信息
        personal_info = validated_data["personal_info"]
        if not isinstance(personal_info, dict):
            validated_data["personal_info"] = {}

        # 验证技能格式
        skills = validated_data["skills"]
        if isinstance(skills, list):
            validated_skills = []
            grouped_skills: dict[str, list[str]] = {}
            for skill in skills:
                if isinstance(skill, dict) and isinstance(skill.get("items"), list):
                    validated_skills.append(
                        {
                            "category": str(skill.get("category", "其他")),
                            "items": [
                                str(item).strip()
                                for item in skill.get("items", [])
                                if str(item).strip()
                            ],
                        }
                    )
                elif isinstance(skill, dict) and skill.get("name"):
                    category = str(skill.get("category", "其他"))
                    grouped_skills.setdefault(category, []).append(
                        str(skill.get("name", "")).strip()
                    )
                elif isinstance(skill, str):
                    grouped_skills.setdefault("其他", []).append(skill.strip())
            validated_skills.extend(
                {"category": category, "items": [item for item in items if item]}
                for category, items in grouped_skills.items()
                if any(items)
            )
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
                        "technologies": project.get("technologies", [])
                        if isinstance(project.get("technologies"), list)
                        else [],
                        "role": str(project.get("role", "")),
                        "duration": str(project.get("duration", "")),
                        "github_url": str(project.get("github_url", "")),
                        "demo_url": str(project.get("demo_url", "")),
                        "achievements": project.get("achievements", [])
                        if isinstance(project.get("achievements"), list)
                        else [],
                    }
                    validated_projects.append(validated_project)
            validated_data["projects"] = validated_projects

        # 计算解析质量分
        quality_score = self._calculate_parsing_quality(validated_data)
        validated_data["parsing_quality"] = quality_score
        validated_data["parsing_method"] = "ai"

        logger.debug(f"数据验证完成，质量分: {quality_score:.2f}")
        personal_info = validated_data.get("personal_info")
        if isinstance(personal_info, dict):
            logger.debug(f"个人信息字段: {list(personal_info.keys())}")
        logger.debug(f"技能数量: {len(validated_data['skills'])}")
        logger.debug(f"项目数量: {len(validated_data['projects'])}")
        return validated_data

    def _calculate_parsing_quality(self, resume_data: Dict[str, Any]) -> float:
        """计算解析质量分 (0-1)"""
        score = 0.0

        # 个人信息完整度 (40%)
        personal_info = resume_data.get("personal_info", {})
        personal_score = 0
        if personal_info.get("name"):
            personal_score += 4
        if personal_info.get("email"):
            personal_score += 3
        if personal_info.get("phone"):
            personal_score += 3
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

    def _extract_basic_info(self, text: str) -> Dict[str, Any]:
        """用正则从原始文本中提取基本个人信息，作为 fallback 的最低保障。"""
        info: Dict[str, Any] = {}

        # 手机号（支持 +86 前缀、空格/连字符分隔的11位号码）
        phone_match = re.search(
            r"(?:\+86[-\s]?)?(1[3-9]\d[-\s]?\d{4}[-\s]?\d{4})", text
        )
        if phone_match:
            info["phone"] = re.sub(r"[-\s]", "", phone_match.group())

        # 邮箱
        email_match = re.search(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text
        )
        if email_match:
            info["email"] = email_match.group()

        # GitHub URL
        github_match = re.search(
            r"github\.com/[\w\-]+(?:/[\w\-]+)?", text, re.IGNORECASE
        )
        if github_match:
            info["github"] = "https://" + github_match.group()

        # LinkedIn URL
        linkedin_match = re.search(r"linkedin\.com/in/[\w\-]+", text, re.IGNORECASE)
        if linkedin_match:
            info["linkedin"] = "https://" + linkedin_match.group()

        # 姓名：优先匹配"姓名：xxx"格式，捕获到行尾（去除结尾空白）
        name_labeled = re.search(
            r"(?:姓\s*名|name)\s*[：:]\s*(.+)", text, re.IGNORECASE
        )
        if name_labeled:
            info["name"] = name_labeled.group(1).strip()
        else:
            for line in text.splitlines():
                stripped = line.strip()
                # 取2-6个汉字，或2-20个字母的纯名字行
                if re.fullmatch(r"[\u4e00-\u9fff]{2,6}", stripped) or re.fullmatch(
                    r"[A-Za-z][a-zA-Z\s]{1,19}", stripped
                ):
                    # 排除明显的标题/关键词行
                    if stripped not in (
                        "个人简历",
                        "简历",
                        "Resume",
                        "CV",
                        "Curriculum Vitae",
                    ):
                        info["name"] = stripped
                        break

        # 求职意向
        position_match = re.search(
            r"(?:求职意向|应聘岗位|应聘职位|目标岗位|position)\s*[：:]\s*(.+)",
            text,
            re.IGNORECASE,
        )
        if position_match:
            info["position"] = position_match.group(1).strip()[:50]

        return info

    def _create_fallback_result(self, text: str) -> Dict[str, Any]:
        """创建备用结果（当AI解析失败时）：用正则提取尽可能多的基本信息。"""
        logger.debug("创建备用结果（含正则提取）")
        personal_info = self._extract_basic_info(text)

        return {
            "personal_info": personal_info,
            "education": [],
            "work_experience": [],
            "skills": [],
            "projects": [],
            "other_info": {},
            "raw_text": text,
            "parsing_quality": 0.0,
            "parsing_method": "fallback",
        }


# 保持向后兼容性
ResumeParser = AIResumeParser
