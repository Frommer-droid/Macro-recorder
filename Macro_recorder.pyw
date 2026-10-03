import ctypes
import sys
import os

# Перенаправляем вывод в файл лога
if getattr(sys, "frozen", False):
    log_file = os.path.join(os.path.dirname(sys.executable), "debug.log")
    # Построчная буферизация: лог виден сразу и не теряется при аварийном завершении.
    sys.stdout = open(log_file, "w", encoding="utf-8", buffering=1)
    sys.stderr = sys.stdout
    print("=== DEBUG LOG START ===")


from app_theme import apply_theme, enforce_button_proportions

import datetime
import glob
import json
import tempfile
import shutil
import subprocess
import traceback
from ctypes import wintypes  # ctypes уже импортирован выше
from pynput import mouse
from pynput import keyboard
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QLineEdit,
    QInputDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSystemTrayIcon,
    QMenu,
    QMessageBox,
    QAbstractItemView,
    QStyle,
    QTreeWidgetItemIterator,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal, Slot, QObject, QEvent, QPoint, QTimer
from PySide6.QtGui import QFont, QPalette, QColor, QIcon, QPixmap, QPainter, QAction
from PySide6.QtNetwork import QLocalServer, QLocalSocket

# --- Импорт для работы с кнопками управления окном ---
try:
    import win32con

    WIN_LIBS_LOADED = True
except ImportError:
    WIN_LIBS_LOADED = False
    print("⚠️ Библиотека pywin32 не установлена.")


# --- Функция для получения пути к ресурсам ---
def resource_path(relative_path):
    """
    Возвращает корректный путь к ресурсу в режиме разработки и в скомпилированном приложении.
    """
    if getattr(sys, "frozen", False):
        # 1. Проверяем рядом с exe (для внешних ресурсов, скопированных post_build.py)
        base_path = os.path.dirname(sys.executable)
        possible_path = os.path.join(base_path, relative_path)
        if os.path.exists(possible_path):
            return possible_path

        # 2. Проверяем во временной папке PyInstaller (для встроенных ресурсов)
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)

    # В режиме разработки
    return os.path.join(os.path.abspath("."), relative_path)


def install_qt_ru_translation(app):
    """Устанавливает русскую локаль стандартных Qt-текстов (Copy/Paste, диалоги).

    Вызывать один раз после создания QApplication, до создания виджетов.
    Переводчик привязывается к app как родитель, поэтому сборщик мусора
    его не удалит. Отсутствие файла — не ошибка: приложение продолжит
    работу с английскими стандартными текстами.
    """
    from PySide6.QtCore import QLibraryInfo, QTranslator

    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, "_MEIPASS", exe_dir)
        candidates += [
            os.path.join(exe_dir, "translations", "qtbase_ru.qm"),
            os.path.join(exe_dir, "_internal", "translations", "qtbase_ru.qm"),
            os.path.join(meipass, "translations", "qtbase_ru.qm"),
            os.path.join(meipass, "qtbase_ru.qm"),
        ]
    else:
        # Режим разработки: перевод рядом с установленным PySide6.
        try:
            import PySide6

            _pyside_dir = os.path.dirname(PySide6.__file__)
            candidates += [
                os.path.join(_pyside_dir, "translations", "qtbase_ru.qm"),
                os.path.join(_pyside_dir, "Qt", "translations", "qtbase_ru.qm"),
            ]
        except Exception:
            pass
    # Системный путь переводов Qt — последний шанс.
    try:
        candidates.append(
            os.path.join(
                QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
                "qtbase_ru.qm",
            )
        )
    except Exception:
        pass

    for path in candidates:
        if path and os.path.exists(path):
            translator = QTranslator(app)
            if translator.load(path):
                app.installTranslator(translator)
                print(f"[OK] Russian Qt locale loaded: {path}")
                return
    print("[SKIP] qtbase_ru.qm not found, Qt standard strings stay in English")


# --- Тема приложения: пакет app_theme (палитра роутера), см. apply_styles ---


# --- Windows API для управления раскладкой клавиатуры ---
try:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    LoadKeyboardLayoutW = user32.LoadKeyboardLayoutW
    LoadKeyboardLayoutW.argtypes = [wintypes.LPCWSTR, wintypes.UINT]
    LoadKeyboardLayoutW.restype = wintypes.HKL
    ActivateKeyboardLayout = user32.ActivateKeyboardLayout
    ActivateKeyboardLayout.argtypes = [wintypes.HKL, wintypes.UINT]
    ActivateKeyboardLayout.restype = wintypes.HKL
    GetKeyboardLayout = user32.GetKeyboardLayout
    GetKeyboardLayout.argtypes = [wintypes.DWORD]
    GetKeyboardLayout.restype = wintypes.HKL
    UnloadKeyboardLayout = user32.UnloadKeyboardLayout
    UnloadKeyboardLayout.argtypes = [wintypes.HKL]
    UnloadKeyboardLayout.restype = wintypes.BOOL
    KLF_ACTIVATE = 0x00000001
    LAYOUT_SWITCH_ENABLED = True
except (ImportError, AttributeError, OSError):
    print("Не удалось загрузить Windows API.")
    LAYOUT_SWITCH_ENABLED = False


# ===== Класс: BackgroundRecorder =====
class BackgroundRecorder(QObject):
    recording_finished = Signal(list)
    recording_started = Signal()
    recording_stopped = Signal()
    MODIFIER_KEYS = {
        keyboard.Key.ctrl,
        keyboard.Key.ctrl_l,
        keyboard.Key.ctrl_r,
        keyboard.Key.alt,
        keyboard.Key.alt_l,
        keyboard.Key.alt_r,
        keyboard.Key.shift,
        keyboard.Key.shift_l,
        keyboard.Key.shift_r,
        keyboard.Key.cmd,
        keyboard.Key.cmd_l,
        keyboard.Key.cmd_r,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.actions, self.is_recording = [], False
        self.pressed_keys = set()
        self.mouse_listener, self.keyboard_listener = None, None
        self.original_layout, self.existing_actions = None, []
        self.english_layout_handle = None

    def _switch_to_english_layout(self):
        if not LAYOUT_SWITCH_ENABLED:
            return
        try:
            self.original_layout = GetKeyboardLayout(0)
            hkl = LoadKeyboardLayoutW("00000409", KLF_ACTIVATE)
            if hkl:
                self.english_layout_handle = hkl
                ActivateKeyboardLayout(hkl, KLF_ACTIVATE)
        except Exception as e:
            print(f"Ошибка переключения раскладки: {e}")

    def _restore_original_layout(self):
        if not LAYOUT_SWITCH_ENABLED or not self.original_layout:
            return
        try:
            ActivateKeyboardLayout(self.original_layout, KLF_ACTIVATE)
            if self.english_layout_handle:
                UnloadKeyboardLayout(self.english_layout_handle)
                self.english_layout_handle = None
            self.original_layout = None
        except Exception as e:
            print(f"Ошибка восстановления раскладки: {e}")

    def get_key_name(self, key):
        if isinstance(key, keyboard.Key):
            return key.name
        if hasattr(key, "vk") and key.vk is not None:
            return f"vk_{key.vk}"
        return str(key)

    def on_click(self, x, y, button, pressed):
        if pressed and self.is_recording:
            self.actions.append(
                {"type": "click", "x": x, "y": y, "button": button.name, "delay": 1.0}
            )

    def on_press(self, key):
        if not self.is_recording:
            return
        if key == keyboard.Key.esc:
            self.stop()
            return False
        self.pressed_keys.add(key)

    def on_release(self, key):
        if not self.is_recording:
            return
        if key in self.pressed_keys and key not in self.MODIFIER_KEYS:
            modifiers = sorted(
                [k for k in self.pressed_keys if k in self.MODIFIER_KEYS],
                key=lambda k: str(k),
            )
            key_names = [self.get_key_name(m) for m in modifiers] + [
                self.get_key_name(key)
            ]
            self.actions.append(
                {
                    "type": "key_press",
                    "key": "+".join(filter(None, key_names)),
                    "delay": 1.0,
                }
            )
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    @Slot()
    def start(self, mode="full", existing_actions=None):
        if self.is_recording:
            return
        self.is_recording, self.actions = True, []
        self.existing_actions = existing_actions if mode == "continue" else []
        self._switch_to_english_layout()
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        )
        self.mouse_listener.start()
        self.keyboard_listener.start()
        self.recording_started.emit()

    @Slot()
    def stop(self):
        if not self.is_recording:
            return
        self.is_recording = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        self.mouse_listener, self.keyboard_listener = None, None
        self._restore_original_layout()
        self.recording_finished.emit(self.existing_actions + self.actions)
        self.recording_stopped.emit()


