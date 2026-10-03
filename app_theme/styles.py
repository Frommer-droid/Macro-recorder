"""Глобальная тема приложения, выделенная из D:\\dev\\OpenCode-router.

Источник QSS-ядра: OpenCode-router, ``app/ui/styles.py`` →
``build_global_stylesheet``. Ядро скопировано 1-в-1 (селекторы роутера:
card, title, health-бейджи, primaryButton и т.д. сохранены для
совместимости будущих экранов).

Appendix в конце покрывает виджеты Macro Recorder, которых нет в QSS
роутера (QLineEdit, QTreeWidget, QMenu, QGroupBox, QCheckBox,
QTableCornerButton), — токенами из :mod:`app_theme.colors`.
Система ролей кнопок (фон → шрифт → hover):
``neutral`` (все кнопки по умолчанию: Настройки, Дублировать, Переименовать,
Новая папка, ⌨️ ❌ ↑↓) → surface_hover → text_strong → primary_hover;
``start_btn`` → accent → on_accent → accent_hover;
``danger_btn`` (Удалить) → danger → on_accent → danger_text;
``success_btn`` (Сохранить, Продолжить) → success → on_accent → success_hover;
``warning_btn`` (Перезаписать) → warning → on_accent → warning_hover.
Недостающие hover/pressed-оттенки — в ``DERIVED_COLORS`` ниже (в палитре
роутера их нет, значения выведены из базовых и помечены явно).
Правило геометрии (см. ``enforce_button_proportions``): кнопка — квадрат
или альбомный прямоугольник; ширина меньше высоты запрещена.
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app_theme.colors import ROUTER_COLORS
from app_theme.scale import scale_point_size, scale_px

# Производные оттенки (в палитре роутера отсутствуют как токены):
# осветления для hover цветных кнопок и затемнение danger для pressed.
# Держатся отдельно, чтобы ROUTER_COLORS оставалась копией 1-в-1.
# Явный пользовательский словарь в apply_theme()/build_global_stylesheet()
# побеждает эти значения.
DERIVED_COLORS: dict[str, str] = {
    "success_hover": "#B3D898",
    "warning_hover": "#E4B183",
    "danger_pressed": "#A9505A",
}


def build_global_stylesheet(
    colors: dict[str, str], scale_factor: float = 1.0, base_font_size: float = 10.0
) -> str:
    colors = {**DERIVED_COLORS, **colors}
    def px(value: int | float) -> int:
        return scale_px(value, scale_factor)

    def pt(value: int | float) -> float:
        return scale_point_size(value, scale_factor)

    # --- Ядро темы роутера (1-в-1, не менять без сверки с источником) ---
    core = f"""
        QWidget {{
            background: {colors['background']};
            color: {colors['text']};
            font-family: "Tahoma", "Segoe UI", "Aptos", sans-serif;
            font-size: {pt(base_font_size)}pt;
        }}
        QMainWindow {{ background: {colors['background']}; }}
        QFrame#card {{
            background: {colors['surface']};
            border: {px(1)}px solid {colors['border']};
            border-radius: {px(10)}px;
        }}
        QFrame#card QWidget {{ background: transparent; }}
        QLabel#title {{ color: {colors['text_strong']}; font-size: {pt(19)}pt; font-weight: 700; }}
        QLabel#subtitle, QLabel#muted, QLabel#scaleInfo {{ color: {colors['muted']}; }}
        QLabel#sectionTitle {{ color: {colors['text_strong']}; font-size: {pt(11)}pt; font-weight: 600; }}
        QLabel#metricValue {{ color: {colors['text_strong']}; font-size: {pt(15)}pt; font-weight: 650; }}
        QLabel#healthGood {{
            color: {colors['on_accent']};
            background: {colors['success']};
            border-radius: {px(10)}px;
            padding: {px(3)}px {px(9)}px;
            font-weight: 700;
        }}
        QLabel#healthBad {{
            color: {colors['on_accent']};
            background: {colors['danger']};
            border-radius: {px(10)}px;
            padding: {px(3)}px {px(9)}px;
            font-weight: 700;
        }}
        QLabel#healthUnknown {{
            color: {colors['text']};
            background: {colors['primary']};
            border-radius: {px(10)}px;
            padding: {px(3)}px {px(9)}px;
            font-weight: 600;
        }}
        QPushButton {{
            background: {colors['surface_alt']};
            border: {px(1)}px solid {colors['border']};
            border-radius: {px(7)}px;
            padding: {px(7)}px {px(13)}px;
            font-weight: 600;
        }}
        QPushButton:hover {{ border-color: {colors['focus']}; background: {colors['surface_hover']}; }}
        QPushButton:pressed {{ background: {colors['surface_pressed']}; }}
        QPushButton:focus {{ border: {px(2)}px solid {colors['focus']}; }}
        QPushButton:disabled {{
            color: {colors['disabled_text']};
            background: {colors['disabled_background']};
            border-color: {colors['disabled_border']};
        }}
        QPushButton#primaryButton {{
            color: {colors['on_accent']};
            background: {colors['accent']};
            border-color: {colors['accent']};
        }}
        QPushButton#primaryButton:hover {{ background: {colors['accent_hover']}; }}
        QPushButton#primaryButton:pressed {{ background: {colors['accent_pressed']}; }}
        QPushButton#primaryButton:disabled {{
            color: {colors['disabled_text']};
            background: {colors['disabled_background']};
            border-color: {colors['disabled_border']};
        }}
        QComboBox, QPlainTextEdit {{
            background: {colors['surface_alt']};
            border: {px(1)}px solid {colors['border']};
            border-radius: {px(6)}px;
            padding: {px(6)}px {px(8)}px;
            selection-background-color: {colors['selection']};
        }}
        QComboBox:focus, QPlainTextEdit:focus {{ border-color: {colors['focus']}; }}
        QComboBox::drop-down {{ border: 0; width: {px(24)}px; }}
        QTableWidget {{
            background: {colors['background']};
            alternate-background-color: {colors['alternate']};
            border: {px(1)}px solid {colors['border']};
            border-radius: {px(7)}px;
            gridline-color: {colors['border']};
            selection-background-color: {colors['selection']};
            selection-color: {colors['text_strong']};
        }}
        QHeaderView::section {{
            background: {colors['surface_alt']};
            color: {colors['muted']};
            border: 0;
            border-bottom: {px(1)}px solid {colors['border']};
            padding: {px(7)}px;
            font-weight: 600;
        }}
        QHeaderView::section:hover {{ background: {colors['surface_hover']}; }}
        QProgressBar {{
            border: 0;
            background: {colors['surface_alt']};
            border-radius: {px(2)}px;
            max-height: {px(4)}px;
        }}
        QProgressBar::chunk {{ background: {colors['accent']}; border-radius: {px(2)}px; }}
        QSplitter::handle {{ background: {colors['border']}; height: {px(1)}px; }}
        QScrollBar:vertical {{ width: {px(10)}px; background: transparent; }}
        QScrollBar::handle:vertical {{
            background: {colors['scrollbar']};
            border-radius: {px(4)}px;
            min-height: {px(24)}px;
        }}
        QToolTip {{
            color: {colors['text']};
            background: {colors['surface']};
            border: {px(1)}px solid {colors['focus']};
            padding: {px(4)}px;
        }}
    """

    # --- Appendix: виджеты Macro Recorder, которых нет в ядре роутера ---
    appendix = f"""
        QLineEdit {{
            background: {colors['surface_alt']};
            border: {px(1)}px solid {colors['border']};
            border-radius: {px(6)}px;
            padding: {px(6)}px {px(8)}px;
            color: {colors['text_strong']};
            selection-background-color: {colors['selection']};
        }}
        QLineEdit:focus {{ border-color: {colors['focus']}; }}
        QTreeWidget {{
            background: {colors['background']};
            alternate-background-color: {colors['alternate']};
            border: {px(1)}px solid {colors['border']};
            border-radius: {px(7)}px;
            selection-background-color: {colors['selection']};
            selection-color: {colors['text_strong']};
        }}
        QTreeView::item {{ padding: {px(4)}px; }}
        QTreeView::item:selected {{
            background: {colors['selection']};
            color: {colors['text_strong']};
        }}
        QTreeView::indicator {{
            border: {px(1)}px solid {colors['border']};
            border-radius: {px(3)}px;
            background: {colors['surface_alt']};
            width: {px(15)}px;
            height: {px(15)}px;
        }}
        QTreeView::indicator:checked {{
            background: {colors['accent']};
            border-color: {colors['accent']};
        }}
        QTableCornerButton::section {{
            background: {colors['surface_alt']};
            border: 0;
        }}
        QCheckBox {{ spacing: {px(6)}px; color: {colors['text']}; }}
        QCheckBox::indicator {{
            border: {px(1)}px solid {colors['border']};
            border-radius: {px(3)}px;
            background: {colors['surface_alt']};
            width: {px(15)}px;
            height: {px(15)}px;
        }}
        QCheckBox::indicator:checked {{
            background: {colors['accent']};
            border-color: {colors['accent']};
        }}
        QMenu {{
            background: {colors['surface']};
            border: {px(1)}px solid {colors['border']};
            color: {colors['text']};
            padding: {px(4)}px;
        }}
        QMenu::item {{ padding: {px(6)}px {px(14)}px; border-radius: {px(4)}px; }}
        QMenu::item:selected {{
            background: {colors['selection']};
            color: {colors['text_strong']};
        }}
        QMenu::separator {{
            height: {px(1)}px;
            background: {colors['border']};
            margin: {px(4)}px {px(8)}px;
        }}
        QGroupBox {{
            background: {colors['surface']};
            border: {px(1)}px solid {colors['border']};
            border-radius: {px(10)}px;
            margin-top: {pt(11)}pt;
            padding: {px(10)}px;
            font-weight: 600;
            color: {colors['text_strong']};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {px(10)}px;
            padding: 0 {px(5)}px;
            color: {colors['muted']};
        }}
        /* Базовая (нейтральная) кнопка: фоном заметно светлее окна,
           шрифт яркий. Ядро роутера выше не трогаем — эти правила побеждают
           по каскаду (тот же селектор, позже в файле). Состояния :disabled
           из ядра при этом сохраняются (псевдо-состояние специфичнее). */
        QPushButton {{
            min-height: {px(30)}px;
            background: {colors['surface_hover']};
            border: {px(1)}px solid {colors['primary']};
            color: {colors['text_strong']};
        }}
        QPushButton:hover {{
            background: {colors['primary_hover']};
            border-color: {colors['focus']};
        }}
        QPushButton:pressed {{ background: {colors['surface_pressed']}; }}
        QPushButton#start_btn {{
            color: {colors['on_accent']};
            background: {colors['accent']};
            border-color: {colors['accent']};
            font-weight: 700;
            min-height: {px(40)}px;
        }}
        QPushButton#start_btn:hover {{ background: {colors['accent_hover']}; }}
        QPushButton#start_btn:pressed {{ background: {colors['accent_pressed']}; }}
        QPushButton#danger_btn {{
            color: {colors['on_accent']};
            background: {colors['danger']};
            border-color: {colors['danger']};
        }}
        QPushButton#danger_btn:hover {{
            background: {colors['danger_text']};
            border-color: {colors['danger_text']};
        }}
        QPushButton#danger_btn:pressed {{
            background: {colors['danger_pressed']};
            border-color: {colors['danger_pressed']};
        }}
        QPushButton#success_btn {{
            color: {colors['on_accent']};
            background: {colors['success']};
            border-color: {colors['success']};
            font-weight: 600;
        }}
        QPushButton#success_btn:hover {{
            background: {colors['success_hover']};
            border-color: {colors['success_hover']};
        }}
        QPushButton#success_btn:pressed {{
            background: {colors['success']};
            border-color: {colors['success']};
        }}
        QPushButton#warning_btn {{
            color: {colors['on_accent']};
            background: {colors['warning']};
            border-color: {colors['warning']};
        }}
        QPushButton#warning_btn:hover {{
            background: {colors['warning_hover']};
            border-color: {colors['warning_hover']};
        }}
        QPushButton#warning_btn:pressed {{
            background: {colors['warning']};
            border-color: {colors['warning']};
        }}
    """
    return core + appendix


def apply_theme(
    app: QApplication,
    base_font_size: float = 11.0,
    scale_factor: float = 1.0,
    colors: dict[str, str] | None = None,
) -> None:
    """Применяет тему: шрифт Tahoma (запасные Segoe UI/Aptos) + глобальный QSS."""
    palette = dict(ROUTER_COLORS)
    if colors:
        palette.update(colors)
    font = QFont(app.font())
    font.setFamilies(["Tahoma", "Segoe UI", "Aptos"])
    app.setFont(font)
    app.setStyleSheet(
        build_global_stylesheet(palette, scale_factor, max(9.0, base_font_size))
    )


def enforce_button_proportions(buttons) -> None:
    """Правило геометрии кнопок: ширина >= высоты.

    Кнопка — либо квадрат, либо альбомный прямоугольник; «портрет»
    (уже, чем высота) запрещён. Икончатым кнопкам ставит
    min-width = текущей высоте: уже высоты стать нельзя, шире — можно.
    Вызывать после apply_theme и при каждой смене шрифта (метрики зависят
    от кегля). Минимум только растёт — при уменьшении кегля кнопки шире
    высоты всё равно не станут.
    """
    for btn in buttons:
        btn.setMinimumWidth(max(btn.minimumWidth(), btn.sizeHint().height()))
