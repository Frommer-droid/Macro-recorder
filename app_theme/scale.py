"""Минимальные helpers масштабирования QSS, выделенные из OpenCode-router.

Источник: OpenCode-router, ``app/services/ui_scale_service.py`` →
``scale_px`` / ``scale_point_size``. Остальной сервис автомасштаба
(вычисление процентов по экрану) сюда не входит: рекордер использует
фиксированный ``scale_factor=1.0``, а размер шрифта задаётся настройкой.
"""

from __future__ import annotations


def scale_px(value: int | float, scale_factor: float) -> int:
    return max(1, round(value * scale_factor))


def scale_point_size(value: int | float, scale_factor: float) -> float:
    return max(1.0, round(value * scale_factor * 2) / 2)
