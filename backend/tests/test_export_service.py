"""
PDF 导出服务测试模块

用于验证 PDF 导出会复用前端打印页，确保导出结果与编辑器预览保持一致。
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.services.processing.export_service as export_service_module
from app.infra.config import settings
from app.services.processing.export_service import ExportService


def _sample_resume_content() -> dict:
    """用于构造一份足以覆盖打印页载荷的最小简历数据。"""
    return {
        "personal_info": {
            "name": "张三",
            "email": "zhangsan@example.com",
            "phone": "13800000000",
        },
        "education": [
            {
                "school": "测试大学",
                "degree": "本科",
                "major": "计算机科学",
                "duration": "2018-2022",
            }
        ],
        "work_experience": [
            {
                "company": "测试公司",
                "position": "后端工程师",
                "duration": "2022-至今",
                "summary": "负责简历系统后端开发与性能优化。",
            }
        ],
        "skills": [{"category": "语言", "items": ["Python", "TypeScript"]}],
        "projects": [
            {
                "name": "导出平台",
                "role": "负责人",
                "duration": "2024",
                "summary": "实现多格式简历导出。",
            }
        ],
    }


def _decode_print_payload(print_url: str) -> dict:
    """用于把打印页 URL 里的 base64 载荷还原成可断言的字典。"""
    parsed = urlparse(print_url)
    query = parse_qs(parsed.query)
    encoded = unquote(query["data"][0])
    raw = base64.urlsafe_b64decode(encoded.encode("utf-8")).decode("utf-8")
    return json.loads(raw)


def test_export_to_pdf_uses_frontend_print_page(tmp_path, monkeypatch):
    """用于验证 PDF 导出会把前端打印页 URL 交给 Playwright。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.com")
    export_service = ExportService()
    captured: dict[str, str] = {}

    async def _capture_print_url(self, print_url: str, filepath: str) -> None:
        """用于捕获传给 Playwright 的打印页 URL，避免真实启动浏览器。"""
        del self
        captured["print_url"] = print_url
        captured["filepath"] = filepath
        Path(filepath).write_bytes(b"%PDF-test")

    monkeypatch.setattr(
        ExportService,
        "_render_pdf_with_playwright",
        _capture_print_url,
    )

    filepath = asyncio.run(export_service.export_to_pdf(_sample_resume_content()))
    exported = Path(filepath)
    parsed = urlparse(captured["print_url"])
    query = parse_qs(parsed.query)

    assert exported.exists()
    assert exported.suffix == ".pdf"
    assert exported.read_bytes().startswith(b"%PDF")
    assert captured["filepath"] == filepath
    assert parsed.scheme == "https"
    assert parsed.netloc == "frontend.example.com"
    assert parsed.path == "/resume/print"
    assert "data" in query
    assert query["data"][0]


def test_build_frontend_print_url_preserves_template_and_chinese_payload(monkeypatch):
    """用于验证打印页 URL 会完整携带模板名和中文简历内容。"""
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.com")
    export_service = ExportService()

    encoded_payload = export_service._build_frontend_print_payload(
        _sample_resume_content(),
        template="compact",
    )
    print_url = export_service._build_frontend_print_url(encoded_payload)
    parsed = urlparse(print_url)
    payload = _decode_print_payload(print_url)

    assert parsed.scheme == "https"
    assert parsed.netloc == "frontend.example.com"
    assert parsed.path == "/resume/print"
    assert payload["template"] == "compact"
    assert payload["content"]["personal_info"]["name"] == "张三"
    assert (
        payload["content"]["work_experience"][0]["summary"]
        == "负责简历系统后端开发与性能优化。"
    )


def test_build_frontend_print_url_preserves_layout_config(monkeypatch):
    """用于验证打印页 URL 会携带预览布局配置。"""
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.com")
    export_service = ExportService()
    layout_config = {
        "density": "compact",
        "moduleOrder": ["personal", "work", "projects", "skills", "education"],
        "visibleModules": ["personal", "work", "projects"],
        "spacingScale": 0.72,
        "templateStyle": "emerald",
    }

    encoded_payload = export_service._build_frontend_print_payload(
        _sample_resume_content(),
        template="emerald",
        layout_config=layout_config,
    )
    print_url = export_service._build_frontend_print_url(encoded_payload)
    payload = _decode_print_payload(print_url)

    assert payload["template"] == "emerald"
    assert payload["layout_config"] == layout_config


