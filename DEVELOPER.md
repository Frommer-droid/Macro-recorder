# 🛠️ Руководство разработчика Macro Recorder

## 📂 Структура проекта

*   `Macro_recorder.pyw`: Главный файл приложения (точка входа).
*   `version.py`: Модуль управления версиями.
*   `VERSION`: Файл с текущей версией проекта.
*   `Sessions/`: Папка для хранения записанных макросов.
*   `Build_Tools/`: Инструменты для сборки EXE (PyInstaller).
*   `macro_player.exe`: Внешний плеер макросов (AutoHotkey).
*   `macro_player.ahk`: Исходный скрипт плеера.

## 🚀 Запуск из исходного кода

Зависимости ставятся только в проектное `.venv`, не в глобальный Python.

1.  Создайте окружение и установите зависимости (Python 3.12):
    ```powershell
    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    ```
2.  Проверьте, что используется именно проектный интерпретатор:
    ```powershell
    .\.venv\Scripts\python.exe -c "import sys; print(sys.executable)"
    ```
    Путь обязан указывать на `MacroRecorder\.venv\Scripts\python.exe`.
3.  Запустите приложение без консольного окна:
    ```powershell
    Start-Process .\.venv\Scripts\pythonw.exe -ArgumentList ".\Macro_recorder.pyw"
    ```
    Вариант с консолью (видны отладочные логи):
    ```powershell
    .\.venv\Scripts\python.exe .\Macro_recorder.pyw
    ```
    Не запускайте `.pyw` через голый `python`/`py` или глобальный `pythonw.exe` —
    это подвяжет GUI к чужому интерпретатору без установленных зависимостей.

## 📦 Сборка (Build)

Для создания EXE файла используется PyInstaller, запуск — только через
проектное `.venv`.

1.  Перейдите в папку `Build_Tools`.
2.  Запустите `SpecCompiler.pyw` или выполните сборку вручную:
    ```powershell
    cd Build_Tools
    ..\.venv\Scripts\python.exe -m PyInstaller --noconfirm MacroRecorder.spec
    ```
3.  Перенесите результат в корень и скопируйте ресурсы (скрипт приложение
    **не запускает** — запускайте exe вручную, если нужно):
    ```powershell
    # выполняется из корня проекта, повторяет шаги post_build.py без автозапуска
    Remove-Item -LiteralPath "MacroRecorder" -Recurse -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath "Build_Tools/dist/MacroRecorder" -Destination "MacroRecorder"
    ```

Результат будет в корневой папке проекта: `MacroRecorder/`.

## 🛡️ Git и контроль версий

В репозиторий **НЕ** должны попадать:
*   `settings.json`: Локальные настройки пользователя.
*   `logo.png`: Исходники изображений (используется только `logo.ico`).
*   `Sessions/`: Папка с пользовательскими макросами.
*   `MacroRecorder/`: Папка с собранным приложением.
*   `*.log`: Логи отладки.

Эти файлы добавлены в `.gitignore`.

## Публичный Windows-установщик

Повторяемая сборка версии 0.3.0 выполняется командой:

```powershell
$env:INNO_SETUP_ISCC = (Get-Command ISCC.exe).Source
.\.venv\Scripts\python.exe Build_Tools/build_release.py
```

Если компилятор отсутствует в PATH, задайте INNO_SETUP_ISCC полным путём к своей установке Inno Setup. Перед повторной сборкой сохраните готовую папку MacroRecorder и удалите только её проверенный путь.

build_release.py использует проектное окружение и минимальный native PATH. MacroRecorder.spec проверяет происхождение всех бинарных компонентов и комплект MSVC из PySide6. Сборка создаёт приложение и отдельную offscreen fixture с той же политикой DLL, проверяет COLLECT-00.toc, stdout/stderr и код завершения frozen smoke. Приложение, запись макросов и горячие клавиши не запускаются.

Публичный payload включает исходники, лицензии, ресурсы и macro_player.exe. Настройки, Sessions, логи и окружение владельца не копируются. Portable-папка остаётся в MacroRecorder, установщик и журналы проверки — в release. Установщик использует русский язык и выбирает D:\Apps\Макро Рекордер при наличии D, иначе C:\Apps\Макро Рекордер.
