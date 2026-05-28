"""
用户数据模型

定义用户相关的数据库表结构，包括用户基本信息和认证信息。
使用SQLAlchemy ORM映射到数据库表。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infra.database import Base

if TYPE_CHECKING:
    from app.models.resume import JobPost, Resume


class ProviderIdentity(Base):
    """用于保存第三方登录提供方与本地用户的绑定关系。"""

    __tablename__ = "provider_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_provider_identities_provider_user_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider_user_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider_email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="provider_identities")


class User(Base):
    """用于保存用户基础信息和认证状态。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    resumes: Mapped[list["Resume"]] = relationship("Resume", back_populates="owner")
    job_posts: Mapped[list["JobPost"]] = relationship(
        "JobPost",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    provider_identities: Mapped[list["ProviderIdentity"]] = relationship(
        "ProviderIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def has_password(self) -> bool:
        """用于告诉前端当前账号是否支持邮箱密码登录。"""
        return bool(self.hashed_password)


class PasswordResetToken(Base):
    """用于保存一次性密码重置令牌的服务端摘要。"""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User")