def test_render_pdf_with_playwright_uses_expected_page_settings(tmp_path, monkeypatch):
    """用于验证 Playwright 渲染时会使用正确的页面参数和 PDF 选项。"""
    export_service = ExportService()
    captured: dict[str, object] = {}
    render_events: list[object] = []
    output_path = tmp_path / "resume.pdf"

    class FakePage:
        """用于记录页面导航和导出参数。"""

        async def goto(self, url: str, wait_until: str) -> None:
            """用于处理goto。"""
            captured["goto"] = {"url": url, "wait_until": wait_until}

        async def wait_for_selector(self, selector: str, **kwargs) -> None:
            """用于处理waitforselector。"""
            render_events.append(("wait_for_selector", selector, kwargs))

        async def evaluate(self, script: str) -> None:
            """用于处理evaluate。"""
            render_events.append(("evaluate", script))

        async def emulate_media(self, media: str) -> None:
            """用于处理emulatemedia。"""
            captured["media"] = media
            render_events.append(("emulate_media", media))

        async def pdf(self, **kwargs) -> None:
            """用于处理pdf。"""
            captured["pdf"] = kwargs
            render_events.append(("pdf", kwargs))
            Path(kwargs["path"]).write_bytes(b"%PDF-fake")

    class FakeBrowser:
        """用于模拟浏览器实例并暴露页面对象。"""

        def __init__(self) -> None:
            """用于处理init。"""
            self.page = FakePage()

        async def new_page(self, **kwargs):
            """用于处理newpage。"""
            captured["viewport"] = kwargs["viewport"]
            return self.page

        async def close(self) -> None:
            """用于处理close。"""
            captured["closed"] = True

    class FakeChromium:
        """用于记录浏览器启动参数。"""

        async def launch(self, headless: bool):
            """用于处理launch。"""
            captured["launch"] = {"headless": headless}
            return FakeBrowser()

    class FakePlaywright:
        """用于暴露假的 chromium 客户端。"""

        chromium = FakeChromium()

    class FakePlaywrightContext:
        """用于模拟 async_playwright 上下文管理器。"""

        async def __aenter__(self):
            """用于处理aenter。"""
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, tb):
            """用于处理aexit。"""
            return False

    monkeypatch.setattr(
        export_service_module,
        "async_playwright",
        lambda: FakePlaywrightContext(),
    )

    asyncio.run(
        export_service._render_pdf_with_playwright(
            "https://frontend.example.com/resume/print?data=abc",
            str(output_path),
        )
    )

    assert captured["launch"] == {"headless": True}
    assert captured["viewport"] == {"width": 1280, "height": 1810}
    assert captured["goto"] == {
        "url": "https://frontend.example.com/resume/print?data=abc",
        "wait_until": "networkidle",
    }
    assert render_events == [
        ("wait_for_selector", '[data-resume-print-ready="true"]', {"state": "attached"}),
        ("wait_for_selector", "#resume-export-content .resume-page", {}),
        ("emulate_media", "print"),
        ("evaluate", "() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))"),
        ("wait_for_selector", '[data-resume-print-ready="true"]', {"state": "attached"}),
        ("wait_for_selector", "#resume-export-content .resume-page", {}),
        ("wait_for_selector", "text=正在计算分页", {"state": "detached"}),
        ("pdf", {
            "path": str(output_path),
            "format": "A4",
            "prefer_css_page_size": True,
            "print_background": True,
            "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
        }),
    ]
    assert captured["media"] == "print"
    assert captured["pdf"] == {
        "path": str(output_path),
        "format": "A4",
        "prefer_css_page_size": True,
        "print_background": True,
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    }
    assert captured["closed"] is True
    assert output_path.read_bytes().startswith(b"%PDF")


def test_render_pdf_with_playwright_injects_storage_payload(tmp_path, monkeypatch):
    """用于验证大载荷渲染会在导航前写入 sessionStorage。"""
    export_service = ExportService()
    captured: dict[str, object] = {}
    render_events: list[object] = []
    output_path = tmp_path / "resume.pdf"

    class FakePage:
        """用于记录页面脚本注入和导出参数。"""

        async def add_init_script(self, script: str) -> None:
            """用于处理addinitscript。"""
            captured["init_script"] = script

        async def goto(self, url: str, wait_until: str) -> None:
            """用于处理goto。"""
            captured["goto"] = {"url": url, "wait_until": wait_until}

        async def wait_for_selector(self, selector: str, **kwargs) -> None:
            """用于处理waitforselector。"""
            render_events.append(("wait_for_selector", selector, kwargs))

        async def evaluate(self, script: str) -> None:
            """用于处理evaluate。"""
            render_events.append(("evaluate", script))

        async def emulate_media(self, media: str) -> None:
            """用于处理emulatemedia。"""
            captured["media"] = media
            render_events.append(("emulate_media", media))

        async def pdf(self, **kwargs) -> None:
            """用于处理pdf。"""
            render_events.append(("pdf", kwargs))
            Path(kwargs["path"]).write_bytes(b"%PDF-fake")

    class FakeBrowser:
        """用于模拟浏览器实例并暴露页面对象。"""

        async def new_page(self, **kwargs):
            """用于处理newpage。"""
            del kwargs
            return FakePage()

        async def close(self) -> None:
            """用于处理close。"""
            captured["closed"] = True

    class FakeChromium:
        """用于记录浏览器启动参数。"""

        async def launch(self, headless: bool):
            """用于处理launch。"""
            del headless
            return FakeBrowser()

    class FakePlaywright:
        """用于暴露假的 chromium 客户端。"""

        chromium = FakeChromium()

    class FakePlaywrightContext:
        """用于模拟 async_playwright 上下文管理器。"""

        async def __aenter__(self):
            """用于处理aenter。"""
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, tb):
            """用于处理aexit。"""
            return False

    monkeypatch.setattr(
        export_service_module,
        "async_playwright",
        lambda: FakePlaywrightContext(),
    )

    asyncio.run(
        export_service._render_pdf_with_playwright(
            "https://frontend.example.com/resume/print?payloadKey=resume-print-test",
            str(output_path),
            storage_key="resume-print-test",
            storage_payload="encoded-payload",
        )
    )

    assert "sessionStorage.setItem" in str(captured["init_script"])
    assert "resume-print-test" in str(captured["init_script"])
    assert "encoded-payload" in str(captured["init_script"])
    assert render_events == [
        ("wait_for_selector", '[data-resume-print-ready="true"]', {"state": "attached"}),
        ("wait_for_selector", "#resume-export-content .resume-page", {}),
        ("emulate_media", "print"),
        ("evaluate", "() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))"),
        ("wait_for_selector", '[data-resume-print-ready="true"]', {"state": "attached"}),
        ("wait_for_selector", "#resume-export-content .resume-page", {}),
        ("wait_for_selector", "text=正在计算分页", {"state": "detached"}),
        ("pdf", {
            "path": str(output_path),
            "format": "A4",
            "prefer_css_page_size": True,
            "print_background": True,
            "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
        }),
    ]
    assert captured["closed"] is True


