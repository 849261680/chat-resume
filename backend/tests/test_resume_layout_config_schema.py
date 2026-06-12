"""用于验证简历布局配置 schema 与前端密度范围一致。"""

import pytest
from pydantic import ValidationError

from app.schemas.resume import LayoutConfigUpdate


def _layout_payload(spacing_scale: float) -> dict[str, object]:
    """用于构造最小布局配置 payload。"""
    modules = ["personal", "summary", "education", "work", "projects", "open_source", "skills"]
    return {
        "density": "custom",
        "moduleOrder": modules,
        "visibleModules": modules,
        "spacingScale": spacing_scale,
        "templateStyle": "classic",
    }


def test_layout_config_accepts_frontend_max_spacing_scale() -> None:
    """用于验证后端接受前端滑块最大值 1.8。"""
    config = LayoutConfigUpdate(**_layout_payload(1.8))

    assert config.spacingScale == 1.8


def test_layout_config_rejects_spacing_scale_above_frontend_max() -> None:
    """用于验证后端拒绝超过前端滑块最大值的间距。"""
    with pytest.raises(ValidationError):
        LayoutConfigUpdate(**_layout_payload(1.81))
