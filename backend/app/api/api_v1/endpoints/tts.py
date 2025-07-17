"""
TTS (Text-to-Speech) API端点
提供文本转语音和语音克隆功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.services.minimax_tts_service import MiniMaxTTSService
from app.api.deps import get_current_user
from pydantic import BaseModel
import tempfile
import os

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = "female-tianmei-jingpin"
    emotion: Optional[str] = "neutral"
    model: Optional[str] = "speech-02-turbo"
    format: Optional[str] = "mp3"
    sample_rate: Optional[int] = 32000

class VoiceCloneRequest(BaseModel):
    voice_name: str = "cloned_voice"

@router.post("/text-to-speech")
async def text_to_speech(
    request: TTSRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    文本转语音
    """
    try:
        tts_service = MiniMaxTTSService()
        
        result = await tts_service.text_to_speech(
            text=request.text,
            voice_id=request.voice_id,
            emotion=request.emotion,
            model=request.model,
            format=request.format,
            sample_rate=request.sample_rate
        )
        
        return {
            "success": True,
            "data": result,
            "message": "语音生成成功"
        }
        
    except Exception as e:
        # 如果是余额不足，返回503 Service Unavailable
        if "insufficient balance" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"TTS服务不可用: {str(e)}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"语音生成失败: {str(e)}"
            )

@router.post("/clone-voice")
async def clone_voice(
    request: VoiceCloneRequest,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    语音克隆
    """
    try:
        # 验证文件格式
        allowed_formats = ["mp3", "wav", "m4a"]
        file_extension = file.filename.split('.')[-1].lower()
        
        if file_extension not in allowed_formats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式。支持的格式: {', '.join(allowed_formats)}"
            )
        
        # 验证文件大小 (20MB)
        if file.size > 20 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件大小不能超过20MB"
            )
        
        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            tts_service = MiniMaxTTSService()
            
            result = await tts_service.clone_voice(
                audio_file_path=temp_file_path,
                voice_name=request.voice_name
            )
            
            return {
                "success": True,
                "data": result,
                "message": "语音克隆成功"
            }
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"语音克隆失败: {str(e)}"
        )

@router.get("/voices")
async def get_voice_list(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取可用的音色列表
    """
    try:
        tts_service = MiniMaxTTSService()
        
        voices = await tts_service.get_voice_list()
        
        return {
            "success": True,
            "data": voices,
            "message": "获取音色列表成功"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取音色列表失败: {str(e)}"
        )

@router.get("/interviewer-voices")
async def get_interviewer_voices(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取面试官音色配置
    """
    try:
        tts_service = MiniMaxTTSService()
        
        interviewer_types = ["professional", "friendly", "strict"]
        voices = {}
        
        for interviewer_type in interviewer_types:
            voices[interviewer_type] = tts_service.get_interviewer_voice_config(interviewer_type)
        
        return {
            "success": True,
            "data": voices,
            "message": "获取面试官音色配置成功"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取面试官音色配置失败: {str(e)}"
        )

@router.post("/interview-question-speech")
async def generate_interview_question_speech(
    request: TTSRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    为面试问题生成语音
    专门用于面试场景的TTS接口
    """
    try:
        tts_service = MiniMaxTTSService()
        
        # 为面试问题添加适当的停顿和语调
        formatted_text = f"<#0.5#>{request.text}<#1.0#>"
        
        result = await tts_service.text_to_speech(
            text=formatted_text,
            voice_id=request.voice_id or "female-tianmei-jingpin",
            emotion=request.emotion or "neutral",
            model=request.model or "speech-02-turbo",
            format=request.format or "mp3",
            sample_rate=request.sample_rate or 32000
        )
        
        return {
            "success": True,
            "data": result,
            "message": "面试问题语音生成成功"
        }
        
    except Exception as e:
        # 如果是余额不足，返回503 Service Unavailable
        if "insufficient balance" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"TTS服务不可用: {str(e)}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"面试问题语音生成失败: {str(e)}"
            )

@router.get("/health")
async def health_check():
    """
    TTS服务健康检查
    """
    try:
        tts_service = MiniMaxTTSService()
        health_status = await tts_service.health_check()
        
        # 根据健康状态返回不同的HTTP状态码
        if health_status["status"] == "healthy":
            return {
                "success": True,
                "data": health_status,
                "message": "TTS服务健康检查完成"
            }
        elif health_status["status"] == "error":
            # 如果是余额不足，返回503 Service Unavailable
            if health_status.get("error_type") == "insufficient_balance":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"TTS服务不可用: {health_status['message']}"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"TTS服务错误: {health_status['message']}"
                )
        else:
            return {
                "success": False,
                "data": health_status,
                "message": "TTS服务状态未知"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"健康检查失败: {str(e)}"
        )