def test_export_to_pdf_surfaces_playwright_failure(tmp_path, monkeypatch):
    """用于验证浏览器渲染失败时导出接口会继续抛出原始异常。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    export_service = ExportService()

    async def _raise_render_error(self, print_url: str, filepath: str) -> None:
        """用于模拟 Playwright 启动失败的异常分支。"""
        del self, print_url, filepath
        raise RuntimeError("Executable doesn't exist")

    monkeypatch.setattr(
        ExportService,
        "_render_pdf_with_playwright",
        _raise_render_error,
    )

    try:
        asyncio.run(export_service.export_to_pdf(_sample_resume_content()))
    except RuntimeError as exc:
        assert "Executable doesn't exist" in str(exc)
    else:
        raise AssertionError("导出失败时应抛出 Playwright 原始异常")


def test_export_to_pdf_surfaces_print_page_timeout(
    tmp_path,
    monkeypatch,
):
    """用于验证前端打印页超时时不会静默生成不同样式的 PDF。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    export_service = ExportService()

    async def _raise_timeout(self, print_url: str, filepath: str) -> None:
        """用于模拟前端打印页加载超时。"""
        del self, print_url, filepath
        raise PlaywrightTimeoutError("Timeout 30000ms exceeded")

    monkeypatch.setattr(
        ExportService,
        "_render_pdf_with_playwright",
        _raise_timeout,
    )

    try:
        asyncio.run(export_service.export_to_pdf(_sample_resume_content()))
    except PlaywrightTimeoutError as exc:
        assert "Timeout 30000ms exceeded" in str(exc)
    else:
        raise AssertionError("打印页超时时不应返回服务端兜底 PDF")


def test_export_to_pdf_uses_storage_payload_for_oversized_print_url(
    tmp_path,
    monkeypatch,
):
    """用于验证超长打印页载荷会走浏览器存储而不是 URL 查询串。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.com")
    export_service = ExportService()
    large_content = _sample_resume_content()
    large_content["projects"] = [
        {
            "name": "超长项目",
            "summary": "负责复杂系统。" * 5000,
        }
    ]
    captured: dict[str, str | None] = {}

    async def _capture_frontend_render(
        self,
        print_url: str,
        filepath: str,
        storage_key: str | None = None,
        storage_payload: str | None = None,
    ) -> None:
        """用于捕获超长载荷导出时传给 Playwright 的参数。"""
        del self
        captured["print_url"] = print_url
        captured["storage_key"] = storage_key
        captured["storage_payload"] = storage_payload
        Path(filepath).write_bytes(b"%PDF-large")

    monkeypatch.setattr(
        ExportService,
        "_render_pdf_with_playwright",
        _capture_frontend_render,
    )

    filepath = asyncio.run(export_service.export_to_pdf(large_content))
    parsed = urlparse(str(captured["print_url"]))
    query = parse_qs(parsed.query)

    assert Path(filepath).read_bytes().startswith(b"%PDF")
    assert len(str(captured["print_url"])) <= export_service_module.MAX_FRONTEND_PRINT_URL_CHARS
    assert "payloadKey" in query
    assert "data" not in query
    assert query["payloadKey"][0] == captured["storage_key"]
    assert captured["storage_payload"]


def test_get_file_url_returns_signed_download_path(tmp_path, monkeypatch):
    """用于验证导出文件地址会拼出带签名的下载路径。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    export_service = ExportService()
    monkeypatch.setattr(
        export_service_module,
        "create_download_token",
        lambda filename, user_id: (
            f"expires=123&user_id={user_id}&signature=signed-{filename}"
        ),
    )

    file_url = export_service.get_file_url(
        filepath=str(tmp_path / "exports" / "resume_demo.pdf"),
        user_id=42,
    )

    assert file_url == (
        "/api/resumes/download/resume_demo.pdf?"
        "expires=123&user_id=42&signature=signed-resume_demo.pdf"
    )
