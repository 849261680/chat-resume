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
        print(f"[UPLOAD] 提取文本长度: {len(text)}")
        print(f"[UPLOAD] 文本前500字符: {text[:500]}")
        
        # 解析简历
        parser = ResumeParser()
        print(f"[UPLOAD] 开始AI解析...")
        resume_data = await parser.parse_resume_text_async(text)
        print(f"[UPLOAD] AI解析完成，数据: {resume_data}")
        print(f"[UPLOAD] 解析质量分: {resume_data.get('parsing_quality', 0)}")
        print(f"[UPLOAD] 解析方法: {resume_data.get('parsing_method', 'unknown')}")
        
        # 保存到数据库
        resume_service = ResumeService(db)
        resume_create = ResumeCreate(
            title=file.filename.split('.')[0],
            content=resume_data,
            original_filename=file.filename
        )
        print(f"[UPLOAD] 开始保存简历到数据库...")
        resume = resume_service.create(resume_create, current_user["id"])
        print(f"[UPLOAD] 简历保存成功，ID: {resume.id}")
        
        # 清理临时文件
        file_service.delete_file(file_path)
        
        return ResumeResponse.model_validate(resume)
        
    except Exception as e:
        # 清理临时文件
        if 'file_path' in locals():
            file_service.delete_file(file_path)
        
        # 记录详细错误信息
        print(f"[ERROR] 简历上传处理失败: {str(e)}")
        print(f"[ERROR] 错误类型: {type(e).__name__}")
        
        # 根据错误类型返回不同的错误信息
        if "数据库" in str(e) or "database" in str(e).lower():
            detail = "数据库保存失败，请稍后重试"
        elif "解析" in str(e) or "parsing" in str(e).lower():
            detail = "简历解析失败，请检查文件格式"
        else:
            detail = f"简历处理失败: {str(e)}"
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )