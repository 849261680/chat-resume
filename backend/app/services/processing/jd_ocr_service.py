"""用于通过视觉模型把 JD 图片识别成纯文本。"""

from __future__ import annotations

import base64
import logging
import re

from app.infra.config import settings
from app.services.llm import ChatService

logger = logging.getLogger(__name__)


class JDOcrService:
    """用于封装 JD 图片 OCR 的视觉模型调用。"""

    async def extract_text_from_image(self, image_bytes: bytes, mime_type: str) -> str:
        """用于把单张 JD 图片识别成尽量原样的纯文本。"""
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{image_base64}"
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "请对这张图片做 OCR，只提取图片里可见的文字。"
                            "要求："
                            "1. 不要总结，不要改写，不要补充解释；"
                            "2. 尽量保留原有段落和换行；"
                            "3. 如果图片里没有可识别文字，返回空字符串。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            }
        ]

        last_error: Exception | None = None
        for model in self._candidate_models():
            try:
                async with self._openrouter_chat_service(model) as chat_service:
                    response = await chat_service.chat_completion(
                        messages=messages,
                        temperature=0,
                        max_tokens=4000,
                        stream=False,
                    )
                break
            except Exception as exc:
                last_error = exc
                if not self._is_provider_rejection(exc):
                    raise
                logger.warning("JD OCR provider rejected vision model=%s", model)
        else:
            raise last_error or RuntimeError("No available JD OCR vision model")

        content = (
            ChatService._coerce_content_text(
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            or ""
        )
        return self._normalize_ocr_text(content)

    @staticmethod
    def _normalize_ocr_text(text: str) -> str:
        """用于清理模型偶发附带的代码块包裹和多余空白。"""
        normalized = re.sub(
            r"^```(?:text|markdown)?\s*|\s*```$", "", text.strip(), flags=re.DOTALL
        )
        return normalized.strip()

    @staticmethod
    def _candidate_models() -> list[str]:
        """用于处理candidate模型列表。"""
        models = [
            settings.OPENROUTER_VISION_MODEL,
            *settings.OPENROUTER_VISION_FALLBACK_MODELS.split(","),
        ]
        candidates: list[str] = []
        for model in models:
            model = model.strip()
            if model and model not in candidates:
                candidates.append(model)
        return candidates

    @staticmethod
    def _openrouter_chat_service(model: str) -> ChatService:
        """用于创建 JD 图片 OCR 专用的 OpenRouter 视觉模型客户端。"""
        return ChatService(
            model=model,
            api_key=settings.OPENROUTER_API_KEY,
            api_base=settings.OPENROUTER_API_BASE,
            provider_name="OpenRouter",
            extra_headers={
                "HTTP-Referer": "https://chat-resume.com",
                "X-Title": "Chat Resume JD OCR",
            },
        )

    @staticmethod
    def _is_provider_rejection(exc: Exception) -> bool:
        """用于判断提供方拒绝响应。"""
        message = str(exc)
        return (
            "provider Terms Of Service" in message
            or "violation of provider Terms Of Service" in message
            or "AI服务请求失败: 403" in message
        )


__all__ = ["JDOcrService"]
