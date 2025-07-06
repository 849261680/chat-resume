import os
import uuid
from typing import Dict, Any, Optional
from fastapi import UploadFile, HTTPException
import PyPDF2
import pdfplumber
from docx import Document
from app.core.config import settings

class FileService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        os.makedirs(self.upload_dir, exist_ok=True)
    
    async def save_uploaded_file(self, file: UploadFile) -> str:
        """保存上传的文件并返回文件路径"""
        if file.size > settings.MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        
        # 生成唯一文件名
        file_extension = os.path.splitext(file.filename)[1].lower()
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(self.upload_dir, unique_filename)
        
        # 保存文件
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        return file_path
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """从PDF提取文本"""
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text.strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to extract text from PDF: {str(e)}")
    
    def extract_text_from_docx(self, file_path: str) -> str:
        """从Word文档提取文本"""
        try:
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to extract text from DOCX: {str(e)}")
    
    def extract_text_from_txt(self, file_path: str) -> str:
        """从文本文件提取文本"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    return f.read().strip()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to read text file: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read text file: {str(e)}")
    
    def extract_text_from_file(self, file_path: str, filename: str) -> str:
        """根据文件类型提取文本"""
        file_extension = os.path.splitext(filename)[1].lower()
        
        if file_extension == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif file_extension in ['.docx', '.doc']:
            return self.extract_text_from_docx(file_path)
        elif file_extension in ['.txt', '.text']:
            return self.extract_text_from_txt(file_path)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_extension}")
    
    def delete_file(self, file_path: str) -> bool:
        """删除文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception:
            return False