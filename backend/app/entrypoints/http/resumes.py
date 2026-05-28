"""
简历管理API端点模块

提供简历的创建、查询、更新、删除等RESTful API端点。
处理简历相关的所有HTTP请求和响应。
"""

import logging
from time import perf_counter
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user, get_current_user_claims
from app.infra.database import get_db
from app.schemas.resume import (
    JobPostCreate,
    JobPostResponse,
    LayoutConfigUpdate,
    ResumeCreate,
    ResumeListItem,
    ResumeResponse,
    ResumeUpdate,
    dump_resume_content_for_frontend,
    dump_resume_preview_content_for_list,
)
from app.services.domain import ResumeService

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_resume_response(resume) -> ResumeResponse:
    """用于把数据库简历对象转换成详情响应模型。"""
    return ResumeResponse.model_validate(
        {
            "id": resume.id,
            "title": resume.title,
            "content": dump_resume_content_for_frontend(resume.content or {}),
            "layout_config": resume.layout_config,
            "original_filename": resume.original_filename,
            "owner_id": resume.owner_id,
            "created_at": resume.created_at,
            "updated_at": resume.updated_at,
        }
    )


def _build_resume_list_item(resume) -> ResumeListItem:
    """用于把数据库简历对象转换成列表页摘要模型。"""
    content = resume.content if isinstance(resume.content, dict) else {}
    job_application = (
        content.get("job_application", {}) if isinstance(content, dict) else {}
    )
    return ResumeListItem.model_validate(
        {
            "id": resume.id,
            "title": resume.title,
            "original_filename": resume.original_filename,
            "owner_id": resume.owner_id,
            "created_at": resume.created_at,
            "updated_at": resume.updated_at,
            "target_company": str(job_application.get("target_company", "") or ""),
            "target_title": str(job_application.get("target_title", "") or ""),
            "layout_config": resume.layout_config,
            "preview_content": dump_resume_preview_content_for_list(content),
        }
    )


@router.get("/job-posts", response_model=list[JobPostResponse])
async def get_job_posts(
    query: str = "",
    limit: int = 20,
    current_user: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """用于返回当前用户保存过的 JD 列表。"""
    resume_service = ResumeService(db)
    return resume_service.list_job_posts_for_user(
        current_user["id"],
        query=query,
        limit=limit,
    )


@router.post("/job-posts", response_model=JobPostResponse)
async def create_job_post(
    payload: JobPostCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于手动保存一条可复用 JD。"""
    if not payload.jd_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JD text is required",
        )
    resume_service = ResumeService(db)
    return resume_service.create_job_post(payload, current_user["id"])


@router.get("/job-posts/{job_post_id}", response_model=JobPostResponse)
async def get_job_post(
    job_post_id: int,
    current_user: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """用于按用户权限返回单条 JD。"""
    resume_service = ResumeService(db)
    job_post = resume_service.get_job_post_for_user(current_user["id"], job_post_id)
    if job_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job post not found",
        )
    return job_post


@router.get("/", response_model=List[ResumeListItem])
async def get_resumes(
    current_user: dict = Depends(get_current_user_claims), db: Session = Depends(get_db)
):
    """用于返回当前用户拥有的全部简历列表。"""
    resume_service = ResumeService(db)
    resumes = resume_service.get_by_owner(current_user["id"])
    return [_build_resume_list_item(resume) for resume in resumes]


@router.post("/", response_model=ResumeResponse)
async def create_resume(
    resume_create: ResumeCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于为当前用户创建一份新简历。"""
    resume_service = ResumeService(db)
    resume = resume_service.create(resume_create, current_user["id"])
    return _build_resume_response(resume)


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: int,
    current_user: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """用于返回单份简历的完整内容。"""
    started_at = perf_counter()
    resume_service = ResumeService(db)
    query_started_at = perf_counter()
    resume = resume_service.get_by_id(resume_id)
    query_elapsed_ms = (perf_counter() - query_started_at) * 1000

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    validate_started_at = perf_counter()
    response = _build_resume_response(resume)
    validate_elapsed_ms = (perf_counter() - validate_started_at) * 1000
    total_elapsed_ms = (perf_counter() - started_at) * 1000
    logger.debug(
        (
            "get_resume timings resume_id=%s user_id=%s query_ms=%.2f "
            "validate_ms=%.2f total_ms=%.2f"
        ),
        resume_id,
        current_user["id"],
        query_elapsed_ms,
        validate_elapsed_ms,
        total_elapsed_ms,
    )
    return response


@router.put("/{resume_id}", response_model=ResumeResponse)
async def update_resume(
    resume_id: int,
    resume_update: ResumeUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于更新一份已有简历的内容或标题。"""
    resume_service = ResumeService(db)

    # 检查简历是否存在
    resume = resume_service.get_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    # 检查权限
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 只更新提供的字段
    update_data = resume_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided"
        )

    # 更新简历
    updated_resume = resume_service.update(resume_id, update_data)
    if not updated_resume:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update resume",
        )

    return _build_resume_response(updated_resume)


@router.put("/{resume_id}/layout", response_model=ResumeResponse)
async def update_resume_layout(
    resume_id: int,
    layout: LayoutConfigUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于保存简历布局配置，支撑前端排版编辑。"""
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    updated = resume_service.update(resume_id, {"layout_config": layout.model_dump()})
    return _build_resume_response(updated)


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于删除当前用户的一份简历。"""
    resume_service = ResumeService(db)

    # 检查简历是否存在
    resume = resume_service.get_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    # 检查权限
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 删除简历
    success = resume_service.delete(resume_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete resume",
        )

    return {"message": "Resume deleted successfully"}


# ── 聊天记录 ──────────────────────────────────────────────────────────────────


class ChatMessageIn(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    stream_events: list | None = None


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    stream_events: list | None = None

    model_config = {"from_attributes": True}


def _check_resume_access(
    resume_id: int,
    user_id: int,
    resume_service: ResumeService,
):
    """用于复用简历存在性和归属校验。"""
    resume = resume_service.get_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )
    if resume.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return resume


@router.get("/{resume_id}/chat-messages", response_model=List[ChatMessageOut])
async def get_chat_messages(
    resume_id: int,
    current_user: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """用于读取某份简历下保存的全部聊天记录。"""
    resume_service = ResumeService(db)
    _check_resume_access(resume_id, current_user["id"], resume_service)
    msgs = resume_service.list_chat_messages(resume_id)
    return [ChatMessageOut.model_validate(m) for m in msgs]


@router.post("/{resume_id}/chat-messages", response_model=List[ChatMessageOut])
async def append_chat_messages(
    resume_id: int,
    messages: List[ChatMessageIn],
    current_user: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """用于批量保存一次对话往返中的聊天记录。"""
    resume_service = ResumeService(db)
    _check_resume_access(resume_id, current_user["id"], resume_service)
    saved = resume_service.append_chat_messages(
        resume_id,
        [message.model_dump() for message in messages],
    )
    return [ChatMessageOut.model_validate(m) for m in saved]


@router.delete("/{resume_id}/chat-messages")
async def clear_chat_messages(
    resume_id: int,
    current_user: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """用于清空某份简历下的全部聊天记录。"""
    resume_service = ResumeService(db)
    _check_resume_access(resume_id, current_user["id"], resume_service)
    resume_service.clear_chat_messages(resume_id)
    return {"message": "cleared"}
