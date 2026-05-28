"""
简历业务逻辑服务模块

提供简历相关的核心业务逻辑，包括简历的创建、更新、查询、删除和聊天记录读写。
处理简历数据验证和业务规则。
"""

import logging
from typing import Any, List

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.interview import InterviewSession, InterviewTurn
from app.models.resume import JobPost, OptimizationRecord, Resume, ResumeChatMessage
from app.schemas.resume import (
    JobPostCreate,
    ResumeContent,
    ResumeCreate,
    dump_resume_content_for_frontend,
)
from app.state.models import AgentEvent, AgentSession

from .file_service import FileService

logger = logging.getLogger(__name__)


class ResumeService:
    """用于封装简历的增删改查和文件清理逻辑。"""

    def __init__(self, db: Session):
        """用于保存当前请求复用的数据库会话。"""
        self.db = db

    def get_by_id(self, resume_id: int) -> Resume | None:
        """用于按主键查询单个简历。"""
        return self.db.query(Resume).filter(Resume.id == resume_id).first()

    def get_by_owner(self, owner_id: int) -> List[Resume]:
        """用于查询某个用户拥有的全部简历。"""
        return self.db.query(Resume).filter(Resume.owner_id == owner_id).all()

    def create(self, resume_create: ResumeCreate, owner_id: int) -> Resume:
        """用于创建新的简历记录。"""
        resume = Resume(
            title=resume_create.title,
            content=self._serialize_content(resume_create.content),
            layout_config=resume_create.layout_config,
            original_filename=resume_create.original_filename,
            owner_id=owner_id,
        )

        try:
            self.db.add(resume)
            self.db.flush()
            self._sync_resume_job_post(resume)
            self.db.commit()
            self.db.refresh(resume)
            return resume
        except Exception as e:
            self.db.rollback()
            logger.error(f"简历创建失败: {str(e)}")
            raise e

    def update(self, resume_id: int, resume_update: dict) -> Resume:
        """用于更新单份简历并同步标记 JSON 字段脏状态。"""
        resume = self.get_by_id(resume_id)
        if resume is None:
            raise ValueError(f"Resume {resume_id} 不存在，无法更新")
        if resume:
            for key, value in resume_update.items():
                if key == "content":
                    value = self._serialize_content(value)
                setattr(resume, key, value)
                if key == "content":
                    flag_modified(resume, "content")
            if "content" in resume_update:
                self._sync_resume_job_post(resume)
            self.db.commit()
            self.db.refresh(resume)
        return resume

    def _serialize_content(self, content: ResumeContent | dict) -> dict:
        """统一将简历内容转换为稳定的 JSON 文档结构。"""
        return dump_resume_content_for_frontend(content)

    def create_job_post(self, payload: JobPostCreate, user_id: int) -> JobPost:
        """用于创建一条用户可复用的 JD 记录。"""
        job_post = JobPost(
            user_id=user_id,
            company_name=payload.company_name.strip(),
            job_title=payload.job_title.strip(),
            jd_text=payload.jd_text.strip(),
            source_url=payload.source_url,
            source_type=payload.source_type.strip() or "manual",
        )
        self.db.add(job_post)
        self.db.commit()
        self.db.refresh(job_post)
        return job_post

    def get_job_post_for_user(self, user_id: int, job_post_id: int) -> JobPost | None:
        """用于按用户权限读取单条 JD 记录。"""
        return (
            self.db.query(JobPost)
            .filter(JobPost.id == job_post_id, JobPost.user_id == user_id)
            .first()
        )

    def list_job_posts_for_user(
        self,
        user_id: int,
        *,
        query: str = "",
        limit: int = 20,
    ) -> list[JobPost]:
        """用于列出当前用户的 JD 记录，支持按公司/岗位/JD 文本粗筛。"""
        safe_limit = max(1, min(limit, 50))
        records = self.db.query(JobPost).filter(JobPost.user_id == user_id)
        normalized_query = query.strip()
        if normalized_query:
            pattern = f"%{normalized_query}%"
            records = records.filter(
                JobPost.company_name.ilike(pattern)
                | JobPost.job_title.ilike(pattern)
                | JobPost.jd_text.ilike(pattern)
            )
        return (
            records.order_by(JobPost.updated_at.desc(), JobPost.created_at.desc())
            .limit(safe_limit)
            .all()
        )

    def get_job_post_payload(self, user_id: int, job_post_id: int) -> dict[str, Any] | None:
        """用于返回适合 Agent 工具消费的单条 JD 字典。"""
        job_post = self.get_job_post_for_user(user_id, job_post_id)
        if job_post is None:
            return None
        return self._job_post_payload(job_post, include_text=True)

    def list_job_post_payloads(
        self,
        user_id: int,
        *,
        query: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """用于返回适合 Agent 工具消费的 JD 摘要列表。"""
        return [
            self._job_post_payload(job_post, include_text=False)
            for job_post in self.list_job_posts_for_user(
                user_id,
                query=query,
                limit=limit,
            )
        ]

    def _sync_resume_job_post(self, resume: Resume) -> None:
        """用于把简历内嵌 JD 同步成可复用 job_posts 记录。"""
        content = resume.content if isinstance(resume.content, dict) else {}
        job_application = content.get("job_application")
        if not isinstance(job_application, dict):
            return

        jd_text = str(job_application.get("jd_text") or "").strip()
        if not jd_text:
            return

        job_post = self._find_resume_job_post(
            user_id=resume.owner_id,
            job_post_id=self._coerce_int(job_application.get("job_post_id")),
        )
        if job_post is None:
            job_post = JobPost(user_id=resume.owner_id, jd_text=jd_text)
            self.db.add(job_post)

        job_post.company_name = str(job_application.get("target_company") or "").strip()
        job_post.job_title = str(job_application.get("target_title") or "").strip()
        job_post.jd_text = jd_text
        job_post.source_type = str(job_post.source_type or "resume")
        self.db.flush()

        job_application["job_post_id"] = job_post.id
        content["job_application"] = job_application
        resume.content = content
        flag_modified(resume, "content")

    def _find_resume_job_post(
        self,
        *,
        user_id: int,
        job_post_id: int | None,
    ) -> JobPost | None:
        """用于按 id 和用户归属寻找可复用 JD 记录。"""
        if job_post_id is None:
            return None
        return self.get_job_post_for_user(user_id, job_post_id)

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        """用于把 JSON 中的 id 值收窄成整数。"""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _job_post_payload(job_post: JobPost, *, include_text: bool) -> dict[str, Any]:
        """用于序列化 JD 记录，列表场景只返回短摘要。"""
        payload: dict[str, Any] = {
            "id": job_post.id,
            "company_name": job_post.company_name,
            "job_title": job_post.job_title,
            "source_url": job_post.source_url,
            "source_type": job_post.source_type,
            "created_at": job_post.created_at.isoformat() if job_post.created_at else None,
            "updated_at": job_post.updated_at.isoformat() if job_post.updated_at else None,
        }
        if include_text:
            payload["jd_text"] = job_post.jd_text
        else:
            payload["jd_preview"] = job_post.jd_text[:300]
            payload["jd_chars"] = len(job_post.jd_text)
        return payload

    def delete(self, resume_id: int) -> bool:
        """用于删除简历及其关联记录和上传文件。"""
        resume = self.get_by_id(resume_id)
        if not resume:
            return False

        try:
            agent_session_ids = [
                session_id
                for (session_id,) in self.db.query(AgentSession.id)
                .filter(AgentSession.resume_id == resume_id)
                .all()
            ]
            if agent_session_ids:
                self.db.query(AgentEvent).filter(
                    AgentEvent.session_id.in_(agent_session_ids)
                ).delete(synchronize_session=False)
                self.db.query(AgentSession).filter(
                    AgentSession.id.in_(agent_session_ids)
                ).delete(synchronize_session=False)

            interview_session_ids = [
                session_id
                for (session_id,) in self.db.query(InterviewSession.id)
                .filter(InterviewSession.resume_id == resume_id)
                .all()
            ]
            if interview_session_ids:
                self.db.query(InterviewTurn).filter(
                    InterviewTurn.session_id.in_(interview_session_ids)
                ).delete(synchronize_session=False)
                self.db.query(InterviewSession).filter(
                    InterviewSession.id.in_(interview_session_ids)
                ).delete(synchronize_session=False)

            self.db.query(ResumeChatMessage).filter(
                ResumeChatMessage.resume_id == resume_id
            ).delete(synchronize_session=False)
            self.db.query(OptimizationRecord).filter(
                OptimizationRecord.resume_id == resume_id
            ).delete(synchronize_session=False)

            if resume.file_path is not None:
                file_service = FileService()
                file_service.delete_file(str(resume.file_path))

            self.db.delete(resume)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            logger.exception("简历删除失败 resume_id=%s", resume_id)
            return False

    def list_chat_messages(self, resume_id: int) -> list[ResumeChatMessage]:
        """用于读取一份简历下的全部聊天记录。"""
        return (
            self.db.query(ResumeChatMessage)
            .filter(ResumeChatMessage.resume_id == resume_id)
            .order_by(ResumeChatMessage.id.asc())
            .all()
        )

    def append_chat_messages(
        self,
        resume_id: int,
        messages: list[dict[str, Any]],
    ) -> list[ResumeChatMessage]:
        """用于批量追加一次往返中的聊天记录。"""
        saved: list[ResumeChatMessage] = []
        for message in messages:
            role = str(message.get("role") or "")
            if role not in {"user", "assistant"}:
                continue
            row = ResumeChatMessage(
                resume_id=resume_id,
                role=role,
                content=str(message.get("content") or ""),
                stream_events=message.get("stream_events"),
            )
            self.db.add(row)
            saved.append(row)
        self.db.commit()
        for row in saved:
            self.db.refresh(row)
        return saved

    def clear_chat_messages(self, resume_id: int) -> None:
        """用于清空一份简历下的全部聊天记录。"""
        self.db.query(ResumeChatMessage).filter(
            ResumeChatMessage.resume_id == resume_id
        ).delete()
        self.db.commit()
