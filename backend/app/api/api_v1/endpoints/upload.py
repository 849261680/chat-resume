from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.file_service import FileService
from app.services.resume_parser import ResumeParser
from app.services.resume_service import ResumeService
from app.schemas.resume import ResumeResponse, ResumeCreate
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/resume", response_model=ResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传简历文件并解析"""
    
    # 验证文件类型
    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
    file_extension = file.filename.split('.')[-1].lower()
    if f'.{file_extension}' not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload PDF, DOCX, DOC, or TXT files."
        )
    
    try:
        # 保存文件
        file_service = FileService()
        file_path = await file_service.save_uploaded_file(file)
        
        # 提取文本
        text = file_service.extract_text_from_file(file_path, file.filename)
        
        # 解析简历
        parser = ResumeParser()
        resume_data = await parser.parse_resume_text_async(text)
        
        # 保存到数据库
        resume_service = ResumeService(db)
        resume_create = ResumeCreate(
            title=file.filename.split('.')[0],
            content=resume_data,
            original_filename=file.filename
        )
        resume = resume_service.create(resume_create, current_user["id"])
        
        # 清理临时文件
        file_service.delete_file(file_path)
        
        return ResumeResponse.from_orm(resume)
        
    except Exception as e:
        # 清理临时文件
        if 'file_path' in locals():
            file_service.delete_file(file_path)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resume: {str(e)}"
        )