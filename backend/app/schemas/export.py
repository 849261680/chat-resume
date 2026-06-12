"""
导出相关数据模式

定义简历和面试报告导出相关的Pydantic模式。
支持多种格式导出的数据验证和序列化。
"""

from typing import Any, Optional

from pydantic import BaseModel, field_validator

from app.schemas.resume import validate_layout_config_value


class ExportRequest(BaseModel):
    """用于校验导出请求参数。"""

    format: str  # pdf, docx, html
    template: Optional[str] = "default"
    layout_config: Optional[dict[str, Any]] = None

    @field_validator("layout_config", mode="before")
    @classmethod
    def validate_layout_config(cls, value: Any) -> dict[str, Any] | None:
        """用于导出时复用布局配置校验。"""
        return validate_layout_config_value(value)


class ExportResponse(BaseModel):
    """用于返回导出文件下载信息。"""

    download_url: str
    filename: str
    format: str
