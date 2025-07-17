"""
MiniMax TTS服务
提供文本转语音和语音克隆功能
"""

import httpx
import json
from typing import Dict, Any, Optional
from app.core.config import settings

class MiniMaxTTSService:
    """MiniMax文本转语音服务"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'MINIMAX_API_KEY', None)
        self.api_base = getattr(settings, 'MINIMAX_API_BASE', 'https://api.minimaxi.com')
        self.group_id = getattr(settings, 'MINIMAX_GROUP_ID', None)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def text_to_speech(
        self, 
        text: str, 
        voice_id: str = "female-tianmei-jingpin",
        emotion: str = "neutral",
        model: str = "speech-02-turbo",
        format: str = "mp3",
        sample_rate: int = 32000
    ) -> Dict[str, Any]:
        """
        文本转语音
        
        Args:
            text: 要转换的文本
            voice_id: 音色ID
            emotion: 情感 (happy, sad, angry, fearful, disgusted, surprised, neutral)
            model: 模型版本 (speech-02-hd, speech-02-turbo)
            format: 音频格式 (mp3, wav, flac, pcm)
            sample_rate: 采样率 (8000, 16000, 22050, 24000, 32000, 44100)
        
        Returns:
            包含音频URL或base64数据的字典
        """
        
        if not self.api_key:
            raise ValueError("MiniMax API密钥未配置")
        
        if not self.group_id:
            raise ValueError("MiniMax Group ID未配置")
        
        url = f"{self.api_base}/v1/t2a_pro?GroupId={self.group_id}"
        
        payload = {
            "text": text,
            "voice_id": voice_id,
            "model": model,
            "emotion": emotion,
            "format": format,
            "sample_rate": sample_rate,
            "bitrate": 128000,
            "channel": 1
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                
                result = response.json()
                
                # 检查API响应状态
                base_resp = result.get("base_resp", {})
                if base_resp.get("status_code") != 0:
                    status_msg = base_resp.get("status_msg", "未知错误")
                    if base_resp.get("status_code") == 1008:
                        raise Exception(f"MiniMax账户余额不足: {status_msg}")
                    else:
                        raise Exception(f"MiniMax API错误 ({base_resp.get('status_code')}): {status_msg}")
                
                # 安全地获取extra_info
                extra_info = result.get("extra_info") or {}
                
                return {
                    "audio_url": result.get("audio_file"),
                    "audio_base64": result.get("audio_data"),
                    "duration": extra_info.get("audio_length", 0) / 1000 if extra_info.get("audio_length") else 0,  # 转换为秒
                    "format": format,
                    "sample_rate": extra_info.get("audio_sample_rate", sample_rate)
                }
                
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            raise Exception(f"MiniMax TTS API错误: {e.response.status_code} - {error_detail}")
        except Exception as e:
            raise Exception(f"TTS服务调用失败: {str(e)}")
    
    async def clone_voice(self, audio_file_path: str, voice_name: str = "cloned_voice") -> Dict[str, Any]:
        """
        语音克隆
        
        Args:
            audio_file_path: 音频文件路径 (MP3, M4A, WAV, 10秒-5分钟, <20MB)
            voice_name: 克隆语音的名称
        
        Returns:
            包含voice_id的字典
        """
        
        if not self.api_key:
            raise ValueError("MiniMax API密钥未配置")
        
        if not self.group_id:
            raise ValueError("MiniMax Group ID未配置")
        
        # 1. 上传音频文件
        upload_url = f"{self.api_base}/v1/files/upload"
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # 上传文件
                with open(audio_file_path, 'rb') as f:
                    files = {"file": f}
                    upload_response = await client.post(
                        upload_url, 
                        files=files, 
                        headers={"Authorization": f"Bearer {self.api_key}"}
                    )
                    upload_response.raise_for_status()
                    
                    file_result = upload_response.json()
                    file_id = file_result.get("file_id")
                
                # 2. 克隆语音
                clone_url = f"{self.api_base}/v1/voice_clone"
                clone_payload = {
                    "file_id": file_id,
                    "voice_name": voice_name
                }
                
                clone_response = await client.post(
                    clone_url, 
                    json=clone_payload, 
                    headers=self.headers
                )
                clone_response.raise_for_status()
                
                clone_result = clone_response.json()
                
                # 检查API响应状态
                base_resp = clone_result.get("base_resp", {})
                if base_resp.get("status_code") != 0:
                    status_msg = base_resp.get("status_msg", "未知错误")
                    if base_resp.get("status_code") == 1008:
                        raise Exception(f"MiniMax账户余额不足: {status_msg}")
                    else:
                        raise Exception(f"MiniMax API错误 ({base_resp.get('status_code')}): {status_msg}")
                
                return {
                    "voice_id": clone_result.get("voice_id"),
                    "voice_name": voice_name,
                    "file_id": file_id
                }
                
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            raise Exception(f"语音克隆API错误: {e.response.status_code} - {error_detail}")
        except Exception as e:
            raise Exception(f"语音克隆失败: {str(e)}")
    
    async def get_voice_list(self) -> Dict[str, Any]:
        """
        获取可用的音色列表
        
        Returns:
            音色列表
        """
        
        if not self.api_key:
            raise ValueError("MiniMax API密钥未配置")
        
        if not self.group_id:
            raise ValueError("MiniMax Group ID未配置")
        
        url = f"{self.api_base}/v1/query/voice_list?GroupId={self.group_id}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                
                result = response.json()
                
                # 检查API响应状态
                base_resp = result.get("base_resp", {})
                if base_resp.get("status_code") != 0:
                    status_msg = base_resp.get("status_msg", "未知错误")
                    if base_resp.get("status_code") == 1008:
                        raise Exception(f"MiniMax账户余额不足: {status_msg}")
                    else:
                        raise Exception(f"MiniMax API错误 ({base_resp.get('status_code')}): {status_msg}")
                
                return result
                
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            raise Exception(f"获取音色列表API错误: {e.response.status_code} - {error_detail}")
        except Exception as e:
            raise Exception(f"获取音色列表失败: {str(e)}")
    
    def get_interviewer_voice_config(self, interviewer_type: str = "professional") -> Dict[str, str]:
        """
        获取面试官音色配置
        
        Args:
            interviewer_type: 面试官类型 (professional, friendly, strict)
        
        Returns:
            音色配置
        """
        
        voice_configs = {
            "professional": {
                "voice_id": "female-tianmei-jingpin",
                "emotion": "neutral",
                "description": "专业女性面试官"
            },
            "friendly": {
                "voice_id": "male-qinse-jingpin",
                "emotion": "happy",
                "description": "友好男性面试官"
            },
            "strict": {
                "voice_id": "female-zhuanye-jingpin",
                "emotion": "neutral",
                "description": "严格女性面试官"
            }
        }
        
        return voice_configs.get(interviewer_type, voice_configs["professional"])
    
    async def health_check(self) -> Dict[str, Any]:
        """
        TTS服务健康检查
        
        Returns:
            服务状态信息
        """
        health_status = {
            "service": "MiniMax TTS",
            "status": "unknown",
            "message": "",
            "config": {
                "api_key_configured": bool(self.api_key),
                "group_id_configured": bool(self.group_id),
                "api_base": self.api_base
            }
        }
        
        # 检查基本配置
        if not self.api_key:
            health_status["status"] = "error"
            health_status["message"] = "API密钥未配置"
            return health_status
        
        if not self.group_id:
            health_status["status"] = "error"
            health_status["message"] = "Group ID未配置"
            return health_status
        
        # 尝试调用API检查可用性
        try:
            # 使用最小的测试文本
            test_result = await self.text_to_speech(
                text="测试",
                voice_id="female-tianmei-jingpin",
                model="speech-02-turbo"
            )
            
            health_status["status"] = "healthy"
            health_status["message"] = "服务运行正常"
            health_status["test_result"] = {
                "audio_url_available": bool(test_result.get("audio_url")),
                "audio_base64_available": bool(test_result.get("audio_base64")),
                "duration": test_result.get("duration", 0)
            }
            
        except Exception as e:
            health_status["status"] = "error"
            health_status["message"] = str(e)
            
            # 解析具体错误类型
            if "insufficient balance" in str(e):
                health_status["error_type"] = "insufficient_balance"
            elif "API错误" in str(e):
                health_status["error_type"] = "api_error"
            elif "网络" in str(e) or "timeout" in str(e):
                health_status["error_type"] = "network_error"
            else:
                health_status["error_type"] = "unknown_error"
        
        return health_status