class SessionTreeWidget(QTreeWidget):
    orderChanged = Signal()

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.sessions_dir = main_window.sessions_dir

    def dropEvent(self, event):
        source_items = self.selectedItems()
        source_paths = [item.data(0, Qt.UserRole) for item in source_items]
        current_session_path = self.main_window.current_session_file
        new_session_path = None
        super().dropEvent(event)
        for i, item in enumerate(source_items):
            src_path = source_paths[i]
            dest_parent_item = item.parent() or self.invisibleRootItem()
            dest_dir = (
                self.sessions_dir
                if dest_parent_item == self.invisibleRootItem()
                else dest_parent_item.data(0, Qt.UserRole)
            )
            dest_path = os.path.join(dest_dir, os.path.basename(src_path))
            if src_path != dest_path:
                try:
                    shutil.move(src_path, dest_path)
                    self.update_item_paths_recursively(item, dest_path)
                    if current_session_path == src_path:
                        new_session_path = dest_path
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "Ошибка перемещения",
                        f"Не удалось переместить {os.path.basename(src_path)}: {e}",
                    )
                    self.main_window.populate_session_tree()
                    return
        if new_session_path:
            self.main_window.current_session_file = new_session_path
        self.orderChanged.emit()

    def update_item_paths_recursively(self, item, new_path):
        item.setData(0, Qt.UserRole, new_path)
        if os.path.isdir(new_path):
            for i in range(item.childCount()):
                child = item.child(i)
                self.update_item_paths_recursively(
                    child,
                    os.path.join(
                        new_path, os.path.basename(child.data(0, Qt.UserRole))
                    ),
                )


