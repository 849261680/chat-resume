import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.export_service import ExportService
from app.services.resume_service import ResumeService
from app.schemas.export import ExportRequest, ExportResponse
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/{resume_id}/export", response_model=ExportResponse)
async def export_resume(
    resume_id: int,
    export_request: ExportRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """导出简历"""
    
    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)
    
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        export_service = ExportService()
        
        # 根据格式导出
        if export_request.format == "pdf":
            filepath = export_service.export_to_pdf(resume.content, export_request.template)
        elif export_request.format == "docx":
            filepath = export_service.export_to_docx(resume.content, export_request.template)
        elif export_request.format == "html":
            filepath = export_service.export_to_html(resume.content, export_request.template)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported export format"
            )
        
        # 获取文件URL
        download_url = export_service.get_file_url(filepath)
        filename = os.path.basename(filepath)
        
        return ExportResponse(
            download_url=download_url,
            filename=filename,
            format=export_request.format
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export resume: {str(e)}"
        )

@router.get("/download/{filename}")
async def download_file(filename: str):
    """下载导出的文件"""
    
    export_service = ExportService()
    filepath = os.path.join(export_service.export_dir, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # 获取文件扩展名来设置media_type
    file_extension = os.path.splitext(filename)[1].lower()
    media_type_map = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.html': 'text/html'
    }
    
    media_type = media_type_map.get(file_extension, 'application/octet-stream')
    
    return FileResponse(
        path=filepath,
        media_type=media_type,
        filename=filename
    )