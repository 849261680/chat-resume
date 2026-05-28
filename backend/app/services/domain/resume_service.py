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
from app.models.resume import OptimizationRecord, Resume, ResumeChatMessage
from app.schemas.resume import (
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
            self.db.commit()
            self.db.refresh(resume)
        return resume

    def _serialize_content(self, content: ResumeContent | dict) -> dict:
        """统一将简历内容转换为稳定的 JSON 文档结构。"""
        return dump_resume_content_for_frontend(content)

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
