"""Тема приложения Macro Recorder, выделенная из OpenCode-router.

Пакет автономен: репозиторий роутера не требуется.
"""

from app_theme.colors import ROUTER_COLORS
from app_theme.scale import scale_point_size, scale_px
from app_theme.styles import (
    DERIVED_COLORS,
    apply_theme,
    build_global_stylesheet,
    enforce_button_proportions,
)

__all__ = [
    "DERIVED_COLORS",
    "ROUTER_COLORS",
    "apply_theme",
    "build_global_stylesheet",
    "enforce_button_proportions",
    "scale_point_size",
    "scale_px",
]
