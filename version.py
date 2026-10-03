"""Version helper."""

from __future__ import annotations

import sys
from pathlib import Path

# ВАЖНО: Обновляйте эту константу при релизе новой версии!
# Она используется в скомпилированном .exe, в то время как файл VERSION используется только в dev-режиме.
FROZEN_VERSION = "0.3.0"


def _read_version() -> str:
    # В frozen (скомпилированном) режиме используем хардкод
    if getattr(sys, 'frozen', False):
        return FROZEN_VERSION

    # В режиме разработки читаем из файла VERSION
    # Путь вычисляется относительно расположения этого файла (version.py)
    # Так как version.py лежит в корне, то и VERSION ищем рядом.
    version_file = Path(__file__).resolve().parent / "VERSION"
    if version_file.exists():
        value = version_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    return "0.0.0"


__version__ = _read_version()
