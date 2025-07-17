#!/usr/bin/env python3
"""
TTS服务测试脚本
用于测试MiniMax TTS API集成
"""

import asyncio
import sys
import os
sys.path.append('.')

from app.services.minimax_tts_service import MiniMaxTTSService
from app.core.config import settings

async def test_tts_service():
    """测试TTS服务"""
    print("开始测试MiniMax TTS服务...")
    
    # 检查API密钥
    if not settings.MINIMAX_API_KEY:
        print("❌ 错误: MINIMAX_API_KEY 未配置")
        print("请在 .env 文件中设置 MINIMAX_API_KEY")
        return False
    
    tts_service = MiniMaxTTSService()
    
    # 测试文本转语音
    try:
        print("\n1. 测试文本转语音...")
        test_text = "您好，这是一个测试语音。请问您对这个职位有什么了解？"
        
        result = await tts_service.text_to_speech(
            text=test_text,
            voice_id="female-tianmei-jingpin",
            emotion="neutral"
        )
        
        print(f"✅ 文本转语音成功")
        print(f"   音频URL: {result.get('audio_url', 'N/A')}")
        print(f"   音频Base64: {'存在' if result.get('audio_base64') else '不存在'}")
        print(f"   时长: {result.get('duration', 'N/A')} 秒")
        
    except Exception as e:
        print(f"❌ 文本转语音失败: {e}")
        return False
    
    # 测试获取音色列表
    try:
        print("\n2. 测试获取音色列表...")
        voices = await tts_service.get_voice_list()
        print(f"✅ 获取音色列表成功，共 {len(voices.get('voices', []))} 个音色")
        
    except Exception as e:
        print(f"❌ 获取音色列表失败: {e}")
        return False
    
    # 测试面试官音色配置
    try:
        print("\n3. 测试面试官音色配置...")
        for interviewer_type in ["professional", "friendly", "strict"]:
            config = tts_service.get_interviewer_voice_config(interviewer_type)
            print(f"   {interviewer_type}: {config['description']} (音色: {config['voice_id']})")
        
        print("✅ 面试官音色配置正常")
        
    except Exception as e:
        print(f"❌ 面试官音色配置失败: {e}")
        return False
    
    print("\n🎉 所有测试通过！TTS服务配置正确")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_tts_service())
    sys.exit(0 if success else 1)