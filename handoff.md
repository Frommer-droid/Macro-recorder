# Состояние сопровождения Macro Recorder

## Текущее состояние

- Обновлено: 2026-10-03, Codex.
- Статус: complete.
- Для публичного кода версии 0.3.0 подготовлена поставка Windows.
- Приложение не меняет функциональную версию; добавлены безопасная сборка и установщик.

## Изменения

- Build_Tools/MacroRecorder.spec: строгий native PATH и проверка происхождения DLL.
- Build_Tools/runtime_policy.py: закрытый allowlist и полный MSVC runtime из PySide6.
- Build_Tools/frozen_smoke.py: импорты Qt, pynput и pywin32 без видимого окна и хоткеев.
- Build_Tools/build_release.py: сборка, COLLECT-аудит, smoke, обезличенный payload и установщик.
- Build_Tools/MacroRecorder.iss: русский мастер, папка D Apps или C Apps на целевой машине.
- README RU/EN, THIRD_PARTY_NOTICES.md и командный файл запуска синхронизированы.

## Проверки

- В каждой из основной и smoke-сборок проверено 74 native-компонента; посторонних источников нет.
- Семь MSVC DLL в корне _internal совпадают с runtime PySide6 по SHA-256.
- Frozen smoke: FROZEN_IMPORT_OK 0.3.0 True; exit 0, stderr пуст.
- Пользовательские настройки, сессии, логи и IDE-настройки не включены в payload.

## Публикация

- Публикуется корневой снимок с одним тегом v0.3.0 и установщиком Release.
- Локальная рабочая история сохраняется; обычный push может вернуть историю.

## Следующее действие

- Использовать проектный .venv и Build_Tools/build_release.py для повторной сборки.
