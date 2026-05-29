"""
简历解析器单元测试

覆盖：
  - _extract_basic_info   正则提取个人信息
  - _parse_ai_response    JSON 提取与清理
  - _clean_json_string    markdown 代码块、BOM、控制字符处理
  - _calculate_parsing_quality  评分逻辑
  - _create_fallback_result     fallback 结构完整性
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.processing.resume_parser import AIResumeParser  # noqa: E402


def _parser() -> AIResumeParser:
    """返回一个不需要 API Key 的解析器实例（仅测试纯函数）。"""
    p = AIResumeParser.__new__(AIResumeParser)
    return p


# ═══════════════════════════════════════════════════════════════════════════
# 0. model configuration
# ═══════════════════════════════════════════════════════════════════════════


class TestParserModelConfig(unittest.TestCase):
    def test_resume_parser_model_overrides_global_openrouter_model(self):
        """用于验证简历parsermodeloverridesglobalopenroutermodel。"""
        with patch.dict(
            "os.environ",
            {
                "OPENROUTER_API_KEY": "test-key",
                "OPENROUTER_MODEL": "deepseek/deepseek-v4-pro",
                "OPENROUTER_RESUME_PARSER_MODEL": "deepseek/deepseek-v4-flash",
            },
            clear=False,
        ):
            parser = AIResumeParser()

        self.assertEqual(parser.model, "deepseek/deepseek-v4-flash")

    def test_resume_parser_model_falls_back_to_global_openrouter_model(self):
        """用于验证简历parsermodelfallsbacktoglobalopenroutermodel。"""
        with patch.dict(
            "os.environ",
            {
                "OPENROUTER_API_KEY": "test-key",
                "OPENROUTER_MODEL": "deepseek/deepseek-v4-pro",
            },
            clear=False,
        ):
            with patch.dict("os.environ", {"OPENROUTER_RESUME_PARSER_MODEL": ""}):
                parser = AIResumeParser()

        self.assertEqual(parser.model, "deepseek/deepseek-v4-pro")

    def test_openrouter_vision_model_does_not_inherit_global_chat_model(self):
        """用于验证openroutervisionmodeldoesnotinheritglobalchatmodel。"""
        from app.infra.config import Settings

        with patch.dict(
            "os.environ",
            {"OPENROUTER_MODEL": "deepseek/deepseek-v4-pro"},
            clear=False,
        ):
            os.environ.pop("OPENROUTER_VISION_MODEL", None)
            settings = Settings()

        self.assertEqual(settings.OPENROUTER_MODEL, "deepseek/deepseek-v4-pro")
        self.assertEqual(
            settings.OPENROUTER_VISION_MODEL,
            "qwen/qwen2.5-vl-72b-instruct",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 1. _extract_basic_info
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractBasicInfo(unittest.TestCase):
    def test_extracts_mainland_phone(self):
        """用于验证extractsmainlandphone。"""
        info = _parser()._extract_basic_info("联系方式：13812345678")
        self.assertEqual(info["phone"], "13812345678")

    def test_extracts_phone_with_86_prefix(self):
        """用于验证extractsphonewith86prefix。"""
        info = _parser()._extract_basic_info("+86 138 1234 5678")
        self.assertIn("phone", info)
        # +86 前缀后的数字去掉分隔符，结果包含完整11位号码
        self.assertIn("13812345678", info["phone"])

    def test_extracts_email(self):
        """用于验证extractsemail。"""
        info = _parser()._extract_basic_info("邮箱：zhangwei@example.com")
        self.assertEqual(info["email"], "zhangwei@example.com")

    def test_extracts_email_with_plus(self):
        """用于验证extractsemailwithplus。"""
        info = _parser()._extract_basic_info("email: user+tag@corp.io")
        self.assertEqual(info["email"], "user+tag@corp.io")

    def test_extracts_github_url(self):
        """用于验证extractsgithuburl。"""
        info = _parser()._extract_basic_info("GitHub: github.com/zhangwei")
        self.assertEqual(info["github"], "https://github.com/zhangwei")

    def test_extracts_github_with_repo(self):
        """用于验证extractsgithubwithrepo。"""
        info = _parser()._extract_basic_info("https://github.com/user/chat-resume")
        self.assertEqual(info["github"], "https://github.com/user/chat-resume")

    def test_extracts_linkedin(self):
        """用于验证extractslinkedin。"""
        info = _parser()._extract_basic_info("linkedin.com/in/zhangwei-dev")
        self.assertEqual(info["linkedin"], "https://linkedin.com/in/zhangwei-dev")

    def test_extracts_labeled_name(self):
        """用于验证extractslabeledname。"""
        info = _parser()._extract_basic_info("姓名：张伟\n手机：13800000000")
        self.assertEqual(info["name"], "张伟")

    def test_extracts_name_english_label(self):
        """用于验证extractsnameenglishlabel。"""
        info = _parser()._extract_basic_info("Name: Wei Zhang\nEmail: w@x.com")
        self.assertEqual(info["name"], "Wei Zhang")

    def test_extracts_name_from_first_chinese_line(self):
        """用于验证extractsnamefromfirstchineseline。"""
        text = "张伟\n求职意向：后端工程师\n13812345678"
        info = _parser()._extract_basic_info(text)
        self.assertEqual(info["name"], "张伟")

    def test_extracts_name_from_first_english_line(self):
        """用于验证extractsnamefromfirstenglishline。"""
        text = "John Smith\nBackend Engineer\njohn@example.com"
        info = _parser()._extract_basic_info(text)
        self.assertEqual(info["name"], "John Smith")

    def test_skips_resume_title_keywords(self):
        """用于验证skips简历titlekeywords。"""
        text = "个人简历\n张伟\n13800000000"
        info = _parser()._extract_basic_info(text)
        self.assertEqual(info["name"], "张伟")

    def test_skips_cv_keyword(self):
        """用于验证skipscvkeyword。"""
        text = "CV\nLi Ming\nli@example.com"
        info = _parser()._extract_basic_info(text)
        self.assertEqual(info["name"], "Li Ming")

    def test_extracts_position_intent(self):
        """用于验证extractspositionintent。"""
        info = _parser()._extract_basic_info("求职意向：高级后端工程师\n")
        self.assertEqual(info["position"], "高级后端工程师")

    def test_extracts_position_alternative_labels(self):
        """用于验证extractspositionalternativelabels。"""
        for label in ("应聘岗位", "应聘职位", "目标岗位"):
            with self.subTest(label=label):
                info = _parser()._extract_basic_info(f"{label}：产品经理")
                self.assertEqual(info["position"], "产品经理")

    def test_position_truncated_to_50_chars(self):
        """用于验证positiontruncatedto50chars。"""
        long_title = "高级" * 30  # 60 chars
        info = _parser()._extract_basic_info(f"求职意向：{long_title}")
        self.assertLessEqual(len(info["position"]), 50)

    def test_empty_text_returns_empty_dict(self):
        """用于验证emptytextreturnsemptydict。"""
        info = _parser()._extract_basic_info("")
        self.assertEqual(info, {})

    def test_no_false_positive_on_landline(self):
        """固定电话不应被误识别为手机号。"""
        info = _parser()._extract_basic_info("电话：010-12345678")
        self.assertNotIn("phone", info)

    def test_multiple_fields_extracted_together(self):
        """用于验证multiplefieldsextractedtogether。"""
        text = (
            "张伟\n"
            "求职意向：后端工程师\n"
            "手机：13812345678\n"
            "Email: zhangwei@example.com\n"
            "github.com/zhangwei\n"
            "linkedin.com/in/zhangwei\n"
        )
        info = _parser()._extract_basic_info(text)
        self.assertEqual(info["name"], "张伟")
        self.assertEqual(info["position"], "后端工程师")
        self.assertEqual(info["phone"], "13812345678")
        self.assertEqual(info["email"], "zhangwei@example.com")
        self.assertEqual(info["github"], "https://github.com/zhangwei")
        self.assertEqual(info["linkedin"], "https://linkedin.com/in/zhangwei")


# ═══════════════════════════════════════════════════════════════════════════
# 2. _parse_ai_response
# ═══════════════════════════════════════════════════════════════════════════


class TestParseAiResponse(unittest.TestCase):
    def test_parses_clean_json(self):
        """用于验证parsescleanjson。"""
        raw = '{"personal_info": {"name": "张伟"}, "skills": []}'
        result = _parser()._parse_ai_response(raw)
        self.assertEqual(result["personal_info"]["name"], "张伟")

    def test_strips_markdown_code_block(self):
        """用于验证stripsmarkdowncodeblock。"""
        raw = '```json\n{"personal_info": {"name": "李明"}}\n```'
        result = _parser()._parse_ai_response(raw)
        self.assertEqual(result["personal_info"]["name"], "李明")

    def test_strips_markdown_code_block_no_language(self):
        """用于验证stripsmarkdowncodeblocknolanguage。"""
        raw = '```\n{"skills": ["Python"]}\n```'
        result = _parser()._parse_ai_response(raw)
        self.assertEqual(result["skills"], ["Python"])

    def test_extracts_json_from_surrounding_text(self):
        """用于验证extractsjsonfromsurroundingtext。"""
        raw = '以下是解析结果：\n{"personal_info": {"name": "王芳"}}\n希望对你有帮助。'
        result = _parser()._parse_ai_response(raw)
        self.assertEqual(result["personal_info"]["name"], "王芳")

    def test_handles_unescaped_newline_in_string(self):
        # JSON 字符串内含原始换行符（LLM 偶尔会这样输出）
        """用于验证handlesunescapednewlineinstring。"""
        raw = '{"description": "第一行\n第二行"}'
        result = _parser()._parse_ai_response(raw)
        self.assertIn("description", result)

    def test_raises_on_completely_invalid_content(self):
        """用于验证raisesoncompletelyinvalidcontent。"""
        with self.assertRaises(Exception):
            _parser()._parse_ai_response("这不是任何格式的JSON内容")

    def test_handles_bom_prefix(self):
        """用于验证handlesbomprefix。"""
        raw = '\ufeff{"personal_info": {"name": "赵六"}}'
        result = _parser()._parse_ai_response(raw)
        self.assertEqual(result["personal_info"]["name"], "赵六")


# ═══════════════════════════════════════════════════════════════════════════
# 3. _clean_json_string
# ═══════════════════════════════════════════════════════════════════════════


class TestCleanJsonString(unittest.TestCase):
    def test_removes_json_code_fence(self):
        """用于验证removesjsoncodefence。"""
        cleaned = _parser()._clean_json_string('```json\n{"a":1}\n```')
        self.assertEqual(cleaned, '{"a":1}')

    def test_removes_plain_code_fence(self):
        """用于验证removesplaincodefence。"""
        cleaned = _parser()._clean_json_string('```\n{"a":1}\n```')
        self.assertEqual(cleaned, '{"a":1}')

    def test_removes_bom(self):
        """用于验证removesbom。"""
        cleaned = _parser()._clean_json_string('\ufeff{"a":1}')
        self.assertFalse(cleaned.startswith("\ufeff"))

    def test_strips_surrounding_whitespace(self):
        """用于验证stripssurroundingwhitespace。"""
        cleaned = _parser()._clean_json_string('  \n{"a":1}\n  ')
        self.assertEqual(cleaned, '{"a":1}')

    def test_fixes_unescaped_newline_in_string_value(self):
        """用于验证fixesunescapednewlineinstringvalue。"""
        raw = '{"desc": "line1\nline2"}'
        cleaned = _parser()._clean_json_string(raw)
        import json

        parsed = json.loads(cleaned)
        self.assertIn("line1", parsed["desc"])

    def test_does_not_alter_valid_json(self):
        """用于验证doesnotaltervalidjson。"""
        valid = '{"name": "张伟", "skills": ["Python", "Go"]}'
        cleaned = _parser()._clean_json_string(valid)
        import json

        self.assertEqual(json.loads(cleaned), json.loads(valid))


# ═══════════════════════════════════════════════════════════════════════════
# 4. _calculate_parsing_quality
# ═══════════════════════════════════════════════════════════════════════════


class TestCalculateParsingQuality(unittest.TestCase):
    def test_empty_resume_scores_zero(self):
        """用于验证empty简历scoreszero。"""
        score = _parser()._calculate_parsing_quality(
            {"personal_info": {}, "skills": [], "projects": [], "education": []}
        )
        self.assertEqual(score, 0.0)

    def test_full_personal_info_contributes_40_percent(self):
        """用于验证fullpersonalinfocontributes40percent。"""
        score = _parser()._calculate_parsing_quality(
            {
                "personal_info": {"name": "张伟", "email": "a@b.com", "phone": "138"},
                "skills": [],
                "projects": [],
                "education": [],
            }
        )
        self.assertAlmostEqual(score, 0.4)

    def test_partial_personal_info_partial_score(self):
        # 只有 name(4分)，满分10分，→ 0.4 * 0.4 = 0.16
        """用于验证partialpersonalinfopartialscore。"""
        score = _parser()._calculate_parsing_quality(
            {
                "personal_info": {"name": "张伟"},
                "skills": [],
                "projects": [],
                "education": [],
            }
        )
        self.assertAlmostEqual(score, 0.16)

    def test_education_contributes_10_percent(self):
        """用于验证educationcontributes10percent。"""
        score = _parser()._calculate_parsing_quality(
            {
                "personal_info": {},
                "skills": [],
                "projects": [],
                "education": [{"school": "北大"}],
            }
        )
        self.assertAlmostEqual(score, 0.1)

    def test_8_skills_contributes_full_25_percent(self):
        """用于验证8skillscontributesfull25percent。"""
        skills = [{"category": "语言", "items": [str(i)]} for i in range(8)]
        score = _parser()._calculate_parsing_quality(
            {"personal_info": {}, "skills": skills, "projects": [], "education": []}
        )
        self.assertAlmostEqual(score, 0.25)

    def test_3_projects_contributes_full_25_percent(self):
        """用于验证3projectscontributesfull25percent。"""
        projects = [{"name": f"项目{i}"} for i in range(3)]
        score = _parser()._calculate_parsing_quality(
            {"personal_info": {}, "skills": [], "projects": projects, "education": []}
        )
        self.assertAlmostEqual(score, 0.25)

    def test_score_capped_at_1(self):
        """用于验证scorecappedat1。"""
        skills = [{"category": "语言", "items": [str(i)]} for i in range(20)]
        projects = [{"name": f"项目{i}"} for i in range(10)]
        score = _parser()._calculate_parsing_quality(
            {
                "personal_info": {"name": "张伟", "email": "a@b.com", "phone": "138"},
                "skills": skills,
                "projects": projects,
                "education": [{"school": "北大"}],
            }
        )
        self.assertLessEqual(score, 1.0)

    def test_score_is_rounded_to_2_decimals(self):
        """用于验证scoreisroundedto2decimals。"""
        score = _parser()._calculate_parsing_quality(
            {
                "personal_info": {"name": "张伟"},
                "skills": [{"category": "x", "items": ["a"]}],
                "projects": [],
                "education": [],
            }
        )
        self.assertEqual(score, round(score, 2))


# ═══════════════════════════════════════════════════════════════════════════
# 5. _create_fallback_result
# ═══════════════════════════════════════════════════════════════════════════


class TestCreateFallbackResult(unittest.TestCase):
    def test_returns_required_keys(self):
        """用于验证returnsrequiredkeys。"""
        result = _parser()._create_fallback_result("任意文本")
        for key in (
            "personal_info",
            "education",
            "work_experience",
            "skills",
            "projects",
            "raw_text",
        ):
            self.assertIn(key, result)

    def test_parsing_method_is_fallback(self):
        """用于验证parsingmethodisfallback。"""
        result = _parser()._create_fallback_result("任意文本")
        self.assertEqual(result["parsing_method"], "fallback")

    def test_parsing_quality_is_zero(self):
        """用于验证parsingqualityiszero。"""
        result = _parser()._create_fallback_result("任意文本")
        self.assertEqual(result["parsing_quality"], 0.0)

    def test_raw_text_preserved(self):
        """用于验证rawtextpreserved。"""
        text = "这是原始简历内容"
        result = _parser()._create_fallback_result(text)
        self.assertEqual(result["raw_text"], text)

    def test_personal_info_populated_from_text(self):
        """用于验证personalinfopopulatedfromtext。"""
        text = "张伟\n13812345678\nzhangwei@example.com"
        result = _parser()._create_fallback_result(text)
        self.assertEqual(result["personal_info"]["phone"], "13812345678")
        self.assertEqual(result["personal_info"]["email"], "zhangwei@example.com")

    def test_empty_text_returns_empty_personal_info(self):
        """用于验证emptytextreturnsemptypersonalinfo。"""
        result = _parser()._create_fallback_result("")
        self.assertIsInstance(result["personal_info"], dict)

    def test_lists_are_empty(self):
        """用于验证listsareempty。"""
        result = _parser()._create_fallback_result("随便")
        self.assertEqual(result["education"], [])
        self.assertEqual(result["work_experience"], [])
        self.assertEqual(result["skills"], [])
        self.assertEqual(result["projects"], [])


if __name__ == "__main__":
    unittest.main()