# === КЛАСС: Сервис воспроизведения на базе AutoHotkey ===
class PlaybackService(QObject):
    def __init__(self, sessions_dir):
        super().__init__()
        self.sessions_dir = sessions_dir
        self.ahk_process = None
        self.temp_dir = tempfile.mkdtemp(prefix="MacroRecorderAHK_")
        self.ahk_script_path = os.path.join(self.temp_dir, "macro_runner.ahk")
        self.macro_player_path = self._get_macro_player_path()

    def _get_macro_player_path(self):
        """Возвращает путь к macro_player.exe с учетом PyInstaller."""
        filename = "macro_player.exe"
        
        if getattr(sys, "frozen", False):
            # 1. Рядом с exe (приоритет)
            exe_dir = os.path.dirname(sys.executable)
            path = os.path.join(exe_dir, filename)
            if os.path.exists(path):
                return path
                
            # 2. Внутри _internal (если onedir)
            path = os.path.join(exe_dir, "_internal", filename)
            if os.path.exists(path):
                return path
                
            # 3. В _MEIPASS (если onefile)
            if hasattr(sys, "_MEIPASS"):
                path = os.path.join(sys._MEIPASS, filename)
                if os.path.exists(path):
                    return path
        else:
            # В разработке
            return os.path.abspath(filename)

        return None

    def _get_stop_sound_path(self):
        """Путь к звуку окончания воспроизведения (Assets/stop.mp3)."""
        relative = os.path.join("Assets", "stop.mp3")
        if getattr(sys, "frozen", False):
            path = os.path.join(os.path.dirname(sys.executable), relative)
        else:
            path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), relative
            )
        return path if os.path.exists(path) else None

    def _translate_hotkey_to_ahk(self, hotkey_str):
        """Преобразует внутренний формат hotkey в формат AHK v2."""
        if not hotkey_str:
            return None

        parts = hotkey_str.lower().split("+")

        AHK_MODIFIER_MAP = {"ctrl": "^", "alt": "!", "shift": "+", "cmd": "#"}

        ahk_parts = []

        for part in parts:
            # Убираем суффиксы _l, _r
            clean_part = part.rsplit("_", 1)[0] if "_" in part else part

            # Обрабатываем vk_ коды
            if part.startswith("vk_"):
                try:
                    vk_code = int(part[3:])
                    hex_code = format(vk_code, "X")
                    ahk_parts.append(f"vk{hex_code}")
                    continue
                except (ValueError, TypeError):
                    pass

            # Модификаторы
            if clean_part in AHK_MODIFIER_MAP:
                ahk_parts.append(AHK_MODIFIER_MAP[clean_part])
            else:
                # Основная клавиша
                KEY_MAP = {
                    "page_up": "PgUp",
                    "page_down": "PgDn",
                    "esc": "Escape",
                    "space": "Space",
                    "enter": "Enter",
                    "tab": "Tab",
                    "backspace": "Backspace",
                    "delete": "Delete",
                }
                ahk_parts.append(KEY_MAP.get(part, part.upper()))

        return "".join(ahk_parts)

    @Slot()
    def reload_sessions(self):
        """Перезагружает все сессии и генерирует AHK скрипт."""

        # Останавливаем предыдущий процесс
        if self.ahk_process and self.ahk_process.poll() is None:
            try:
                self.ahk_process.terminate()
                self.ahk_process.wait(timeout=2)
            except:
                pass

        if not self.macro_player_path or not os.path.exists(self.macro_player_path):
            print("⚠️ macro_player.exe не найден!")
            return

        # Генерируем AHK скрипт
        ahk_script_content = "#Requires AutoHotkey v2.0\n"
        ahk_script_content += "#SingleInstance Force\n"
        ahk_script_content += "#NoTrayIcon\n\n"

        hotkey_count = 0

        # Сканируем все JSON файлы
        for filepath in glob.glob(
            os.path.join(self.sessions_dir, "**", "*.json"), recursive=True
        ):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if hotkey := data.get("hotkey"):
                    ahk_hotkey = self._translate_hotkey_to_ahk(hotkey)
                    if not ahk_hotkey:
                        continue

                    # Экранируем пути
                    escaped_player = self.macro_player_path.replace("\\", "\\\\")
                    escaped_session = filepath.replace("\\", "\\\\")
                    stop_sound = self._get_stop_sound_path()
                    escaped_sound = (
                        stop_sound.replace("\\", "\\\\") if stop_sound else ""
                    )

                    def _play_lines(indent):
                        # RunWait ждёт конца воспроизведения (заодно не даёт
                        # наложиться повторному нажатию), SoundPlay асинхронен.
                        lines = f'{indent}RunWait(\'"{escaped_player}" "{escaped_session}"\', , "Hide")\n'
                        if escaped_sound:
                            lines += f'{indent}SoundPlay "{escaped_sound}"\n'
                        return lines

                    # Формируем hotkey
                    ahk_script_content += (
                        f"; {ahk_hotkey} -> {os.path.basename(filepath)}\n"
                    )
                    ahk_script_content += f"{ahk_hotkey}:: {{\n"

                    if window_title := data.get("window_title", ""):
                        escaped_title = window_title.replace('"', '""')
                        ahk_script_content += (
                            f'    if (WinActive("{escaped_title}")) {{\n'
                        )
                        ahk_script_content += _play_lines("        ")
                        ahk_script_content += "    }\n"
                    else:
                        ahk_script_content += _play_lines("    ")

                    ahk_script_content += "}\n\n"
                    hotkey_count += 1
                    print(f"✓ Добавлен: {ahk_hotkey} -> {os.path.basename(filepath)}")
            except Exception as e:
                print(f"Ошибка: {e}")

        # F12 для выхода
        ahk_script_content += "F12::ExitApp\n"

        # Сохраняем скрипт
        try:
            with open(self.ahk_script_path, "w", encoding="utf-8-sig") as f:
                f.write(ahk_script_content)
            print(f"✓ Скрипт сохранен: {self.ahk_script_path}")
        except Exception as e:
            print(f"Ошибка сохранения скрипта: {e}")
            return

        # Находим AutoHotkey
        autohotkey_path = self._find_autohotkey_executable()

        if not autohotkey_path:
            print("⚠️ AutoHotkey не найден!")
            return

        print(f"✓ Используется: {autohotkey_path}")

        # Запускаем
        try:
            import subprocess

            self.ahk_process = subprocess.Popen(
                [autohotkey_path, self.ahk_script_path],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            print(f"✓ Процесс запущен, PID: {self.ahk_process.pid}")
            print(f"✓ Загружено {hotkey_count} горячих клавиш")

        except Exception as e:
            print(f"❌ Ошибка запуска: {e}")

    def _find_autohotkey_executable(self):
        """Ищет AutoHotkey.exe в стандартных путях."""
        locations = [
            r"C:\Program Files\AutoHotkey\v2\AutoHotkey.exe",
            r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe",
            os.path.expanduser(
                r"~\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey.exe"
            ),
        ]
        
        # Если запущено скомпилированное приложение, ищем рядом с exe
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            locations.insert(0, os.path.join(exe_dir, "AutoHotkey.exe"))
            locations.insert(0, os.path.join(exe_dir, "tools", "AutoHotkey.exe"))

        for loc in locations:
            if os.path.exists(loc):
                return loc

        # Поиск в PATH
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            full_path = os.path.join(path_dir, "AutoHotkey.exe")
            if os.path.exists(full_path):
                return full_path

        return None

    def stop(self):
        """Останавливает сервис."""
        if self.ahk_process and self.ahk_process.poll() is None:
            try:
                self.ahk_process.terminate()
            except:
                pass

        try:
            shutil.rmtree(self.temp_dir)
        except OSError:
            pass


class HotkeyCaptureOverlay(QWidget):
    hotkey_captured = Signal(str)
    MODIFIER_KEYS = {
        keyboard.Key.ctrl,
        keyboard.Key.ctrl_l,
        keyboard.Key.ctrl_r,
        keyboard.Key.alt,
        keyboard.Key.alt_l,
        keyboard.Key.alt_r,
        keyboard.Key.shift,
        keyboard.Key.shift_l,
        keyboard.Key.shift_r,
        keyboard.Key.cmd,
        keyboard.Key.cmd_l,
        keyboard.Key.cmd_r,
    }

    def __init__(self):
        super().__init__()
        (
            self.is_stopping,
            self.pressed_keys,
            self.mouse_listener,
            self.keyboard_listener,
            self.original_layout,
        ) = (False, set(), None, None, None)
        self.english_layout_handle = None
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.setWindowOpacity(0.3)
        p = self.palette()
        p.setColor(QPalette.Window, QColor("black"))
        self.setPalette(p)
        label = QLabel("Нажмите горячую клавишу или сочетание...", self)
        label.setFont(QFont("Arial", 20))
        label.setAlignment(Qt.AlignCenter)
        tp = label.palette()
        tp.setColor(QPalette.WindowText, QColor("white"))
        label.setPalette(tp)
        QVBoxLayout(self).addWidget(label)

    def _switch_to_english_layout(self):
        if not LAYOUT_SWITCH_ENABLED:
            return
        try:
            self.original_layout = GetKeyboardLayout(0)
            hkl = LoadKeyboardLayoutW("00000409", KLF_ACTIVATE)
            if hkl:
                self.english_layout_handle = hkl
                ActivateKeyboardLayout(hkl, KLF_ACTIVATE)
        except Exception as e:
            print(f"Error switching layout: {e}")

    def _restore_original_layout(self):
        if not LAYOUT_SWITCH_ENABLED or not self.original_layout:
            return
        try:
            ActivateKeyboardLayout(self.original_layout, KLF_ACTIVATE)
            if self.english_layout_handle:
                UnloadKeyboardLayout(self.english_layout_handle)
                self.english_layout_handle = None
            self.original_layout = None
        except Exception as e:
            print(f"Error restoring layout: {e}")

    def start_listeners(self):
        if not self.mouse_listener:
            self.mouse_listener = mouse.Listener(on_click=self.on_click)
            self.mouse_listener.start()
        if not self.keyboard_listener:
            self.keyboard_listener = keyboard.Listener(
                on_press=self.on_press, on_release=self.on_release
            )
            self.keyboard_listener.start()

    def showEvent(self, event):
        self._switch_to_english_layout()
        super().showEvent(event)
        self.start_listeners()

    def get_key_name(self, key):
        if isinstance(key, keyboard.Key):
            return key.name
        if hasattr(key, "vk") and key.vk is not None:
            return f"vk_{key.vk}"
        return str(key)

    def on_click(self, x, y, button, pressed):
        pass

    def on_press(self, key):
        if key == keyboard.Key.esc:
            self.stop_recording()
            return False
        self.pressed_keys.add(key)

    def on_release(self, key):
        if key in self.pressed_keys:
            if key in self.MODIFIER_KEYS and len(self.pressed_keys) == 1:
                if key in self.pressed_keys:
                    self.pressed_keys.remove(key)
                    return
            main_key = list(self.pressed_keys - self.MODIFIER_KEYS)
            if not main_key:
                if key in self.pressed_keys:
                    self.pressed_keys.remove(key)
                    return
            modifiers = sorted(
                [k for k in self.pressed_keys if k in self.MODIFIER_KEYS],
                key=lambda k: str(k),
            )
            key_names = [self.get_key_name(m) for m in modifiers] + [
                self.get_key_name(main_key[0])
            ]
            self.hotkey_captured.emit("+".join(filter(None, key_names)))
            self.stop_recording()
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    @Slot()
    def stop_recording(self):
        if self.is_stopping:
            return
        self.is_stopping = True
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        self._restore_original_layout()
        self.close()


class MainWindow(QWidget):
    VK_TO_CHAR = {
        **{i: chr(i) for i in range(65, 91)},
        **{i: str(i - 48) for i in range(48, 58)},
        **{i: f"Numpad{i - 96}" for i in range(96, 106)},
        **{i: f"F{i - 111}" for i in range(112, 124)},
        186: ";",
        187: "=",
        188: ",",
        189: "-",
        190: ".",
        191: "/",
        192: "`",
        219: "[",
        220: "\\",
        221: "]",
        222: "'",
        8: "Backspace",
        9: "Tab",
        13: "Enter",
        20: "CapsLock",
        27: "Esc",
        32: "Space",
        33: "PageUp",
        34: "PageDown",
        35: "End",
        36: "Home",
        37: "Left",
        38: "Up",
        39: "Right",
        40: "Down",
        45: "Insert",
        46: "Delete",
        110: "NumpadDel",
    }

    def __init__(self, playback_service):
        super().__init__()
        self._is_initializing = True
        self._is_handling_check = False
        self._left_width_frozen = False
        self._table_width = 0
        self._col_floors: dict = {}
        self.is_closing = False
        self.right_click_on_close = False

        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.sessions_dir = os.path.join(self.script_dir, "Sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)
        self.playback_service = playback_service
        self.playback_service.sessions_dir = self.sessions_dir
        self.background_recorder = BackgroundRecorder()
        self.background_recorder.recording_started.connect(self.on_recording_started)
        self.background_recorder.recording_stopped.connect(self.on_recording_stopped)
        self._last_geometry = None
        self.current_session_file = None
        self.font_size = 11
        
        # Инициализируем атрибут overlay как None
        self.hotkey_capture_overlay = None
        
        # Устанавливаем иконку окна
        icon_path = resource_path("logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            print(f"✓ Иконка установлена: {icon_path}")
        else:
            print(f"⚠️ Файл иконки не найден: {icon_path}")
        
        self.init_ui()
        QTimer.singleShot(200, self.init_tray_icon)
        self.load_settings()
        self.populate_session_tree()
        self.post_load_select_session()
        self._is_initializing = False

        # ========== ДОБАВЬТЕ ЭТУ ПРОВЕРКУ ==========
        # Если включен запуск свернутым - прячем окно через задержку
        if self.start_minimized_action.isChecked():
            QTimer.singleShot(800, self.hide)
        # ===========================================

    def nativeEvent(self, eventType, message):
        if WIN_LIBS_LOADED and eventType == "windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == win32con.WM_NCRBUTTONDOWN:
                if msg.wParam == 20:
                    self.right_click_on_close = True
                    self.hide()
                    if hasattr(self, "tray_icon"):
                        self.tray_icon.showMessage(
                            "Регистратор действий",
                            "Приложение свернуто в системный трей",
                            QSystemTrayIcon.MessageIcon.Information,
                            2000,
                        )
                    return True, 0
            if msg.message == win32con.WM_SYSCOMMAND:
                if msg.wParam == win32con.SC_CLOSE:
                    if not self.right_click_on_close:
                        self.quit_application()
                        return True, 0
                    else:
                        self.right_click_on_close = False
                        return True, 0
                elif msg.wParam == win32con.SC_MINIMIZE:
                    self.showMinimized()
                    return True, 0
        return super().nativeEvent(eventType, message)

    def quit_application(self):
        self.is_closing = True
        self.save_settings()
        self.playback_service.stop()
        QApplication.instance().quit()

    def hideEvent(self, event):
        if not self.isMinimized():
            self._last_geometry = self.geometry()
        super().hideEvent(event)

    def showEvent(self, event):
        if self._last_geometry and not self.isMaximized():
            self.setGeometry(self._last_geometry)
        super().showEvent(event)

    def format_key_string_for_display(self, key_str):
        if not key_str:
            return ""
        formatted_parts = []
        for part in key_str.split("+"):
            clean_part = part.strip()
            if clean_part.startswith("vk_"):
                try:
                    vk_code = int(clean_part[3:])
                    formatted_parts.append(self.VK_TO_CHAR.get(vk_code, clean_part))
                except (ValueError, TypeError):
                    formatted_parts.append(clean_part)
            else:
                formatted_parts.append(clean_part.replace("_", " ").capitalize())
        return "+".join(formatted_parts)

    def create_tray_icon(self, color="dodgerblue"):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()
        return QIcon(pixmap)

    def init_tray_icon(self):
        # Используем иконку приложения для трея, если она есть
        icon_path = resource_path("logo.ico")
        if os.path.exists(icon_path):
            self.normal_icon = QIcon(icon_path)
            print(f"✓ Иконка трея установлена: {icon_path}")
        else:
            # Используем сгенерированную иконку как fallback
            self.normal_icon = self.create_tray_icon("dodgerblue")
            print("⚠️ Используется сгенерированная иконка для трея")
        
        self.recording_icon = self.create_tray_icon("red")
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.normal_icon)
        self.tray_icon.setToolTip("Регистратор действий")
        tray_menu = QMenu()
        self.show_hide_action = QAction("Показать", self)
        self.show_hide_action.triggered.connect(self.show_hide_window)
        tray_menu.addAction(self.show_hide_action)
        tray_menu.addSeparator()
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    @Slot()
    def show_hide_window(self):
        if self.isVisible():
            self.hide()
            self.show_hide_action.setText("Показать")
        else:
            self.show()
            self.activateWindow()
            self.raise_()
            self.show_hide_action.setText("Скрыть")

    @Slot(QSystemTrayIcon.ActivationReason)
    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show()
            self.activateWindow()
            self.show_hide_action.setText("Скрыть")

    def init_ui(self):
        self.setWindowTitle("Регистратор и воспроизводитель действий")
        self._create_context_menu_actions()
        self.main_v_layout = QVBoxLayout(self)
        self.main_v_layout.setContentsMargins(10, 10, 10, 10)
        self.main_v_layout.setSpacing(6)

        # --- Top Bar (Settings) ---
        top_bar_layout = QHBoxLayout()

        self.settings_button = QPushButton("Настройки")
        self.settings_button.setFixedWidth(150)  # Increased width to fit text

        # Create Menu
        settings_menu = QMenu(self)
        font_size_menu = settings_menu.addMenu("Размер шрифта")

        font_sizes = [10, 11, 12, 13, 14, 16, 18, 20]
        for size in font_sizes:
            action = QAction(f"{size} pt", self)
            # Use default argument to capture loop variable
            action.triggered.connect(lambda checked=False, s=size: self.set_font_size(s))
            font_size_menu.addAction(action)

        settings_menu.addSeparator()
        self.autostart_action = QAction("Автозапуск при входе в Windows", self)
        self.autostart_action.setCheckable(True)
        self.autostart_action.toggled.connect(
            lambda checked: self.on_autostart_changed(
                Qt.Checked if checked else Qt.Unchecked
            )
        )
        settings_menu.addAction(self.autostart_action)
        self.start_minimized_action = QAction("Запускать свернутым в трей", self)
        self.start_minimized_action.setCheckable(True)
        self.start_minimized_action.toggled.connect(
            lambda checked: self.on_start_minimized_changed(
                Qt.Checked if checked else Qt.Unchecked
            )
        )
        settings_menu.addAction(self.start_minimized_action)

        self.settings_button.setMenu(settings_menu)
        top_bar_layout.addWidget(self.settings_button)
        top_bar_layout.addStretch()  # Push remaining space to the right

        self.main_v_layout.addLayout(top_bar_layout)
        main_content_widget = QWidget()
        main_layout = QHBoxLayout(main_content_widget)
        self.left_widget = QWidget()
        left_layout = QVBoxLayout(self.left_widget)
        self.start_button = QPushButton("Начать новую запись")
        self.start_button.setObjectName("start_btn")
        self.start_button.clicked.connect(self.start_recording)
        # Подписи и поля — прямо на тёмном фоне панели, без карточки.
        key_label = QLabel("Клавиша")
        key_label.setObjectName("muted")
        left_layout.addWidget(key_label)
        hotkey_layout = QHBoxLayout()
        self.hotkey_input = QLineEdit()
        self.capture_hotkey_button = QPushButton("⌨️")
        self.capture_hotkey_button.setToolTip("Захватить горячую клавишу")
        self.capture_hotkey_button.clicked.connect(self.start_hotkey_capture)
        self.clear_hotkey_button = QPushButton("❌")
        self.clear_hotkey_button.setToolTip("Удалить горячую клавишу")
        self.clear_hotkey_button.clicked.connect(self.clear_hotkey)
        hotkey_layout.addWidget(self.hotkey_input)
        hotkey_layout.addWidget(self.capture_hotkey_button)
        hotkey_layout.addWidget(self.clear_hotkey_button)
        left_layout.addLayout(hotkey_layout)
        title_label = QLabel("Заголовок окна")
        title_label.setObjectName("muted")
        left_layout.addWidget(title_label)
        self.window_title_input = QLineEdit()
        left_layout.addWidget(self.window_title_input)
        self.save_button = QPushButton("Сохранить изменения")
        self.save_button.setObjectName("success_btn")
        self.save_button.clicked.connect(self.update_current_session)
        # Автозапуск переехал в выпадающее меню «Настройки» (см. top bar).
        actions_group = QGroupBox("Последовательность действий")
        actions_layout = QVBoxLayout(actions_group)
        self.action_table = QTableWidget()
        self.action_table.setColumnCount(5)
        self.action_table.setHorizontalHeaderLabels(
            ["Тип", "Детали", "X", "Y", "Пауза (с)"]
        )
        action_header = self.action_table.horizontalHeader()
        # Все колонки — Interactive: resizeColumnsToContents подгоняет их
        # под текущий контент, а полы в _fit_action_table_width не дают
        # сужаться (храповик: клики не двигают геометрию никогда).
        # X/Y: минимум под 4 цифры ставит _enforce_coordinate_minimums.
        for _col in range(5):
            action_header.setSectionResizeMode(_col, QHeaderView.Interactive)
        vheader = self.action_table.verticalHeader()
        # Ширина заголовка строк — константа (до 999 строк без изменений).
        vheader.setMinimumWidth(
            vheader.fontMetrics().horizontalAdvance("888") + 16
        )
        for _col in (0, 1, 4):
            action_header.setSectionResizeMode(_col, QHeaderView.ResizeToContents)
        for _col in (2, 3):
            action_header.setSectionResizeMode(_col, QHeaderView.Interactive)
        self.action_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.action_table.itemSelectionChanged.connect(self.update_action_buttons_state)
        # Колонки таблицы всегда держатся по контенту.
        table_model = self.action_table.model()
        table_model.rowsInserted.connect(
            lambda *args: self._fit_action_table_width()
        )
        table_model.rowsRemoved.connect(
            lambda *args: self._fit_action_table_width()
        )
        self.action_table.verticalScrollBar().rangeChanged.connect(
            lambda *args: self._fit_action_table_width()
        )
        self.duplicate_selected_button = QPushButton("Дублировать")
        self.duplicate_selected_button.clicked.connect(self.duplicate_selected_actions)
        self.delete_selected_button = QPushButton("Удалить")
        self.delete_selected_button.setObjectName("danger_btn")
        self.delete_selected_button.clicked.connect(self.delete_selected_actions)
        self.move_up_button = QPushButton("↑")
        self.move_up_button.clicked.connect(self.move_actions_up)
        self.move_down_button = QPushButton("↓")
        self.move_down_button.clicked.connect(self.move_actions_down)
        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.addWidget(self.duplicate_selected_button)
        action_buttons_layout.addWidget(self.delete_selected_button)
        action_buttons_layout.addStretch()
        action_buttons_layout.addWidget(self.move_up_button)
        action_buttons_layout.addWidget(self.move_down_button)
        actions_layout.addWidget(self.action_table)
        actions_layout.addLayout(action_buttons_layout)
        left_layout.addWidget(actions_group)
        # Большая синяя кнопка — в самом низу левой панели,
        # под ней — зелёная «Сохранить изменения».
        left_layout.addWidget(self.start_button)
        left_layout.addWidget(self.save_button)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        sessions_group = QGroupBox("Сохраненные сессии")
        sessions_layout = QVBoxLayout(sessions_group)
        self.session_tree = SessionTreeWidget(self)
        self.session_tree.setHeaderHidden(False)
        self.session_tree.setColumnCount(2)
        self.session_tree.setHeaderLabels(["Название", "Клавиша"])
        header = self.session_tree.header()
        # Без этого последняя секция («Клавиша») принудительно растягивается
        # на полдерева (дефолт Qt), игнорируя режим колонки.
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.session_tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.session_tree.setDragEnabled(True)
        self.session_tree.setAcceptDrops(True)
        self.session_tree.setDropIndicatorShown(True)
        self.session_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.session_tree.customContextMenuRequested.connect(
            self.show_session_tree_context_menu
        )
        self.session_tree.currentItemChanged.connect(self.on_current_item_changed)
        self.session_tree.itemChanged.connect(self.on_session_item_changed)
        self.session_tree.itemSelectionChanged.connect(
            self.update_session_buttons_state
        )
        self.session_tree.orderChanged.connect(self.save_settings)
        self.session_tree.itemExpanded.connect(self.save_settings)
        self.session_tree.itemCollapsed.connect(self.save_settings)
        file_management_layout = QHBoxLayout()
        self.new_folder_button = QPushButton("Новая папка")
        self.new_folder_button.clicked.connect(self.create_new_folder)
        self.rename_item_button = QPushButton("Переименовать")
        self.rename_item_button.clicked.connect(self.rename_selected_item)
        self.delete_item_button = QPushButton("Удалить")
        self.delete_item_button.setObjectName("danger_btn")
        self.delete_item_button.clicked.connect(self.delete_selected_items)
        file_management_layout.addWidget(self.new_folder_button)
        file_management_layout.addWidget(self.rename_item_button)
        file_management_layout.addWidget(self.delete_item_button)
        session_actions_layout = QHBoxLayout()
        self.overwrite_session_button = QPushButton("Перезаписать")
        self.overwrite_session_button.setObjectName("warning_btn")
        self.overwrite_session_button.clicked.connect(self.overwrite_current_session)
        self.continue_session_button = QPushButton("Продолжить")
        self.continue_session_button.setObjectName("success_btn")
        self.continue_session_button.clicked.connect(self.continue_current_session)
        self.duplicate_session_button = QPushButton("Дублировать")
        self.duplicate_session_button.clicked.connect(self.duplicate_current_session)
        session_actions_layout.addWidget(self.overwrite_session_button)
        session_actions_layout.addWidget(self.continue_session_button)
        session_actions_layout.addWidget(self.duplicate_session_button)
        tree_move_buttons_layout = QHBoxLayout()
        self.move_item_up_button = QPushButton("↑")
        self.move_item_up_button.clicked.connect(self.move_items_up)
        self.move_item_down_button = QPushButton("↓")
        self.move_item_down_button.clicked.connect(self.move_items_down)
        tree_move_buttons_layout.addWidget(self.move_item_up_button)
        tree_move_buttons_layout.addWidget(self.move_item_down_button)
        sessions_layout.addWidget(self.session_tree)
        sessions_layout.addLayout(file_management_layout)
        sessions_layout.addLayout(session_actions_layout)
        sessions_layout.addLayout(tree_move_buttons_layout)
        right_layout.addWidget(sessions_group)
        right_widget.setLayout(right_layout)
        main_layout.addWidget(self.left_widget, 0)
        main_layout.addWidget(right_widget, 1)
        self.main_v_layout.addWidget(main_content_widget)
        self.update_action_buttons_state()
        self.update_session_buttons_state()
        self._fit_action_table_width()
        # Икончатые кнопки — квадратные (правило: ширина >= высоты).
        self._square_icon_buttons = [
            self.capture_hotkey_button,
            self.clear_hotkey_button,
            self.move_up_button,
            self.move_down_button,
        ]
        self.apply_styles()

    def _create_context_menu_actions(self):
        self.rename_action = QAction("Переименовать (F2)", self)
        self.rename_action.triggered.connect(self.rename_selected_item)
        self.delete_action = QAction("Удалить (Del)", self)
        self.delete_action.triggered.connect(self.delete_selected_items)
        self.cut_action = QAction("Вырезать (Ctrl+X)", self)
        self.cut_action.triggered.connect(self.cut_selected_items)
        self.copy_action = QAction("Копировать (Ctrl+C)", self)
        self.copy_action.triggered.connect(self.copy_selected_items)
        self.paste_action = QAction("Вставить (Ctrl+V)", self)
        self.paste_action.triggered.connect(self.paste_items)
        self.duplicate_context_action = QAction("Дублировать", self)
        self.duplicate_context_action.triggered.connect(self.duplicate_current_session)

    @Slot(QPoint)
    def show_session_tree_context_menu(self, position):
        menu = QMenu(self)
        selected_items = self.session_tree.selectedItems()
        count = len(selected_items)
        is_single_file = count == 1 and os.path.isfile(
            selected_items[0].data(0, Qt.UserRole)
        )
        self.rename_action.setEnabled(count == 1)
        self.delete_action.setEnabled(count > 0)
        self.cut_action.setEnabled(count > 0)
        self.copy_action.setEnabled(count > 0)
        self.paste_action.setEnabled(
            hasattr(self, "clipboard_paths") and bool(self.clipboard_paths)
        )
        self.duplicate_context_action.setEnabled(is_single_file)
        menu.addAction(self.rename_action)
        menu.addAction(self.delete_action)
        menu.addSeparator()
        menu.addAction(self.cut_action)
        menu.addAction(self.copy_action)
        menu.addAction(self.paste_action)
        menu.addAction(self.duplicate_context_action)
        menu.exec(self.session_tree.viewport().mapToGlobal(position))

    @Slot(QTreeWidgetItem, int)
    def on_session_item_changed(self, item, column):
        if self._is_handling_check or column != 0:
            return
        if item.checkState(0) == Qt.Checked:
            self.handle_selection(item)

    def populate_session_tree(self):
        self.session_tree.clear()
        ordered_paths = getattr(self, "tree_order_to_load", [])
        path_to_item, processed_paths = {}, set()

        def add_items_from_list(paths):
            for path in paths:
                if not os.path.exists(path) or path in processed_paths:
                    continue
                parent_path = os.path.dirname(path)
                parent_item = path_to_item.get(
                    parent_path, self.session_tree.invisibleRootItem()
                )
                is_dir = os.path.isdir(path)
                display_name = (
                    os.path.basename(path)
                    if is_dir
                    else os.path.splitext(os.path.basename(path))[0]
                )
                item = QTreeWidgetItem(parent_item)
                item.setText(0, display_name)
                item.setData(0, Qt.UserRole, path)
                item.setIcon(
                    0,
                    self.style().standardIcon(
                        QStyle.SP_DirIcon if is_dir else QStyle.SP_FileIcon
                    ),
                )
                if not is_dir:
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.Unchecked)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        item.setText(
                            1,
                            self.format_key_string_for_display(data.get("hotkey", "")),
                        )
                    except Exception as e:
                        print(f"Could not read hotkey for {path}: {e}")
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
                path_to_item[path] = item
                processed_paths.add(path)

        add_items_from_list(ordered_paths)
        newly_discovered_paths = [
            os.path.join(r, n)
            for r, d, f in os.walk(self.sessions_dir)
            for n in d + [fi for fi in f if fi.endswith(".json")]
        ]
        add_items_from_list(
            sorted(p for p in newly_discovered_paths if p not in processed_paths)
        )

    @Slot()
    def update_session_buttons_state(self):
        selected_items = self.session_tree.selectedItems()
        count = len(selected_items)
        if count == 0:
            return
        is_single_file = count == 1 and os.path.isfile(
            selected_items[0].data(0, Qt.UserRole)
        )
        self.rename_item_button.setEnabled(count == 1)
        self.delete_item_button.setEnabled(count > 0)
        self.overwrite_session_button.setEnabled(is_single_file)
        self.continue_session_button.setEnabled(is_single_file)
        self.duplicate_session_button.setEnabled(is_single_file)

    @Slot()
    def create_new_folder(self):
        selected_item = self.session_tree.currentItem()
        parent_path, parent_widget = (
            self.sessions_dir,
            self.session_tree.invisibleRootItem(),
        )
        if selected_item:
            path = selected_item.data(0, Qt.UserRole)
            if os.path.isdir(path):
                parent_path, parent_widget = path, selected_item
            else:
                parent_path, parent_widget = (
                    os.path.dirname(path),
                    selected_item.parent() or self.session_tree.invisibleRootItem(),
                )
        folder_name, ok = QInputDialog.getText(self, "Новая папка", "Имя папки:")
        if ok and folder_name:
            new_folder_path = os.path.join(parent_path, folder_name)
            try:
                os.makedirs(new_folder_path, exist_ok=True)
                folder_item = QTreeWidgetItem(parent_widget, [folder_name])
                folder_item.setData(0, Qt.UserRole, new_folder_path)
                folder_item.setIcon(0, self.style().standardIcon(QStyle.SP_DirIcon))
                self.save_settings()
            except OSError as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось создать папку: {e}")

    @Slot()
    def rename_selected_item(self):
        item = self.session_tree.currentItem()
        if not item:
            return
        old_path = item.data(0, Qt.UserRole)
        is_dir = os.path.isdir(old_path)
        old_name = (
            os.path.basename(old_path)
            if is_dir
            else os.path.splitext(os.path.basename(old_path))[0]
        )
        new_name, ok = QInputDialog.getText(
            self, "Переименовать", "Новое имя:", text=old_name
        )
        if ok and new_name and new_name != old_name:
            ext = "" if is_dir else ".json"
            new_path = os.path.join(os.path.dirname(old_path), new_name + ext)
            try:
                os.rename(old_path, new_path)
                item.setText(0, new_name)
                self.update_item_paths_recursively(item, new_path)
                if self.current_session_file == old_path:
                    self.current_session_file = new_path
                self.save_settings()
                self.playback_service.reload_sessions()
            except OSError as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось переименовать: {e}")

    def update_item_paths_recursively(self, item, new_path):
        item.setData(0, Qt.UserRole, new_path)
        if os.path.isdir(new_path):
            for i in range(item.childCount()):
                child_item = item.child(i)
                child_basename = os.path.basename(child_item.data(0, Qt.UserRole))
                child_new_path = os.path.join(new_path, child_basename)
                self.update_item_paths_recursively(child_item, child_new_path)

    @Slot()
    def delete_selected_items(self):
        items = self.session_tree.selectedItems()
        if not items:
            return
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Вы уверены, что хотите удалить {len(items)} элемент(ов)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            for item in items:
                path = item.data(0, Qt.UserRole)
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    (
                        item.parent() or self.session_tree.invisibleRootItem()
                    ).removeChild(item)
                except OSError as e:
                    QMessageBox.warning(
                        self, "Ошибка", f"Не удалось удалить {path}: {e}"
                    )
            self.clear_details_panel()
            self.save_settings()
            self.playback_service.reload_sessions()

    @Slot()
    def copy_selected_items(self):
        self.clipboard_paths = [
            item.data(0, Qt.UserRole) for item in self.session_tree.selectedItems()
        ]
        self.clipboard_operation = "copy"

    @Slot()
    def cut_selected_items(self):
        self.clipboard_paths = [
            item.data(0, Qt.UserRole) for item in self.session_tree.selectedItems()
        ]
        self.clipboard_operation = "cut"

    @Slot()
    def paste_items(self):
        if not getattr(self, "clipboard_paths", None):
            return
        target_item = self.session_tree.currentItem()
        dest_path = self.sessions_dir
        if target_item:
            path = target_item.data(0, Qt.UserRole)
            dest_path = path if os.path.isdir(path) else os.path.dirname(path)
        for src_path in self.clipboard_paths:
            basename = os.path.basename(src_path)
            new_dest_path = os.path.join(dest_path, basename)
            try:
                if self.clipboard_operation == "copy":
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, new_dest_path)
                    else:
                        shutil.copy2(src_path, new_dest_path)
                        with open(new_dest_path, "r+", encoding="utf-8") as f:
                            data = json.load(f)
                            data["hotkey"] = ""
                            f.seek(0)
                            json.dump(data, f, indent=4)
                            f.truncate()
                elif self.clipboard_operation == "cut":
                    shutil.move(src_path, new_dest_path)
            except Exception as e:
                QMessageBox.warning(
                    self, "Ошибка вставки", f"Не удалось вставить {basename}: {e}"
                )
        if self.clipboard_operation == "cut":
            self.clipboard_paths = []
        self.populate_session_tree()
        self.save_settings()
        self.playback_service.reload_sessions()

    def populate_action_table(self, actions):
        self.action_table.setRowCount(0)
        for i, action in enumerate(actions):
            self.action_table.insertRow(i)
            type_item = QTableWidgetItem(action.get("type", "N/A"))
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            details_item, x_item, y_item = (
                QTableWidgetItem(),
                QTableWidgetItem(),
                QTableWidgetItem(),
            )
            delay_item = QTableWidgetItem(str(action.get("delay", 1.0)))
            action_type = action.get("type")
            if action_type == "click":
                button_name = action.get("button", "N/A")
                details_item.setText(button_name)
                details_item.setData(Qt.UserRole, button_name)
                details_item.setFlags(details_item.flags() & ~Qt.ItemIsEditable)
                x_item.setText(str(action.get("x", "")))
                y_item.setText(str(action.get("y", "")))
            elif action_type == "key_press":
                raw_key_str = action.get("key", "N/A")
                details_item.setText(self.format_key_string_for_display(raw_key_str))
                details_item.setData(Qt.UserRole, raw_key_str)
                details_item.setFlags(details_item.flags() & ~Qt.ItemIsEditable)
                x_item.setFlags(x_item.flags() & ~Qt.ItemIsEditable)
                y_item.setFlags(y_item.flags() & ~Qt.ItemIsEditable)
            self.action_table.setItem(i, 0, type_item)
            self.action_table.setItem(i, 1, details_item)
            self.action_table.setItem(i, 2, x_item)
            self.action_table.setItem(i, 3, y_item)
            self.action_table.setItem(i, 4, delay_item)
        self._fit_action_table_width()
        self._maybe_freeze_left_panel()

    @Slot()
    def update_action_buttons_state(self):
        count = len(set(index.row() for index in self.action_table.selectedIndexes()))
        self.delete_selected_button.setEnabled(count > 0)
        self.duplicate_selected_button.setEnabled(count > 0)
        self.move_up_button.setEnabled(count > 0)
        self.move_down_button.setEnabled(count > 0)

    @Slot()
    def duplicate_selected_actions(self):
        selected_row_indices = sorted(
            list(set(index.row() for index in self.action_table.selectedIndexes()))
        )
        if not selected_row_indices:
            return
        actions = self.read_data_from_action_table()
        offset = 0
        last_selected_index = selected_row_indices[-1]
        for i in selected_row_indices:
            actions.insert(last_selected_index + 1 + offset, actions[i].copy())
            offset += 1
        self.populate_action_table(actions)

    def read_data_from_action_table(self):
        actions = []
        for i in range(self.action_table.rowCount()):
            action = {"type": self.action_table.item(i, 0).text()}
            try:
                action["delay"] = float(self.action_table.item(i, 4).text())
            except (ValueError, AttributeError):
                action["delay"] = 1.0
            if action["type"] == "click":
                try:
                    action["x"], action["y"] = int(
                        self.action_table.item(i, 2).text()
                    ), int(self.action_table.item(i, 3).text())
                except (ValueError, AttributeError):
                    action["x"], action["y"] = 0, 0
                action["button"] = self.action_table.item(i, 1).data(Qt.UserRole)
            elif action["type"] == "key_press":
                action["key"] = self.action_table.item(i, 1).data(Qt.UserRole)
            actions.append(action)
        return actions

    def clear_details_panel(self):
        self.hotkey_input.clear()
        self.window_title_input.clear()
        self.action_table.setRowCount(0)
        self.current_session_file = None

    @Slot(QTreeWidgetItem, QTreeWidgetItem)
    def on_current_item_changed(self, current, previous):
        if self._is_handling_check:
            return
        self.handle_selection(current)
        if not self._is_initializing:
            self.save_settings()

    def handle_selection(self, item):
        if self._is_handling_check:
            return
        # Папка: только подсветка строки в дереве, левая панель показывает
        # ранее выбранную сессию и не трогается вообще.
        if item is not None and not os.path.isfile(item.data(0, Qt.UserRole)):
            return
        self._is_handling_check = True
        iterator = QTreeWidgetItemIterator(self.session_tree)
        while iterator.value():
            if iterator.value() is not item and (
                iterator.value().flags() & Qt.ItemIsUserCheckable
            ):
                iterator.value().setCheckState(0, Qt.Unchecked)
            iterator += 1
        if item and os.path.isfile(item.data(0, Qt.UserRole)):
            if item.checkState(0) == Qt.Unchecked:
                item.setCheckState(0, Qt.Checked)
            self.load_session_from_path(item.data(0, Qt.UserRole))
        else:
            self.clear_details_panel()
        self._is_handling_check = False

    def load_session_from_path(self, path):
        self.current_session_file = path
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_hotkey = data.get("hotkey", "")
            self.hotkey_input.setText(self.format_key_string_for_display(raw_hotkey))
            self.hotkey_input.setProperty("raw_hotkey", raw_hotkey)
            self.window_title_input.setText(data.get("window_title", ""))
            self.populate_action_table(data.get("actions", []))
        except Exception as e:
            self.clear_details_panel()
            print(f"Error loading session {path}: {e}")

    @Slot()
    def delete_selected_actions(self):
        selected_items = self.action_table.selectedItems()
        if not selected_items:
            return
        rows_to_delete = sorted(
            list(set(item.row() for item in selected_items)), reverse=True
        )
        if (
            QMessageBox.question(
                self,
                "Подтверждение",
                f"Удалить {len(rows_to_delete)} выбранных действий?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            for row in rows_to_delete:
                self.action_table.removeRow(row)

    @Slot()
    def move_items_up(self):
        selected_items = self.session_tree.selectedItems()
        if not selected_items:
            return
        items_to_move = sorted(
            selected_items,
            key=lambda i: (
                i.parent() or self.session_tree.invisibleRootItem()
            ).indexOfChild(i),
        )
        for item in items_to_move:
            parent = item.parent() or self.session_tree.invisibleRootItem()
            index = parent.indexOfChild(item)
            if index > 0:
                parent.takeChild(index)
                parent.insertChild(index - 1, item)
        for item in items_to_move:
            item.setSelected(True)
        self.save_settings()

    @Slot()
    def move_items_down(self):
        selected_items = self.session_tree.selectedItems()
        if not selected_items:
            return
        items_to_move = sorted(
            selected_items,
            key=lambda i: (
                i.parent() or self.session_tree.invisibleRootItem()
            ).indexOfChild(i),
            reverse=True,
        )
        for item in items_to_move:
            parent = item.parent() or self.session_tree.invisibleRootItem()
            index = parent.indexOfChild(item)
            if index < parent.childCount() - 1:
                parent.takeChild(index)
                parent.insertChild(index + 1, item)
        for item in items_to_move:
            item.setSelected(True)
        self.save_settings()

    @Slot()
    def move_actions_up(self):
        selected_rows = sorted(
            list(set(index.row() for index in self.action_table.selectedIndexes()))
        )
        if not selected_rows or selected_rows[0] == 0:
            return
        actions = self.read_data_from_action_table()
        for row in selected_rows:
            actions[row], actions[row - 1] = actions[row - 1], actions[row]
        self.populate_action_table(actions)
        self.action_table.clearSelection()
        for row in selected_rows:
            self.action_table.selectRow(row - 1)

    @Slot()
    def move_actions_down(self):
        selected_rows = sorted(
            list(set(index.row() for index in self.action_table.selectedIndexes())),
            reverse=True,
        )
        if not selected_rows or selected_rows[0] == self.action_table.rowCount() - 1:
            return
        actions = self.read_data_from_action_table()
        for row in selected_rows:
            actions[row], actions[row + 1] = actions[row + 1], actions[row]
        self.populate_action_table(actions)
        self.action_table.clearSelection()
        for row in selected_rows:
            self.action_table.selectRow(row + 1)

    @Slot()
    def update_current_session(self):
        if not self.current_session_file or not os.path.isfile(
            self.current_session_file
        ):
            return
        try:
            raw_hotkey = self.hotkey_input.property("raw_hotkey")
            data = {
                "hotkey": raw_hotkey,
                "window_title": self.window_title_input.text().strip(),
                "actions": self.read_data_from_action_table(),
            }
            with open(self.current_session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            if current_item := self.session_tree.currentItem():
                current_item.setText(1, self.format_key_string_for_display(raw_hotkey))
                self.session_tree.resizeColumnToContents(1)
            self.playback_service.reload_sessions()
        except Exception as e:
            print(f"Error updating: {e}")

    @Slot()
    def start_recording(self):
        self.current_save_dir = self.sessions_dir
        if item := self.session_tree.currentItem():
            path = item.data(0, Qt.UserRole)
            self.current_save_dir = (
                path if os.path.isdir(path) else os.path.dirname(path)
            )
        try:
            self.background_recorder.recording_finished.disconnect(
                self.handle_new_session_finished
            )
        except (TypeError, RuntimeError):
            pass
        self.background_recorder.recording_finished.connect(
            self.handle_new_session_finished
        )
        self.background_recorder.start(mode="full")

    @Slot()
    def overwrite_current_session(self):
        item = self.session_tree.currentItem()
        if not item or os.path.isdir(item.data(0, Qt.UserRole)):
            QMessageBox.warning(
                self, "Внимание", "Сначала выберите сессию (файл) для перезаписи."
            )
            return
        self.current_session_file = item.data(0, Qt.UserRole)
        try:
            self.background_recorder.recording_finished.disconnect(
                self.handle_overwrite_finished
            )
        except (TypeError, RuntimeError):
            pass
        self.background_recorder.recording_finished.connect(
            self.handle_overwrite_finished
        )
        self.background_recorder.start(mode="full")

    @Slot()
    def continue_current_session(self):
        item = self.session_tree.currentItem()
        if not item or os.path.isdir(item.data(0, Qt.UserRole)):
            QMessageBox.warning(
                self, "Внимание", "Сначала выберите сессию (файл) для продолжения."
            )
            return
        self.current_session_file = item.data(0, Qt.UserRole)
        try:
            with open(self.current_session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            existing_actions = data.get("actions", [])
        except Exception:
            existing_actions = []
        try:
            self.background_recorder.recording_finished.disconnect(
                self.handle_continue_finished
            )
        except (TypeError, RuntimeError):
            pass
        self.background_recorder.recording_finished.connect(
            self.handle_continue_finished
        )
        self.background_recorder.start(
            mode="continue", existing_actions=existing_actions
        )

    @Slot()
    def duplicate_current_session(self):
        item = self.session_tree.currentItem()
        if not item or os.path.isdir(item.data(0, Qt.UserRole)):
            QMessageBox.warning(
                self, "Внимание", "Выберите сессию (файл) для дублирования."
            )
            return
        src_path = item.data(0, Qt.UserRole)
        dir_name, base_name = os.path.split(src_path)
        name, ext = os.path.splitext(base_name)
        copy_num = 1
        while True:
            new_name = f"{name} (copy {copy_num})" if copy_num > 1 else f"{name} (copy)"
            dest_path = os.path.join(dir_name, new_name + ext)
            if not os.path.exists(dest_path):
                break
            copy_num += 1
        try:
            shutil.copy2(src_path, dest_path)
            self.populate_session_tree()
            if new_item := self.find_item_by_path(dest_path):
                self.session_tree.setCurrentItem(new_item)
            self.save_settings()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось дублировать сессию: {e}")

    @Slot()
    def start_hotkey_capture(self):
        # Удаляем предыдущее подключение
        if self.hotkey_capture_overlay:
            try:
                self.hotkey_capture_overlay.hotkey_captured.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.hotkey_capture_overlay.close()
            self.hotkey_capture_overlay = None
        
        self.hide()
        self.hotkey_capture_overlay = HotkeyCaptureOverlay()
        self.hotkey_capture_overlay.hotkey_captured.connect(self.set_hotkey_from_capture)
        self.hotkey_capture_overlay.show()

    @Slot()
    def clear_hotkey(self):
        self.hotkey_input.clear()
        self.hotkey_input.setProperty("raw_hotkey", "")

    @Slot(str)
    def set_hotkey_from_capture(self, raw_hotkey):
        if self.hotkey_capture_overlay:
            try:
                self.hotkey_capture_overlay.hotkey_captured.disconnect(self.set_hotkey_from_capture)
            except (TypeError, RuntimeError):
                pass
            
            if raw_hotkey:
                self.hotkey_input.setText(self.format_key_string_for_display(raw_hotkey))
                self.hotkey_input.setProperty("raw_hotkey", raw_hotkey)
            
            self.hotkey_capture_overlay.close()
            self.hotkey_capture_overlay = None
        
        self.show()
        self.raise_()
        self.activateWindow()

    def find_item_by_path(self, path):
        it = QTreeWidgetItemIterator(self.session_tree)
        while it.value():
            if it.value().data(0, Qt.UserRole) == path:
                return it.value()
            it += 1
        return None

    @Slot(list)
    def handle_new_session_finished(self, actions):
        try:
            self.background_recorder.recording_finished.disconnect(
                self.handle_new_session_finished
            )
        except (TypeError, RuntimeError):
            pass
        if actions:
            filepath = os.path.join(
                self.current_save_dir,
                f"session_{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}.json",
            )
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(
                        {"hotkey": "", "window_title": "", "actions": actions},
                        f,
                        indent=4,
                    )
                self.populate_session_tree()
                if new_item := self.find_item_by_path(filepath):
                    self.session_tree.setCurrentItem(new_item)
                self.playback_service.reload_sessions()
            except Exception as e:
                print(f"Error saving: {e}")

    @Slot(list)
    def handle_overwrite_finished(self, actions):
        try:
            self.background_recorder.recording_finished.disconnect(
                self.handle_overwrite_finished
            )
        except (TypeError, RuntimeError):
            pass
        if actions and self.current_session_file:
            try:
                with open(self.current_session_file, "r+", encoding="utf-8") as f:
                    data = json.load(f)
                    data["actions"] = actions
                    f.seek(0)
                    json.dump(data, f, indent=4)
                    f.truncate()
                self.load_session_from_path(self.current_session_file)
                self.playback_service.reload_sessions()
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка", f"Не удалось перезаписать сессию: {e}"
                )

    @Slot(list)
    def handle_continue_finished(self, actions):
        try:
            self.background_recorder.recording_finished.disconnect(
                self.handle_continue_finished
            )
        except (TypeError, RuntimeError):
            pass
        if actions and self.current_session_file:
            try:
                with open(self.current_session_file, "r+", encoding="utf-8") as f:
                    data = json.load(f)
                    data["actions"] = actions
                    f.seek(0)
                    json.dump(data, f, indent=4)
                    f.truncate()
                self.load_session_from_path(self.current_session_file)
                self.playback_service.reload_sessions()
            except Exception as e:
                print(f"Ошибка дозаписи сессии: {e}")

    @Slot()
    def on_recording_started(self):
        self.tray_icon.setIcon(self.recording_icon)
        self.tray_icon.showMessage(
            "Запись Началась",
            "Нажмите ESC для остановки.",
            QSystemTrayIcon.Information,
            2000,
        )
        self.hide()

    @Slot()
    def on_recording_stopped(self):
        self.tray_icon.setIcon(self.normal_icon)
        self.showNormal()
        self.activateWindow()

    @Slot(int)
    def on_autostart_changed(self, state):
        enabled = (state == Qt.Checked)
        self.set_autostart(enabled)
        self.save_settings()

    @Slot(int)
    def on_start_minimized_changed(self, state):
        self.save_settings()

    def apply_styles(self):
        apply_theme(QApplication.instance(), self.font_size)
        # Правило ширины кнопок — после темы (метрики зависят от шрифта).
        enforce_button_proportions(getattr(self, "_square_icon_buttons", []))
        self._fit_action_table_width()

    def _fit_action_table_width(self):
        """Колонки и таблица — храповик: только растут, никогда не сужаются.

        Ширина колонки = max(название, данные, прежний размер, для X/Y —
        минимум 4 цифры координат). Поэтому клики по папкам/сессиям меняют
        только строки: геометрия стоит мёртво. Новому, более широкому
        контенту таблица и панель раздвигаются один раз (редкий случай);
        узкому ничего не меняется. Переполнение — штатный скролл.
        """
        table = self.action_table
        table.resizeColumnsToContents()
        self._enforce_coordinate_minimums(table)
        for col in range(table.columnCount()):
            grown = max(self._col_floors.get(col, 0), table.columnWidth(col))
            self._col_floors[col] = grown
            if table.columnWidth(col) < grown:
                table.setColumnWidth(col, grown)
        need = (
            table.verticalHeader().width()
            + table.horizontalHeader().length()
            + table.frameWidth() * 2
            + 6
        )
        if table.verticalScrollBar().maximum() > 0:
            need += table.verticalScrollBar().sizeHint().width()
        if need > self._table_width:
            self._table_width = need
            table.setFixedWidth(need)

    @staticmethod
    def _enforce_coordinate_minimums(table):
        """Минимум колонок X/Y (индексы 2, 3) — под 4 цифры.

        Отступ Qt вычисляем самокалибровкой: текущий fitted-размер минус
        ширина самого широкого из имеющихся текстов.
        """
        fm = table.fontMetrics()
        for col in (2, 3):
            texts = [table.horizontalHeaderItem(col).text()]
            for row in range(table.rowCount()):
                item = table.item(row, col)
                if item and item.text():
                    texts.append(item.text())
            widest = max(texts, key=fm.horizontalAdvance)
            padding = table.columnWidth(col) - fm.horizontalAdvance(widest)
            minimum = fm.horizontalAdvance("8888") + padding
            if table.columnWidth(col) < minimum:
                table.setColumnWidth(col, minimum)

    def _maybe_freeze_left_panel(self):
        """Один раз задаёт МИНИМУМ ширины левой панели (после первого показа
        контента). Панель уже никогда не сузится от кликов; новому широкому
        контенту — раздвинется один раз вместе с таблицей."""
        if self._left_width_frozen or not self.isVisible():
            return
        self._left_width_frozen = True
        self.left_widget.setMinimumWidth(self.left_widget.width())

    @Slot(int)
    def set_font_size(self, size):
        self.font_size = size
        self.apply_styles()
        self.save_settings()

    def _to_relative(self, path):
        """Преобразует абсолютный путь в относительный (относительно script_dir)."""
        if not path:
            return None
        try:
            return os.path.relpath(path, self.script_dir)
        except ValueError:
            return path  # Если пути на разных дисках

    def _to_absolute(self, path):
        """Преобразует относительный путь в абсолютный."""
        if not path:
            return None
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(self.script_dir, path))

    @Slot()
    def save_settings(self):
        if self._is_initializing:
            return
        checked_session_path = None
        it = QTreeWidgetItemIterator(self.session_tree)
        while it.value():
            if it.value().checkState(0) == Qt.Checked:
                checked_session_path = it.value().data(0, Qt.UserRole)
                break
            it += 1
        ordered_paths = [
            it.value().data(0, Qt.UserRole)
            for it in QTreeWidgetItemIterator(self.session_tree)
        ]
        expanded_paths = [
            it.value().data(0, Qt.UserRole)
            for it in QTreeWidgetItemIterator(self.session_tree)
            if it.value().isExpanded()
        ]
        settings = {
            "geometry": self.geometry().getRect(),
            "font_size": self.font_size,
            "checked_session": self._to_relative(checked_session_path),
            "expanded_folders": [self._to_relative(p) for p in expanded_paths],
            "tree_order": [self._to_relative(p) for p in ordered_paths],
            "autostart_enabled": self.autostart_action.isChecked(),
            "start_minimized": self.start_minimized_action.isChecked(),
        }
        with open(
            os.path.join(self.script_dir, "settings.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(settings, f, indent=4)

    def load_settings(self):
        try:
            with open(
                os.path.join(self.script_dir, "settings.json"), "r", encoding="utf-8"
            ) as f:
                settings = json.load(f)
            if geom := settings.get("geometry"):
                self.setGeometry(*geom)
            self.font_size = settings.get("font_size", 11)
            self.checked_session_to_load = self._to_absolute(settings.get("checked_session"))
            self.expanded_paths_to_load = [
                self._to_absolute(p) for p in settings.get("expanded_folders", [])
            ]
            self.tree_order_to_load = [
                self._to_absolute(p) for p in settings.get("tree_order", [])
            ]
        except (FileNotFoundError, json.JSONDecodeError):
            (
                self.checked_session_to_load,
                self.expanded_paths_to_load,
                self.tree_order_to_load,
            ) = (None, [], [])
            settings = {} # Создаем пустой словарь, если файл не найден

        # Загрузка настроек автозапуска
        self.autostart_action.setChecked(settings.get('autostart_enabled', False))
        self.start_minimized_action.setChecked(settings.get('start_minimized', False))

    def post_load_select_session(self):
        item_to_select = None
        it = QTreeWidgetItemIterator(self.session_tree)
        while it.value():
            item = it.value()
            path = item.data(0, Qt.UserRole)
            if path in self.expanded_paths_to_load:
                item.setExpanded(True)
            if path == self.checked_session_to_load:
                item_to_select = item
            it += 1
        if item_to_select:
            self.session_tree.setCurrentItem(item_to_select)
            parent = item_to_select.parent()
            while parent:
                parent.setExpanded(True)
                parent = parent.parent()
        else:
            first_item = self.session_tree.topLevelItem(0)
            if first_item:
                while first_item.childCount() > 0:
                    first_item = first_item.child(0)
                if first_item and os.path.isfile(first_item.data(0, Qt.UserRole)):
                    self.session_tree.setCurrentItem(first_item)

    def moveEvent(self, event):
        super().moveEvent(event)
        self.save_settings()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.save_settings()

    def closeEvent(self, event):
        if not self.is_closing:
            event.ignore()
        else:
            event.accept()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange and self.isMinimized():
            event.ignore()
            self.hide()
            self.tray_icon.show()
        super().changeEvent(event)


    def set_autostart(self, enabled):
        """
        Включает или отключает автозапуск приложения через создание/удаление ярлыка
        в папке автозагрузки Windows.
        """
        try:
            startup_folder = os.path.join(
                os.environ['APPDATA'],
                'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
            )
            shortcut_path = os.path.join(startup_folder, 'MacroRecorder.lnk')

            if enabled:
                if getattr(sys, 'frozen', False):
                    target_path = sys.executable
                else:
                    target_path = os.path.abspath(sys.argv[0])
                
                target_path = os.path.normpath(target_path)
                
                if not os.path.exists(target_path):
                    print(f"Целевой файл не найден: {target_path}")
                    return

                vbs_script = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{target_path}"
oLink.WorkingDirectory = "{os.path.dirname(target_path)}"
oLink.Description = "Macro Recorder"
oLink.Save
"""
                vbs_path = os.path.join(os.environ['TEMP'], 'create_shortcut.vbs')
                
                try:
                    with open(vbs_path, 'w') as f:
                        f.write(vbs_script)
                    
                    subprocess.run(
                        ['cscript', '//Nologo', vbs_path],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    
                    os.remove(vbs_path)
                    
                    if os.path.exists(shortcut_path):
                        print(f"Ярлык создан в Startup: {shortcut_path}")
                    else:
                        print("Не удалось создать ярлык")
                
                except Exception as e:
                    print(f"Ошибка создания ярлыка: {e}")
                    print(traceback.format_exc())
            
            else:
                if os.path.exists(shortcut_path):
                    try:
                        os.remove(shortcut_path)
                        print("Ярлык автозапуска удален")
                    except Exception as e:
                        print(f"Ошибка удаления ярлыка: {e}")
        
        except Exception as e:
            print(f"Ошибка функции set_autostart: {e}")
            print(traceback.format_exc())


_SINGLE_INSTANCE_SERVER_NAME = "MacroRecorderSingleInstance"


def _notify_running_instance():
    """Просит уже запущенную копию показать окно. True — копия была."""
    sock = QLocalSocket()
    try:
        sock.connectToServer(_SINGLE_INSTANCE_SERVER_NAME)
        if sock.waitForConnected(500):
            try:
                sock.write(b"raise")
                sock.waitForBytesWritten(500)
            finally:
                sock.disconnectFromServer()
            return True
    except Exception:
        pass
    return False


def _start_instance_server():
    """Слушает повторные запуски. Возвращает (state, server).

    state["window"] заполняется после создания окна; пришедший раньше
    запрос поднимает окно сразу после (флаг pending).
    """
    server = QLocalServer()
    if not server.listen(_SINGLE_INSTANCE_SERVER_NAME):
        QLocalServer.removeServer(_SINGLE_INSTANCE_SERVER_NAME)
        server.listen(_SINGLE_INSTANCE_SERVER_NAME)
    state = {"window": None, "pending_raise": False}

    def _raise_window():
        window = state["window"]
        if window is None:
            state["pending_raise"] = True
            return
        window.showNormal()
        window.show()
        window.raise_()
        window.activateWindow()

    def _on_new_connection():
        sock = server.nextPendingConnection()
        while sock is not None:
            try:
                sock.waitForReadyRead(300)
                sock.readAll()
            except Exception:
                pass
            try:
                sock.disconnectFromServer()
            except Exception:
                pass
            sock = (
                server.nextPendingConnection()
                if server.hasPendingConnections()
                else None
            )
        _raise_window()

    server.newConnection.connect(_on_new_connection)
    return state, server


if __name__ == "__main__":
    import subprocess

    app = QApplication(sys.argv)
    from PySide6.QtCore import QTimer

    # Одна копия: повторный запуск показывает существующее окно и выходит.
    if _notify_running_instance():
        print("Уже запущено: показано существующее окно.")
        sys.exit(0)
    _instance_state, _instance_server = _start_instance_server()
    app._instance_server = _instance_server  # держать ссылку, иначе GC убьёт сервер

    # Русская локаль стандартных Qt-текстов — до создания виджетов.
    install_qt_ru_translation(app)

    # Устанавливаем AppUserModelID для Windows (с обработкой ошибок)
    if sys.platform == "win32":
        try:
            myappid = "mycompany.macrorecorder.app.version1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelIDW(myappid)
            print(f"✓ AppUserModelID установлен: {myappid}")
        except AttributeError:
            print("⚠️ SetCurrentProcessExplicitAppUserModelIDW не найдена (старая версия Windows)")
        except Exception as e:
            print(f"⚠️ Ошибка установки AppUserModelID: {e}")
    
    # Устанавливаем иконку приложения
    icon_path = resource_path("logo.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        print(f"✓ Глобальная иконка приложения установлена: {icon_path}")
    else:
        print(f"⚠️ Файл иконки не найден: {icon_path}")
    
    app.setQuitOnLastWindowClosed(False)
    main_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    sessions_dir = os.path.join(main_dir, "Sessions")
    playback_service = PlaybackService(sessions_dir)
    main_window = MainWindow(playback_service)
    main_window.apply_styles()
    _instance_state["window"] = main_window
    if _instance_state.pop("pending_raise", False):
        main_window.showNormal()
        main_window.raise_()
        main_window.activateWindow()
    main_window.show()
    QTimer.singleShot(100, playback_service.reload_sessions)
    sys.exit(app.exec())
