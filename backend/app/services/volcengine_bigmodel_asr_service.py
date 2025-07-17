"""
火山引擎大模型流式语音识别服务
基于官方WebSocket二进制协议实现
"""

import asyncio
import json
import struct
import gzip
import uuid
import websockets
import logging
from typing import Dict, Any, Optional, Callable, AsyncGenerator
from app.core.config import settings

logger = logging.getLogger(__name__)

class VolcEngineBigModelASRService:
    """火山引擎大模型流式语音识别服务"""
    
    def __init__(self):
        self.app_key = getattr(settings, 'VOLCENGINE_APP_KEY', None)
        self.access_token = getattr(settings, 'VOLCENGINE_ACCESS_TOKEN', None)
        self.resource_id = getattr(settings, 'VOLCENGINE_ASR_RESOURCE_ID', 'volc.bigasr.sauc.duration')
        
        # API端点
        self.endpoints = {
            'bidirectional': 'wss://openspeech.bytedance.com/api/v3/sauc/bigmodel',
            'streaming_input': 'wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream',
            'optimized': 'wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async'
        }
        
        # 默认使用双向流式模式
        self.current_endpoint = self.endpoints['bidirectional']
        
        # 协议常量
        self.PROTOCOL_VERSION = 0b0001
        self.HEADER_SIZE = 0b0001
        
        # 消息类型
        self.MSG_TYPE_FULL_CLIENT_REQUEST = 0b0001
        self.MSG_TYPE_AUDIO_ONLY_REQUEST = 0b0010
        self.MSG_TYPE_FULL_SERVER_RESPONSE = 0b1001
        self.MSG_TYPE_ERROR = 0b1111
        
        # 消息标志
        self.MSG_FLAG_NONE = 0b0000
        self.MSG_FLAG_SEQUENCE_POSITIVE = 0b0001
        self.MSG_FLAG_LAST_PACKET = 0b0010
        self.MSG_FLAG_SEQUENCE_NEGATIVE = 0b0011
        
        # 序列化方式
        self.SERIALIZATION_NONE = 0b0000
        self.SERIALIZATION_JSON = 0b0001
        
        # 压缩方式
        self.COMPRESSION_NONE = 0b0000
        self.COMPRESSION_GZIP = 0b0001
    
    def _create_header(self, message_type: int, message_flags: int, 
                       serialization: int, compression: int) -> bytes:
        """创建4字节协议头部"""
        # 第一个字节: protocol_version(4bits) + header_size(4bits)
        byte1 = (self.PROTOCOL_VERSION << 4) | self.HEADER_SIZE
        
        # 第二个字节: message_type(4bits) + message_flags(4bits)
        byte2 = (message_type << 4) | message_flags
        
        # 第三个字节: serialization(4bits) + compression(4bits)
        byte3 = (serialization << 4) | compression
        
        # 第四个字节: 保留字段
        byte4 = 0x00
        
        return struct.pack('>BBBB', byte1, byte2, byte3, byte4)
    
    def _parse_header(self, header_bytes: bytes) -> Dict[str, int]:
        """解析4字节协议头部"""
        byte1, byte2, byte3, byte4 = struct.unpack('>BBBB', header_bytes)
        
        return {
            'protocol_version': (byte1 >> 4) & 0x0F,
            'header_size': byte1 & 0x0F,
            'message_type': (byte2 >> 4) & 0x0F,
            'message_flags': byte2 & 0x0F,
            'serialization': (byte3 >> 4) & 0x0F,
            'compression': byte3 & 0x0F,
            'reserved': byte4
        }
    
    def _create_message(self, message_type: int, message_flags: int,
                        serialization: int, compression: int,
                        payload: bytes, sequence: Optional[int] = None) -> bytes:
        """创建完整的消息"""
        # 创建头部
        header = self._create_header(message_type, message_flags, serialization, compression)
        
        # 压缩payload
        if compression == self.COMPRESSION_GZIP:
            payload = gzip.compress(payload)
        
        # 创建消息
        message = header
        
        # 添加序列号（如果需要）
        if sequence is not None:
            # 使用有符号整数格式来支持负序列号
            message += struct.pack('>i', sequence)
        
        # 添加payload大小和payload
        message += struct.pack('>I', len(payload))
        message += payload
        
        return message
    
    async def _read_message(self, websocket) -> Dict[str, Any]:
        """读取并解析消息"""
        try:
            # 读取完整的WebSocket消息
            message_data = await websocket.recv()
            
            if len(message_data) < 4:
                raise Exception("消息头部不完整")
            
            # 解析头部
            header = self._parse_header(message_data[:4])
            offset = 4
            
            # 读取序列号（如果存在）
            sequence = None
            if header['message_flags'] in [self.MSG_FLAG_SEQUENCE_POSITIVE, self.MSG_FLAG_SEQUENCE_NEGATIVE]:
                if len(message_data) < offset + 4:
                    raise Exception("序列号不完整")
                # 使用有符号整数格式来支持负序列号
                sequence = struct.unpack('>i', message_data[offset:offset+4])[0]
                offset += 4
            
            # 读取payload大小
            if len(message_data) < offset + 4:
                raise Exception("Payload大小不完整")
            payload_size = struct.unpack('>I', message_data[offset:offset+4])[0]
            offset += 4
            
            # 读取payload
            if len(message_data) < offset + payload_size:
                raise Exception("Payload数据不完整")
            payload = message_data[offset:offset+payload_size]
            
            # 解压缩payload
            if header['compression'] == self.COMPRESSION_GZIP:
                payload = gzip.decompress(payload)
            
            # 解析payload
            parsed_payload = None
            if header['serialization'] == self.SERIALIZATION_JSON:
                parsed_payload = json.loads(payload.decode('utf-8'))
            
            return {
                'header': header,
                'sequence': sequence,
                'payload': parsed_payload,
                'raw_payload': payload
            }
            
        except Exception as e:
            logger.error(f"读取消息失败: {str(e)}")
            raise
    
    def _create_full_client_request(self, config: Dict[str, Any]) -> bytes:
        """创建full client request"""
        # 默认配置
        default_config = {
            "user": {
                "uid": str(uuid.uuid4()),
                "platform": "Linux",
                "sdk_version": "1.0.0",
                "app_version": "1.0.0"
            },
            "audio": {
                "format": "pcm",
                "codec": "raw",
                "rate": 16000,
                "bits": 16,
                "channel": 1
            },
            "request": {
                "model_name": "bigmodel",
                "enable_itn": True,
                "enable_punc": True,
                "enable_ddc": False,
                "show_utterances": True,
                "result_type": "full",
                "vad_segment_duration": 3000,
                "end_window_size": 800,
                "force_to_speech_time": 1000
            }
        }
        
        # 合并配置
        merged_config = {**default_config, **config}
        
        # 序列化为JSON
        json_data = json.dumps(merged_config, ensure_ascii=False).encode('utf-8')
        
        # 创建消息
        return self._create_message(
            message_type=self.MSG_TYPE_FULL_CLIENT_REQUEST,
            message_flags=self.MSG_FLAG_NONE,
            serialization=self.SERIALIZATION_JSON,
            compression=self.COMPRESSION_GZIP,
            payload=json_data
        )
    
    def _create_audio_request(self, audio_data: bytes, sequence: int, 
                             is_last: bool = False) -> bytes:
        """创建audio only request"""
        if is_last:
            # 对于最后一个音频包，使用负序列号和negative标志
            message_flags = self.MSG_FLAG_SEQUENCE_NEGATIVE
            actual_sequence = -sequence if sequence > 0 else sequence
        else:
            # 对于中间的音频包，使用正序列号和positive标志
            message_flags = self.MSG_FLAG_SEQUENCE_POSITIVE
            actual_sequence = sequence
        
        return self._create_message(
            message_type=self.MSG_TYPE_AUDIO_ONLY_REQUEST,
            message_flags=message_flags,
            serialization=self.SERIALIZATION_NONE,
            compression=self.COMPRESSION_GZIP,
            payload=audio_data,
            sequence=actual_sequence
        )
    
    async def create_websocket_connection(self, mode: str = 'bidirectional') -> websockets.WebSocketServerProtocol:
        """创建WebSocket连接"""
        if not all([self.app_key, self.access_token]):
            raise ValueError("火山引擎配置不完整，请检查 VOLCENGINE_APP_KEY、VOLCENGINE_ACCESS_TOKEN 环境变量")
        
        # 选择端点
        if mode not in self.endpoints:
            mode = 'bidirectional'
        
        endpoint = self.endpoints[mode]
        connect_id = str(uuid.uuid4())
        
        # 设置请求头
        headers = {
            'X-Api-App-Key': str(self.app_key),
            'X-Api-Access-Key': str(self.access_token),
            'X-Api-Resource-Id': self.resource_id,
            'X-Api-Connect-Id': connect_id
        }
        
        logger.info(f"正在连接火山引擎WebSocket: {endpoint}")
        
        try:
            websocket = await asyncio.wait_for(
                websockets.connect(endpoint, additional_headers=headers),
                timeout=10.0
            )
            
            logger.info(f"WebSocket连接成功, Connect-ID: {connect_id}")
            return websocket
            
        except asyncio.TimeoutError:
            raise Exception("连接火山引擎WebSocket超时，请检查网络连接")
        except Exception as e:
            raise Exception(f"连接火山引擎WebSocket失败: {str(e)}")
    
    async def simple_recognition(self, audio_data: bytes, 
                                config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """简单的一次性语音识别"""
        try:
            # 检查配置
            if not all([self.app_key, self.access_token]):
                return {
                    "success": False,
                    "error": "火山引擎配置不完整，请检查环境变量配置",
                    "message": "语音识别失败：配置不完整"
                }
            
            # 检查音频数据
            if not audio_data or len(audio_data) == 0:
                return {
                    "success": False,
                    "error": "音频数据为空",
                    "message": "语音识别失败：无音频数据"
                }
            
            # 创建WebSocket连接
            websocket = await self.create_websocket_connection('streaming_input')
            
            try:
                # 发送配置请求
                full_request = self._create_full_client_request(config or {})
                await websocket.send(full_request)
                
                # 读取配置响应
                response = await self._read_message(websocket)
                if response['header']['message_type'] == self.MSG_TYPE_ERROR:
                    error_msg = response['payload'].get('message', '配置请求失败')
                    return {
                        "success": False,
                        "error": error_msg,
                        "message": "语音识别失败：配置错误"
                    }
                
                # 发送音频数据（标记为最后一包）
                audio_request = self._create_audio_request(audio_data, 2, is_last=True)
                await websocket.send(audio_request)
                
                # 读取识别结果
                result_response = await self._read_message(websocket)
                
                if result_response['header']['message_type'] == self.MSG_TYPE_FULL_SERVER_RESPONSE:
                    payload = result_response['payload']
                    
                    if payload and 'result' in payload:
                        text = payload['result'].get('text', '')
                        utterances = payload['result'].get('utterances', [])
                        
                        return {
                            "success": True,
                            "text": text,
                            "utterances": utterances,
                            "audio_info": payload.get('audio_info', {}),
                            "message": "语音识别完成"
                        }
                    else:
                        return {
                            "success": False,
                            "error": "识别结果为空",
                            "message": "语音识别失败：无识别结果"
                        }
                else:
                    return {
                        "success": False,
                        "error": "接收到未知消息类型",
                        "message": "语音识别失败：协议错误"
                    }
                
            finally:
                await websocket.close()
                
        except Exception as e:
            logger.error(f"简单语音识别失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "语音识别失败"
            }
    
    async def streaming_recognition(self, audio_chunks: AsyncGenerator[bytes, None],
                                   config: Optional[Dict[str, Any]] = None,
                                   on_partial_result: Optional[Callable[[str], None]] = None,
                                   on_final_result: Optional[Callable[[Dict[str, Any]], None]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """流式语音识别"""
        try:
            # 创建WebSocket连接
            websocket = await self.create_websocket_connection('bidirectional')
            
            try:
                # 发送配置请求
                full_request = self._create_full_client_request(config or {})
                await websocket.send(full_request)
                
                # 读取配置响应
                response = await self._read_message(websocket)
                if response['header']['message_type'] == self.MSG_TYPE_ERROR:
                    error_msg = response['payload'].get('message', '配置请求失败')
                    yield {
                        "success": False,
                        "error": error_msg,
                        "message": "流式语音识别失败：配置错误"
                    }
                    return
                
                # 处理音频流
                sequence = 1
                async for audio_chunk in audio_chunks:
                    if audio_chunk:
                        # 发送音频数据
                        audio_request = self._create_audio_request(audio_chunk, sequence)
                        await websocket.send(audio_request)
                        sequence += 1
                        
                        # 尝试读取响应
                        try:
                            result_response = await asyncio.wait_for(
                                self._read_message(websocket), 
                                timeout=0.1
                            )
                            
                            if result_response['header']['message_type'] == self.MSG_TYPE_FULL_SERVER_RESPONSE:
                                payload = result_response['payload']
                                
                                if payload and 'result' in payload:
                                    text = payload['result'].get('text', '')
                                    utterances = payload['result'].get('utterances', [])
                                    
                                    # 检查是否有确定的分句
                                    has_definite = any(u.get('definite', False) for u in utterances)
                                    
                                    result = {
                                        "success": True,
                                        "text": text,
                                        "utterances": utterances,
                                        "is_final": has_definite,
                                        "sequence": sequence
                                    }
                                    
                                    # 调用回调
                                    if has_definite and on_final_result:
                                        on_final_result(result)
                                    elif not has_definite and on_partial_result:
                                        on_partial_result(text)
                                    
                                    yield result
                                    
                        except asyncio.TimeoutError:
                            # 没有响应，继续处理下一个音频块
                            continue
                
                # 发送结束标记
                final_request = self._create_audio_request(b'', sequence, is_last=True)
                await websocket.send(final_request)
                
                # 读取最终结果
                final_response = await self._read_message(websocket)
                if final_response['header']['message_type'] == self.MSG_TYPE_FULL_SERVER_RESPONSE:
                    payload = final_response['payload']
                    
                    if payload and 'result' in payload:
                        result = {
                            "success": True,
                            "text": payload['result'].get('text', ''),
                            "utterances": payload['result'].get('utterances', []),
                            "is_final": True,
                            "audio_info": payload.get('audio_info', {}),
                            "sequence": sequence
                        }
                        
                        if on_final_result:
                            on_final_result(result)
                        
                        yield result
                
            finally:
                await websocket.close()
                
        except Exception as e:
            logger.error(f"流式语音识别失败: {str(e)}")
            yield {
                "success": False,
                "error": str(e),
                "message": "流式语音识别失败"
            }
    
    def get_audio_format_info(self) -> Dict[str, Any]:
        """获取音频格式要求信息"""
        return {
            "format": "PCM/WAV/OGG",
            "codec": "raw/opus",
            "sample_rate": 16000,
            "channels": 1,
            "bit_depth": 16,
            "byte_order": "big-endian",
            "encoding": "signed",
            "chunk_size_ms": "100-200",
            "supported_formats": ["pcm", "wav", "ogg"]
        }
    
    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "service_name": "火山引擎大模型流式语音识别",
            "version": "v3",
            "endpoints": self.endpoints,
            "current_endpoint": self.current_endpoint,
            "supported_modes": ["bidirectional", "streaming_input", "optimized"],
            "features": [
                "实时流式识别",
                "双向流式通信",
                "语义分句",
                "标点符号",
                "文本规范化",
                "敏感词过滤",
                "热词支持"
            ]
        }