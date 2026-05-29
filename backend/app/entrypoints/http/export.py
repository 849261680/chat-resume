"""用于提供简历导出和下载入口。"""

import os
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user
from app.infra.database import get_db
from app.infra.security import verify_download_token
from app.schemas.export import ExportRequest, ExportResponse
from app.services.domain import ResumeService
from app.services.processing import ExportService

router = APIRouter()


@router.post("/{resume_id}/export", response_model=ExportResponse)
async def export_resume(
    resume_id: int,
    export_request: ExportRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于把指定简历导出成目标格式文件。"""

    # 验证简历权限
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

    try:
        export_service = ExportService()

        # 根据格式导出
        resume_data: Dict[str, Any] = cast(
            Dict[str, Any], resume.content if resume.content is not None else {}
        )
        template_name: str = export_request.template or "default"
        layout_config: Dict[str, Any] | None = export_request.layout_config
        if layout_config is None and resume.layout_config is not None:
            layout_config = cast(Dict[str, Any], resume.layout_config)

        if export_request.format == "pdf":
            filepath = await export_service.export_to_pdf(
                resume_data,
                template_name,
                layout_config,
            )
        elif export_request.format == "docx":
            filepath = export_service.export_to_docx(resume_data, template_name)
        elif export_request.format == "html":
            filepath = export_service.export_to_html(resume_data, template_name)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported export format",
            )

        # 获取文件URL
        download_url = export_service.get_file_url(
            filepath=filepath,
            user_id=current_user["id"],
        )
        filename = os.path.basename(filepath)

        return ExportResponse.model_validate(
            {
                "download_url": download_url,
                "filename": filename,
                "format": export_request.format,
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export resume: {str(e)}",
        )


@router.get("/download/{filename}")
async def download_file(
    filename: str,
    expires: int = Query(...),
    user_id: int = Query(...),
    signature: str = Query(..., min_length=64, max_length=64),
):
    """用于校验签名后返回导出的文件内容。"""

    if not verify_download_token(
        filename=filename,
        user_id=user_id,
        expires=expires,
        signature=signature,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid download token"
        )

    export_service = ExportService()
    filepath = os.path.join(export_service.export_dir, filename)

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    # 获取文件扩展名来设置media_type
    file_extension = os.path.splitext(filename)[1].lower()
    media_type_map = {
        ".pdf": "application/pdf",
        ".docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        ".html": "text/html",
    }

    media_type = media_type_map.get(file_extension, "application/octet-stream")

    return FileResponse(path=filepath, media_type=media_type, filename=filename)
