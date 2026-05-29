"""
导出服务模块

负责生成和导出简历、面试报告等多种格式的文件。
支持PDF、Word、HTML等格式的导出功能。
"""

import base64
import json
import logging
import os
import uuid
from html import escape
from typing import Any, Dict
from urllib.parse import quote

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.infra.config import settings
from app.infra.security import create_download_token

logger = logging.getLogger(__name__)
MAX_FRONTEND_PRINT_URL_CHARS = 8000


class ExportService:
    """处理简历导出。"""

    def __init__(self):
        """用于初始化当前对象。"""
        self.export_dir = os.path.join(settings.UPLOAD_DIR, "exports")
        os.makedirs(self.export_dir, exist_ok=True)

    async def export_to_pdf(
        self,
        resume_content: Dict[str, Any],
        template: str = "default",
        layout_config: Dict[str, Any] | None = None,
    ) -> str:
        """使用前端打印页导出与预览一致的简历 PDF。"""
        filename = f"resume_{uuid.uuid4().hex}.pdf"
        filepath = os.path.join(self.export_dir, filename)
        print_url = self._build_frontend_print_url(
            resume_content,
            template,
            layout_config,
        )
        if len(print_url) > MAX_FRONTEND_PRINT_URL_CHARS:
            logger.error(
                "pdf_export.frontend_print_url_too_large",
                extra={
                    "template": template,
                    "print_url_length": len(print_url),
                    "max_print_url_length": MAX_FRONTEND_PRINT_URL_CHARS,
                },
            )
            raise ValueError(
                "Resume PDF export payload is too large for the print page URL"
            )

        try:
            await self._render_pdf_with_playwright(print_url, filepath)
        except PlaywrightTimeoutError:
            logger.exception(
                "pdf_export.frontend_print_timeout",
                extra={
                    "template": template,
                    "print_url_length": len(print_url),
                    "content_bytes": len(
                        json.dumps(resume_content, ensure_ascii=False).encode("utf-8")
                    ),
                },
            )
            raise
        return filepath

    def export_to_docx(
        self, resume_content: Dict[str, Any], template: str = "default"
    ) -> str:
        """导出简历为Word文档。"""

        del template
        filename = f"resume_{uuid.uuid4().hex}.docx"
        filepath = os.path.join(self.export_dir, filename)

        doc = SimpleDocTemplate(filepath, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.black,
            spaceAfter=12,
            alignment=1,
        )
        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#1d4ed8"),
            spaceAfter=6,
            spaceBefore=12,
        )
        normal_style = styles["Normal"]

        personal_info = resume_content.get("personal_info", {})
        if personal_info.get("name"):
            story.append(Paragraph(escape(str(personal_info["name"])), title_style))
            story.append(Spacer(1, 12))

        contact_info = self._build_contact_texts(personal_info)
        if contact_info:
            story.append(Paragraph(" | ".join(contact_info), normal_style))
            story.append(Spacer(1, 12))

        education = resume_content.get("education", [])
        if education:
            story.append(Paragraph("教育背景", heading_style))
            for edu in education:
                edu_text = self._join_parts(
                    [
                        edu.get("school", ""),
                        edu.get("degree", ""),
                        edu.get("major", ""),
                        edu.get("duration", ""),
                    ]
                )
                if edu_text:
                    story.append(Paragraph(escape(edu_text), normal_style))
                for highlight in self._build_highlight_texts(edu.get("highlights", [])):
                    story.append(Paragraph(escape(highlight), normal_style))
            story.append(Spacer(1, 12))

        work_experience = resume_content.get("work_experience", [])
        if work_experience:
            story.append(Paragraph("工作经验", heading_style))
            for work in work_experience:
                work_text = self._join_parts(
                    [
                        work.get("company", ""),
                        work.get("position", ""),
                        work.get("duration", ""),
                    ]
                )
                if work_text:
                    story.append(Paragraph(escape(work_text), normal_style))
                description = str(
                    work.get("summary", "") or work.get("description", "")
                ).strip()
                if description:
                    story.append(Paragraph(escape(description), normal_style))
                for highlight in self._build_highlight_texts(
                    work.get("highlights", [])
                ):
                    story.append(Paragraph(escape(highlight), normal_style))
                story.append(Spacer(1, 6))
            story.append(Spacer(1, 12))

        skills = self._build_skill_texts(resume_content.get("skills", []))
        if skills:
            story.append(Paragraph("技能专长", heading_style))
            story.append(
                Paragraph(" | ".join(escape(item) for item in skills), normal_style)
            )
            story.append(Spacer(1, 12))

        projects = resume_content.get("projects", [])
        if projects:
            story.append(Paragraph("项目经验", heading_style))
            for project in projects:
                project_name = str(project.get("name", "")).strip()
                if project_name:
                    story.append(Paragraph(escape(project_name), normal_style))
                description = str(
                    project.get("summary", "") or project.get("description", "")
                ).strip()
                if description:
                    story.append(Paragraph(escape(description), normal_style))
                for highlight in self._build_highlight_texts(
                    project.get("highlights", []) or project.get("achievements", [])
                ):
                    story.append(Paragraph(escape(highlight), normal_style))
                story.append(Spacer(1, 6))

        doc.build(story)
        return filepath

    def export_to_html(
        self, resume_content: Dict[str, Any], template: str = "default"
    ) -> str:
        """导出简历为HTML。"""

        del template
        filename = f"resume_{uuid.uuid4().hex}.html"
        filepath = os.path.join(self.export_dir, filename)

        with open(filepath, "w", encoding="utf-8") as file:
            file.write(self._build_html_content(resume_content))

        return filepath

    async def _render_pdf_with_playwright(self, print_url: str, filepath: str) -> None:
        """使用 Playwright 打开前端打印页并输出 PDF。"""

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1280, "height": 1810})
                await page.goto(print_url, wait_until="networkidle")
                await page.emulate_media(media="print")
                await page.pdf(
                    path=filepath,
                    format="A4",
                    prefer_css_page_size=True,
                    print_background=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                )
            finally:
                await browser.close()

    def _build_frontend_print_url(
        self,
        resume_content: Dict[str, Any],
        template: str,
        layout_config: Dict[str, Any] | None = None,
    ) -> str:
        """构建前端打印页地址。"""

        payload = {
            "content": resume_content,
            "template": template,
            "layout_config": layout_config,
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        ).decode("utf-8")
        return f"{settings.FRONTEND_URL.rstrip('/')}/resume/print?data={quote(encoded)}"

    def _build_html_content(self, resume_content: Dict[str, Any]) -> str:
        """构建基础HTML导出内容。"""

        personal_info = resume_content.get("personal_info", {})
        education = resume_content.get("education", [])
        work_experience = resume_content.get("work_experience", [])
        skills = self._build_skill_texts(resume_content.get("skills", []))
        projects = resume_content.get("projects", [])

        contact_html = "".join(
            f"<span>{escape(text)}</span>"
            for text in self._build_contact_texts(personal_info)
        )
        education_parts: list[str] = []
        for item in education:
            subtitle = self._join_parts(
                [
                    item.get("degree", ""),
                    item.get("major", ""),
                    item.get("duration", ""),
                ]
            )
            education_parts.append(
                f"""
            <div class="item">
                <div class="item-title">{escape(str(item.get("school", "")))}</div>
                <div class="item-subtitle">{escape(subtitle)}</div>
                {self._build_highlights_html(item.get("highlights", []))}
            </div>
            """
            )
        education_html = "".join(education_parts)

        work_parts: list[str] = []
        for item in work_experience:
            subtitle = self._join_parts(
                [
                    item.get("position", ""),
                    item.get("duration", ""),
                ]
            )
            description = str(
                item.get("summary", "") or item.get("description", "")
            ).strip()
            work_parts.append(
                f"""
            <div class="item">
                <div class="item-title">{escape(str(item.get("company", "")))}</div>
                <div class="item-subtitle">{escape(subtitle)}</div>
                <div class="item-content">{escape(description)}</div>
                {self._build_highlights_html(item.get("highlights", []))}
            </div>
            """
            )
        work_html = "".join(work_parts)
        skill_html = "".join(
            f'<span class="skill">{escape(item)}</span>' for item in skills
        )
        project_parts: list[str] = []
        for item in projects:
            subtitle = self._join_parts(
                [
                    item.get("role", ""),
                    item.get("duration", ""),
                ]
            )
            description = str(
                item.get("summary", "") or item.get("description", "")
            ).strip()
            project_parts.append(
                f"""
            <div class="item">
                <div class="item-title">{escape(str(item.get("name", "")))}</div>
                <div class="item-subtitle">{escape(subtitle)}</div>
                <div class="item-content">{escape(description)}</div>
                {
                    self._build_highlights_html(
                        item.get("highlights", []) or item.get("achievements", [])
                    )
                }
            </div>
            """
            )
        project_html = "".join(project_parts)

        return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>简历 - {escape(str(personal_info.get("name", "")))}</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            color: #111827;
            background: #f3f4f6;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        }}
        .page {{
            width: 816px;
            margin: 0 auto;
            padding: 48px;
            background: white;
        }}
        .header {{
            margin-bottom: 28px;
            padding-bottom: 16px;
            text-align: center;
            border-bottom: 1px solid #d1d5db;
        }}
        .name {{
            margin-bottom: 8px;
            font-size: 32px;
            font-weight: 700;
        }}
        .contact {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 12px 18px;
            font-size: 13px;
            color: #4b5563;
        }}
        .section {{
            margin-bottom: 24px;
        }}
        .section-title {{
            margin: 0 0 12px;
            padding-bottom: 6px;
            font-size: 20px;
            font-weight: 700;
            border-bottom: 1px solid #e5e7eb;
        }}
        .item {{
            margin-bottom: 14px;
        }}
        .item-title {{
            font-weight: 700;
        }}
        .item-subtitle {{
            color: #6b7280;
        }}
        .item-content {{
            margin-top: 5px;
            white-space: pre-wrap;
        }}
        .item-highlights {{
            margin: 8px 0 0 18px;
            padding: 0;
        }}
        .item-highlight {{
            margin-top: 4px;
        }}
        .skills {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .skill {{
            padding: 4px 10px;
            font-size: 12px;
            background: #f3f4f6;
            border-radius: 999px;
        }}
    </style>
</head>
<body>
    <div class="page">
        <div class="header">
            <div class="name">{escape(str(personal_info.get("name", "")))}</div>
            <div class="contact">{contact_html}</div>
        </div>
        {self._wrap_section("教育背景", education_html)}
        {self._wrap_section("工作经验", work_html)}
        {
            self._wrap_section(
                "技能专长",
                f'<div class="skills">{skill_html}</div>' if skill_html else "",
            )
        }
        {self._wrap_section("项目经验", project_html)}
    </div>
</body>
</html>
"""

    def _wrap_section(self, title: str, content: str) -> str:
        """包装导出区块。"""

        if not content:
            return ""
        return (
            '<section class="section">'
            f'<div class="section-title">{title}</div>'
            f"{content}"
            "</section>"
        )

    def _build_contact_texts(self, personal_info: Dict[str, Any]) -> list[str]:
        """构建联系信息文本。"""

        contact_info: list[str] = []
        if personal_info.get("email"):
            contact_info.append(f"邮箱：{personal_info['email']}")
        if personal_info.get("phone"):
            contact_info.append(f"电话：{personal_info['phone']}")
        if personal_info.get("address"):
            contact_info.append(f"地址：{personal_info['address']}")
        if personal_info.get("github"):
            contact_info.append("GitHub")
        if personal_info.get("linkedin"):
            contact_info.append("LinkedIn")
        if personal_info.get("website"):
            contact_info.append("个人网站")
        return contact_info

    def _build_skill_texts(self, skills: list[Any]) -> list[str]:
        """构建技能文本。"""

        values = []
        for item in skills:
            if isinstance(item, dict):
                category = str(item.get("category", "")).strip()
                grouped_items = item.get("items", [])
                if isinstance(grouped_items, list) and grouped_items:
                    labels = [
                        str(skill).strip()
                        for skill in grouped_items
                        if str(skill).strip()
                    ]
                    if labels:
                        values.append(
                            f"{category}：{' / '.join(labels)}"
                            if category
                            else " / ".join(labels)
                        )
                    continue
                label = item.get("name", "")
            else:
                label = item
            if label:
                values.append(str(label))
        return values

    def _build_highlight_texts(self, highlights: list[Any]) -> list[str]:
        """将高亮点统一成文本列表。"""

        values = []
        for item in highlights:
            if isinstance(item, dict):
                label = item.get("text", "")
            else:
                label = item
            if label:
                values.append(f"• {str(label).strip()}")
        return values

    def _build_highlights_html(self, highlights: list[Any]) -> str:
        """构建高亮点 HTML。"""

        values = self._build_highlight_texts(highlights)
        if not values:
            return ""
        items = "".join(
            f'<li class="item-highlight">{escape(value)}</li>' for value in values
        )
        return f'<ul class="item-highlights">{items}</ul>'

    def _join_parts(self, parts: list[Any]) -> str:
        """拼接非空文本。"""

        return " | ".join(str(part).strip() for part in parts if str(part).strip())

    def get_file_url(self, *, filepath: str, user_id: int) -> str:
        """获取文件访问URL。"""

        filename = os.path.basename(filepath)
        query = create_download_token(filename=filename, user_id=user_id)
        return f"/api/resumes/download/{filename}?{query}"

    def delete_file(self, filepath: str) -> bool:
        """删除导出文件。"""

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
            return False
        except Exception:
            return False
