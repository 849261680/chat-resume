"""用于覆盖 test_jd_ocr_service.py 对应的回归测试。"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.processing.jd_ocr_service import JDOcrService  # noqa: E402


class JDOcrServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_extract_text_falls_back_after_provider_rejection(self):
        """用于验证extracttextfallsbackafterproviderrejection。"""
        called_models: list[str] = []

        class FakeChatService:
            @staticmethod
            def _coerce_content_text(value):
                """用于处理coercecontenttext。"""
                return value if isinstance(value, str) else ""

            def __init__(self, model: str, **kwargs):
                """用于处理init。"""
                del kwargs
                self.model = model
                called_models.append(model)

            async def __aenter__(self):
                """用于处理aenter。"""
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                """用于处理aexit。"""
                return None

            async def chat_completion(self, **kwargs):
                """用于处理chatcompletion。"""
                if self.model == "first-vision":
                    raise Exception(
                        "AI服务请求失败: 403 - violation of provider Terms Of Service"
                    )
                return {"choices": [{"message": {"content": "岗位职责\n负责后端"}}]}

        with (
            patch(
                "app.services.processing.jd_ocr_service.settings.OPENROUTER_VISION_MODEL",
                "first-vision",
            ),
            patch(
                "app.services.processing.jd_ocr_service.settings.OPENROUTER_VISION_FALLBACK_MODELS",
                "second-vision",
            ),
            patch(
                "app.services.processing.jd_ocr_service.ChatService",
                FakeChatService,
            ),
        ):
            text = await JDOcrService().extract_text_from_image(
                image_bytes=b"fake-image",
                mime_type="image/png",
            )

        self.assertEqual(called_models, ["first-vision", "second-vision"])
        self.assertEqual(text, "岗位职责\n负责后端")

    def test_candidate_models_deduplicates_primary_and_fallbacks(self):
        """用于验证candidatemodelsdeduplicatesprimaryandfallbacks。"""
        with (
            patch(
                "app.services.processing.jd_ocr_service.settings.OPENROUTER_VISION_MODEL",
                "qwen/qwen2.5-vl-72b-instruct",
            ),
            patch(
                "app.services.processing.jd_ocr_service.settings.OPENROUTER_VISION_FALLBACK_MODELS",
                "google/gemini-2.5-flash,qwen/qwen2.5-vl-72b-instruct",
            ),
        ):
            models = JDOcrService._candidate_models()

        self.assertEqual(
            models,
            ["qwen/qwen2.5-vl-72b-instruct", "google/gemini-2.5-flash"],
        )
