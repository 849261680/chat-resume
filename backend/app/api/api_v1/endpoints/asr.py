"""
ASR (自动语音识别) API端点
支持火山引擎端到端实时语音大模型
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import json
import asyncio
import logging
from app.core.database import get_db
from app.services.volcengine_bigmodel_asr_service import VolcEngineBigModelASRService
from app.api.deps import get_current_user
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

class ASRConfigRequest(BaseModel):
    """ASR配置请求"""
    language: Optional[str] = "zh-CN"
    sample_rate: Optional[int] = 16000
    format: Optional[str] = "pcm"
    continuous: Optional[bool] = True

class AudioDataRequest(BaseModel):
    """音频数据请求"""
    audio_data: str  # base64编码的音频数据
    format: Optional[str] = "pcm"
    sample_rate: Optional[int] = 16000

# 全局WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.asr_services: Dict[str, VolcEngineBigModelASRService] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.asr_services[client_id] = VolcEngineBigModelASRService()
        logger.info(f"Client {client_id} connected")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.asr_services:
            del self.asr_services[client_id]
        logger.info(f"Client {client_id} disconnected")
    
    async def send_message(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {str(e)}")
    
    def get_asr_service(self, client_id: str) -> Optional[VolcEngineBigModelASRService]:
        return self.asr_services.get(client_id)

manager = ConnectionManager()

@router.websocket("/realtime/{client_id}")
async def websocket_asr_endpoint(websocket: WebSocket, client_id: str):
    """
    实时语音识别WebSocket端点
    """
    await manager.connect(websocket, client_id)
    asr_service = manager.get_asr_service(client_id)
    
    if not asr_service:
        await websocket.close(code=1008, reason="ASR service initialization failed")
        return
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            
            if message_type == "start":
                # 开始语音识别会话
                try:
                    websocket_conn = await asr_service.create_websocket_connection()
                    await manager.send_message(client_id, {
                        "type": "session_created",
                        "success": True,
                        "session_id": client_id,
                        "message": "语音识别会话已创建"
                    })
                except Exception as e:
                    await manager.send_message(client_id, {
                        "type": "error",
                        "success": False,
                        "error": str(e)
                    })
            
            elif message_type == "audio":
                # 处理音频数据
                audio_base64 = message.get("audio_data")
                sequence = message.get("sequence", 1)
                
                if audio_base64:
                    try:
                        import base64
                        audio_data = base64.b64decode(audio_base64)
                        
                        # 简单识别处理
                        result = await asr_service.simple_recognition(audio_data)
                        
                        await manager.send_message(client_id, {
                            "type": "recognition_result",
                            "success": result.get("success", False),
                            "text": result.get("text", ""),
                            "is_final": True,
                            "sequence": sequence
                        })
                        
                    except Exception as e:
                        await manager.send_message(client_id, {
                            "type": "error",
                            "success": False,
                            "error": str(e),
                            "sequence": sequence
                        })
            
            elif message_type == "end":
                # 结束识别
                await manager.send_message(client_id, {
                    "type": "session_ended",
                    "success": True,
                    "message": "语音识别会话已结束"
                })
                break
                
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {str(e)}")
    finally:
        manager.disconnect(client_id)

@router.post("/config")
async def get_asr_config(
    request: ASRConfigRequest = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取ASR配置信息
    """
    try:
        asr_service = VolcEngineBigModelASRService()
        audio_format = asr_service.get_audio_format_info()
        service_info = asr_service.get_service_info()
        
        return {
            "success": True,
            "config": {
                "supported_languages": ["zh-CN", "en-US"],
                "audio_format": audio_format,
                "websocket_url": "/api/v1/asr/realtime/{client_id}",
                "max_duration": 300,  # 5分钟
                "streaming_support": True,
                "service_info": service_info
            },
            "message": "ASR配置获取成功"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取ASR配置失败: {str(e)}"
        )

@router.post("/recognize")
async def recognize_audio(
    request: AudioDataRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    一次性语音识别（非实时）
    """
    try:
        asr_service = VolcEngineBigModelASRService()
        
        # 解码音频数据
        import base64
        audio_data = base64.b64decode(request.audio_data)
        
        # 执行识别
        result = await asr_service.simple_recognition(audio_data)
        
        return {
            "success": result.get("success", False),
            "text": result.get("text", ""),
            "error": result.get("error"),
            "message": result.get("message", "语音识别完成")
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"语音识别失败: {str(e)}"
        )

@router.get("/status")
async def get_asr_status(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取ASR服务状态
    """
    try:
        asr_service = VolcEngineBigModelASRService()
        
        # 检查配置
        config_status = {
            "app_key_configured": bool(asr_service.app_key),
            "access_key_configured": bool(asr_service.access_key),
            "resource_id_configured": bool(asr_service.resource_id),
            "resource_id": asr_service.resource_id
        }
        
        return {
            "success": True,
            "status": "healthy" if all(config_status.values()) else "configuration_incomplete",
            "config": config_status,
            "active_connections": len(manager.active_connections),
            "service_info": asr_service.get_service_info(),
            "message": "ASR服务状态正常"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取ASR状态失败: {str(e)}"
        )

@router.post("/interview-recognition")
async def interview_recognition(
    request: AudioDataRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    面试专用语音识别
    针对面试场景优化的语音识别接口
    """
    try:
        asr_service = VolcEngineBigModelASRService()
        
        # 解码音频数据
        import base64
        audio_data = base64.b64decode(request.audio_data)
        
        # 面试场景优化配置
        interview_config = {
            "request": {
                "model_name": "bigmodel",
                "enable_itn": True,
                "enable_punc": True,
                "enable_ddc": True,  # 启用语义顺滑
                "show_utterances": True,
                "result_type": "full",
                "end_window_size": 500,  # 快速判停，提高实时性
                "force_to_speech_time": 800
            }
        }
        
        # 执行识别
        result = await asr_service.simple_recognition(audio_data, interview_config)
        
        if result.get("success"):
            # 面试回答后处理
            text = result.get("text", "").strip()
            utterances = result.get("utterances", [])
            
            # 基本的文本清理
            if text:
                # 去除多余空格和换行
                text = " ".join(text.split())
                
                # 添加标点符号（简单处理）
                if text and not text.endswith(('.', '!', '?', '。', '！', '？')):
                    text += "。"
            
            return {
                "success": True,
                "text": text,
                "original_text": result.get("text", ""),
                "utterances": utterances,
                "word_count": len(text.replace(" ", "")),
                "confidence": 0.95,  # 火山引擎大模型通常有较高的准确率
                "audio_info": result.get("audio_info", {}),
                "message": "面试语音识别完成"
            }
        else:
            return {
                "success": False,
                "text": "",
                "error": result.get("error"),
                "message": "面试语音识别失败"
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"面试语音识别失败: {str(e)}"
        )