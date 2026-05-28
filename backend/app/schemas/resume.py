"""
简历相关数据模式

为 AI 编辑提供更稳定的结构：
- 强类型文档 schema
- 数组项稳定 id
- item 级使用 summary
- 列表级使用 highlights
- 兼容旧版 description / achievements 数据
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _stable_id(prefix: str) -> str:
    """用于处理稳定标识。"""
    return f"{prefix}_{uuid4().hex[:12]}"


def _parse_json_if_needed(value: Any) -> Any:
    """用于解析JSONifneeded。"""
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return value
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                import json

                return json.loads(stripped)
            except Exception:
                return value
    return value


def _split_text_items(value: str) -> list[str]:
    """用于拆分文本条目。"""
    normalized = value.replace("；", "\n").replace("•", "\n").replace("·", "\n")
    parts = [item.strip(" -\n\t\r") for item in normalized.splitlines()]
    return [item for item in parts if item]


class ResumeBaseModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class ResumeLink(ResumeBaseModel):
    id: str = Field(default_factory=lambda: _stable_id("link"))
    label: str = ""
    url: str = ""


class ResumeHighlight(ResumeBaseModel):
    id: str = Field(default_factory=lambda: _stable_id("hl"))
    text: str = ""


class ResumeMeta(ResumeBaseModel):
    schema_version: str = "2.0"
    language: str = "zh-CN"
    target_role: str = ""


class JobApplication(ResumeBaseModel):
    job_post_id: Optional[int] = None
    target_title: str = ""
    target_company: str = ""
    jd_text: str = ""
    strategy: str = ""


class PersonalInfo(ResumeBaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    position: str = ""
    headline: str = ""
    location: str = ""
    github: str = ""
    linkedin: str = ""
    website: str = ""
    address: str = ""
    links: list[ResumeLink] = Field(default_factory=list)

    @model_validator(mode="after")
    def populate_links(self) -> "PersonalInfo":
        """用于填充链接。"""
        existing = {item.label.lower(): item for item in self.links}
        for label, url in (
            ("GitHub", self.github),
            ("LinkedIn", self.linkedin),
            ("Website", self.website),
        ):
            if url and label.lower() not in existing:
                self.links.append(ResumeLink(label=label, url=url))
        return self


class Summary(ResumeBaseModel):
    text: str = ""

    @model_validator(mode="before")
    @classmethod
    def from_string(cls, value: Any) -> Any:
        """用于从配置创建字符串。"""
        if isinstance(value, str):
            return {"text": value}
        return value


class EducationItem(ResumeBaseModel):
    id: str = Field(default_factory=lambda: _stable_id("edu"))
    school: str = ""
    major: str = ""
    degree: str = ""
    duration: str = ""
    start_date: str = ""
    end_date: str = ""
    location: str = ""
    gpa: str = ""
    description: str = ""
    highlights: list[ResumeHighlight] = Field(default_factory=list)

    @model_validator(mode="after")
    def migrate_description(self) -> "EducationItem":
        """用于迁移description。"""
        if self.description:
            lines = [
                line.strip("• ").strip()
                for line in self.description.splitlines()
                if line.strip()
            ]
            if lines and not self.highlights:
                self.highlights = [ResumeHighlight(text=line) for line in lines]
        # description 仅作为兼容输入保留，不再作为主存储字段输出
        self.description = ""
        return self


class WorkExperienceItem(ResumeBaseModel):
    id: str = Field(default_factory=lambda: _stable_id("work"))
    company: str = ""
    position: str = ""
    duration: str = ""
    start_date: str = ""
    end_date: str = ""
    is_current: bool = False
    location: str = ""
    employment_type: str = ""
    description: str = ""
    highlights: list[ResumeHighlight] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def migrate_description(self) -> "WorkExperienceItem":
        """用于迁移description。"""
        if self.description:
            lines = [
                line.strip("• ").strip()
                for line in self.description.splitlines()
                if line.strip()
            ]
            if lines and not self.highlights:
                self.highlights = [ResumeHighlight(text=line) for line in lines]
        # description 仅作为兼容输入保留，不再作为主存储字段输出
        self.description = ""
        return self


class SkillItem(ResumeBaseModel):
    id: str = Field(default_factory=lambda: _stable_id("skill"))
    category: str = ""
    items: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_shape(cls, value: Any) -> Any:
        """用于迁移legacy结构。"""
        if isinstance(value, dict):
            incoming_id = value.get("id") or _stable_id("skill")
            if "items" in value:
                items = value.get("items", [])
                if isinstance(items, list):
                    normalized_items = [
                        str(item).strip() for item in items if str(item).strip()
                    ]
                elif items:
                    normalized_items = [str(items).strip()]
                else:
                    normalized_items = []
                return {
                    "id": incoming_id,
                    "category": str(value.get("category", "")).strip(),
                    "items": normalized_items,
                }

            name = str(value.get("name", "")).strip()
            category = str(value.get("category", "其他")).strip() or "其他"
            if name:
                return {
                    "id": incoming_id,
                    "category": category,
                    "items": [name],
                }
        elif isinstance(value, str):
            text = value.strip()
            if text:
                return {"id": _stable_id("skill"), "category": "其他", "items": [text]}
        return value


class ProjectItem(ResumeBaseModel):
    id: str = Field(default_factory=lambda: _stable_id("proj"))
    name: str = ""
    description: str = ""
    summary: str = ""
    overview: str = ""
    technologies: list[str] = Field(default_factory=list)
    role: str = ""
    duration: str = ""
    start_date: str = ""
    end_date: str = ""
    github_url: str = ""
    demo_url: str = ""
    achievements: list[str] = Field(default_factory=list)
    highlights: list[ResumeHighlight] = Field(default_factory=list)
    links: list[ResumeLink] = Field(default_factory=list)

    @field_validator("technologies", mode="before")
    @classmethod
    def ensure_technologies(cls, value: Any) -> list[str]:
        """用于确保technologies。"""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return [str(value)]

    @field_validator("achievements", mode="before")
    @classmethod
    def ensure_achievements(cls, value: Any) -> list[str]:
        """用于确保achievements。"""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return [str(value)]

    @model_validator(mode="after")
    def migrate_fields(self) -> "ProjectItem":
        """用于迁移字段。"""
        if self.summary and not self.overview:
            self.overview = self.summary
        if self.description and not self.overview:
            self.overview = self.description
        if self.achievements and not self.highlights:
            self.highlights = [ResumeHighlight(text=item) for item in self.achievements]
        existing = {item.label.lower(): item for item in self.links}
        for label, url in (("GitHub", self.github_url), ("Demo", self.demo_url)):
            if url and label.lower() not in existing:
                self.links.append(ResumeLink(label=label, url=url))
        # description / achievements 仅作为兼容输入保留，不再作为主存储字段输出
        self.description = ""
        self.summary = ""
        self.achievements = []
        return self


class LanguageItem(ResumeBaseModel):
    id: str = Field(default_factory=lambda: _stable_id("lang"))
    name: str = ""
    level: str = ""


class CustomSection(ResumeBaseModel):
    id: str = Field(default_factory=lambda: _stable_id("section"))
    title: str = ""
    content: str = ""


class ResumeContent(ResumeBaseModel):
    meta: ResumeMeta = Field(default_factory=ResumeMeta)
    parsing_quality: Optional[float] = None
    parsing_method: Optional[str] = None
    job_application: JobApplication = Field(default_factory=JobApplication)
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: Summary = Field(default_factory=Summary)
    education: list[EducationItem] = Field(default_factory=list)
    work_experience: list[WorkExperienceItem] = Field(default_factory=list)
    skills: list[SkillItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    custom_sections: list[CustomSection] = Field(default_factory=list)

    @field_validator(
        "meta",
        "job_application",
        "personal_info",
        "summary",
        mode="before",
    )
    @classmethod
    def parse_object_json(cls, value: Any) -> Any:
        """用于解析对象JSON。"""
        parsed = _parse_json_if_needed(value)
        if parsed in (None, ""):
            return {}
        return parsed

    @field_validator(
        "education",
        "work_experience",
        "skills",
        "projects",
        "languages",
        "custom_sections",
        mode="before",
    )
    @classmethod
    def parse_list_json(cls, value: Any) -> Any:
        """用于解析列表JSON。"""
        parsed = _parse_json_if_needed(value)
        if parsed in (None, ""):
            return []
        return parsed

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value: Any) -> Any:
        """用于标准化技能。"""
        parsed = _parse_json_if_needed(value)
        if parsed in (None, ""):
            return []
        if isinstance(parsed, str):
            return [
                {"category": "其他", "items": [item]}
                for item in _split_text_items(parsed)
            ]
        if isinstance(parsed, list):
            grouped: dict[str, list[str]] = {}
            normalized: list[Any] = []
            has_legacy_shape = False
            for item in parsed:
                if isinstance(item, dict) and "items" in item:
                    normalized.append(item)
                    continue
                if isinstance(item, dict) and item.get("name"):
                    has_legacy_shape = True
                    category = str(item.get("category", "其他")).strip() or "其他"
                    grouped.setdefault(category, []).append(
                        str(item.get("name", "")).strip()
                    )
                    continue
                if isinstance(item, str) and item.strip():
                    has_legacy_shape = True
                    grouped.setdefault("其他", []).append(item.strip())
            if has_legacy_shape:
                normalized.extend(
                    {"category": category, "items": items}
                    for category, items in grouped.items()
                    if items
                )
                return normalized
        return parsed

    @field_validator("projects", mode="before")
    @classmethod
    def normalize_projects(cls, value: Any) -> Any:
        """用于标准化项目。"""
        parsed = _parse_json_if_needed(value)
        if parsed in (None, ""):
            return []
        if isinstance(parsed, str):
            text = parsed.strip()
            if not text:
                return []
            return [
                {
                    "name": "历史项目",
                    "summary": text,
                    "description": text,
                    "role": "",
                    "duration": "",
                    "highlights": [{"text": item} for item in _split_text_items(text)],
                }
            ]
        return parsed

    @field_validator("work_experience", mode="before")
    @classmethod
    def normalize_work_experience(cls, value: Any) -> Any:
        """用于标准化工作经历经历。"""
        parsed = _parse_json_if_needed(value)
        if parsed in (None, ""):
            return []
        if isinstance(parsed, str):
            text = parsed.strip()
            if not text:
                return []
            return [
                {
                    "company": "",
                    "position": "",
                    "duration": "",
                    "summary": text,
                    "description": text,
                    "highlights": [{"text": item} for item in _split_text_items(text)],
                }
            ]
        return parsed

    @field_validator("education", mode="before")
    @classmethod
    def normalize_education(cls, value: Any) -> Any:
        """用于标准化教育经历。"""
        parsed = _parse_json_if_needed(value)
        if parsed in (None, ""):
            return []
        if isinstance(parsed, str):
            text = parsed.strip()
            if not text:
                return []
            return [
                {
                    "school": text,
                    "major": "",
                    "degree": "",
                    "duration": "",
                    "description": text,
                }
            ]
        return parsed


_FRONTEND_RESUME_CONTENT_INCLUDE = {
    "parsing_quality": True,
    "parsing_method": True,
    "job_application": True,
    "personal_info": True,
    "summary": True,
    "education": True,
    "work_experience": True,
    "skills": True,
    "projects": True,
}

_RESUME_LIST_PREVIEW_INCLUDE = {
    "personal_info": True,
    "education": True,
    "work_experience": True,
    "skills": True,
    "projects": True,
}


def _prune_empty_frontend_value(value: Any) -> Any:
    """用于裁剪emptyfrontend值。"""
    if isinstance(value, dict):
        pruned = {key: _prune_empty_frontend_value(item) for key, item in value.items()}
        pruned = {
            key: item for key, item in pruned.items() if item not in (None, "", [], {})
        }
        return pruned

    if isinstance(value, list):
        pruned = [_prune_empty_frontend_value(item) for item in value]
        return [item for item in pruned if item not in (None, "", [], {})]

    return value


def dump_resume_content_for_frontend(
    content: "ResumeContent | dict[str, Any]",
) -> dict[str, Any]:
    """输出和前端编辑器/预览一致的简历结构，作为统一标准。"""
    normalized = (
        content
        if isinstance(content, ResumeContent)
        else ResumeContent.model_validate(content)
    )
    frontend_content = normalized.model_dump(
        mode="json",
        include=_FRONTEND_RESUME_CONTENT_INCLUDE,
    )
    return _prune_empty_frontend_value(frontend_content) or {}


def dump_resume_preview_content_for_list(
    content: "ResumeContent | dict[str, Any]",
) -> dict[str, Any]:
    """输出列表页卡片预览所需的最小内容，避免逐条详情请求。"""
    normalized = (
        content
        if isinstance(content, ResumeContent)
        else ResumeContent.model_validate(content)
    )
    preview_content = normalized.model_dump(
        mode="json",
        include=_RESUME_LIST_PREVIEW_INCLUDE,
    )
    return _prune_empty_frontend_value(preview_content) or {}


class ResumeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    content: ResumeContent
    layout_config: Optional[dict[str, Any]] = None
    original_filename: Optional[str] = None


class ResumeUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: Optional[str] = None
    content: Optional[ResumeContent] = None
    original_filename: Optional[str] = None


class LayoutConfigUpdate(BaseModel):
    density: str
    moduleOrder: list[str]
    visibleModules: list[str]
    spacingScale: float
    templateStyle: str = "classic"


class ResumeResponse(BaseModel):
    id: int
    title: str
    content: ResumeContent
    layout_config: Optional[dict[str, Any]] = None
    original_filename: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ResumeListItem(BaseModel):
    """列表页轻量响应。"""

    id: int
    title: str
    original_filename: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    target_company: str = ""
    target_title: str = ""
    layout_config: Optional[dict[str, Any]] = None
    preview_content: dict[str, Any] = Field(default_factory=dict)


class JobPostCreate(BaseModel):
    """用于创建可复用 JD 记录。"""

    company_name: str = ""
    job_title: str = ""
    jd_text: str
    source_url: Optional[str] = None
    source_type: str = "manual"


class JobPostResponse(BaseModel):
    """用于向前端或 Agent 返回单条 JD 记录。"""

    id: int
    user_id: int
    company_name: str = ""
    job_title: str = ""
    jd_text: str
    source_url: Optional[str] = None
    source_type: str = ""
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    model_config = ConfigDict(from_attributes=True)


class OptimizationRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    jd_content: str


class OptimizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resume_id: int
    jd_content: str
    suggestions: dict[str, Any]
    created_at: datetime
