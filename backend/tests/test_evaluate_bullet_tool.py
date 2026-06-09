"""用于覆盖 evaluate_bullet 工具的回归测试。"""

import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.tools.resume.evaluate_bullet_tool import (
    _parse_evaluation,
    evaluate_bullet,
)


def _resume_with_bullet() -> dict[str, Any]:
    """用于构造一份含单条 bullet 的简历。"""
    return {
        "work_experience": [
            {
                "id": "work_1",
                "company": "测试公司",
                "position": "前端工程师",
                "highlights": [
                    {"id": "b1", "text": "负责公司官网的开发和维护"},
                    {"id": "b2", "text": "主导重构前端架构，页面加载速度提升 40%，支撑日均 10 万 PV"},
                ],
            }
        ],
    }


def _mock_llm_response(evaluation: dict[str, Any]) -> dict[str, Any]:
    """用于构造模拟 LLM 返回的 response 结构。"""
    content = json.dumps(evaluation, ensure_ascii=False)
    return {"choices": [{"message": {"content": content}}]}


class ParseEvaluationTests(unittest.TestCase):
    """用于覆盖 _parse_evaluation 的解析逻辑。"""

    def test_parse_valid_json(self):
        """用于验证正常 JSON 能被正确解析。"""
        raw = json.dumps({
            "score": 75,
            "grade": "B",
            "checks": {"quantification": {"pass": False, "detail": "缺少数据"}},
            "summary": "合格但需改进",
            "suggestions": ["补充量化数据"],
        })
        result = _parse_evaluation(raw)
        self.assertEqual(result["score"], 75)
        self.assertEqual(result["grade"], "B")
        self.assertEqual(len(result["suggestions"]), 1)

    def test_parse_json_in_markdown_block(self):
        """用于验证 markdown 代码块内的 JSON 能被正确提取。"""
        evaluation = {"score": 85, "grade": "A", "checks": {}, "summary": "", "suggestions": []}
        raw = "```json\n" + json.dumps(evaluation) + "\n```"
        result = _parse_evaluation(raw)
        self.assertEqual(result["score"], 85)

    def test_parse_invalid_json_returns_fallback(self):
        """用于验证无效 JSON 返回降级结果。"""
        result = _parse_evaluation("这不是 JSON")
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["grade"], "F")
        self.assertIn("解析失败", result["summary"])


class EvaluateBulletTests(unittest.IsolatedAsyncioTestCase):
    """用于覆盖 evaluate_bullet 工具的主流程。"""

    async def test_returns_error_for_invalid_section(self):
        """用于验证不支持的板块返回错误。"""
        result = await evaluate_bullet(
            _resume_with_bullet(),
            section="skills",
            item_id="work_1",
            bullet_id="b1",
        )
        self.assertFalse(result["success"])

    async def test_returns_error_for_missing_item(self):
        """用于验证找不到条目时返回错误。"""
        result = await evaluate_bullet(
            _resume_with_bullet(),
            section="work_experience",
            item_id="nonexistent",
            bullet_id="b1",
        )
        self.assertFalse(result["success"])
        self.assertIn("未找到", result["message"])

    async def test_returns_error_for_missing_bullet(self):
        """用于验证找不到 bullet 时返回错误。"""
        result = await evaluate_bullet(
            _resume_with_bullet(),
            section="work_experience",
            item_id="work_1",
            bullet_id="nonexistent",
        )
        self.assertFalse(result["success"])
        self.assertIn("未找到", result["message"])

    @patch("app.tools.resume.evaluate_bullet_tool.ChatService")
    async def test_evaluate_weak_bullet(self, mock_chat_cls):
        """用于验证弱 bullet 得到低分和改进建议。"""
        mock_chat = AsyncMock()
        mock_chat.chat_completion = AsyncMock(return_value=_mock_llm_response({
            "score": 35,
            "grade": "D",
            "checks": {
                "quantification": {"pass": False, "detail": "缺少量化数据"},
                "expression": {"pass": False, "detail": "以弱动词开头"},
                "impact": {"pass": False, "detail": "未体现结果"},
                "ownership": {"pass": False, "detail": "像职责描述"},
                "persuasiveness": {"pass": False, "detail": "无法追问"},
            },
            "summary": "像职责描述，缺乏成果证据",
            "suggestions": ["补充量化数据", "用强动作动词开头"],
        }))
        mock_chat.__aenter__ = AsyncMock(return_value=mock_chat)
        mock_chat.__aexit__ = AsyncMock(return_value=None)
        mock_chat_cls.return_value = mock_chat

        result = await evaluate_bullet(
            _resume_with_bullet(),
            section="work_experience",
            item_id="work_1",
            bullet_id="b1",
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["score"], 35)
        self.assertEqual(result["grade"], "D")
        self.assertIn("bullet_text", result)
        self.assertIn("location", result)
        self.assertEqual(result["location"]["bullet_id"], "b1")
        self.assertFalse(result["checks"]["quantification"]["pass"])

    @patch("app.tools.resume.evaluate_bullet_tool.ChatService")
    async def test_evaluate_strong_bullet(self, mock_chat_cls):
        """用于验证强 bullet 得到高分。"""
        mock_chat = AsyncMock()
        mock_chat.chat_completion = AsyncMock(return_value=_mock_llm_response({
            "score": 90,
            "grade": "S",
            "checks": {
                "quantification": {"pass": True, "detail": "含量化数据"},
                "expression": {"pass": True, "detail": "强动作动词"},
                "impact": {"pass": True, "detail": "结果清晰"},
                "ownership": {"pass": True, "detail": "体现主导"},
                "persuasiveness": {"pass": True, "detail": "极具说服力"},
            },
            "summary": "优秀的成果证据",
            "suggestions": [],
        }))
        mock_chat.__aenter__ = AsyncMock(return_value=mock_chat)
        mock_chat.__aexit__ = AsyncMock(return_value=None)
        mock_chat_cls.return_value = mock_chat

        result = await evaluate_bullet(
            _resume_with_bullet(),
            section="work_experience",
            item_id="work_1",
            bullet_id="b2",
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["score"], 90)
        self.assertEqual(result["grade"], "S")
        self.assertTrue(result["checks"]["impact"]["pass"])


if __name__ == "__main__":
    unittest.main()
