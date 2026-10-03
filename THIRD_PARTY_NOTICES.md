# Сторонние компоненты

MIT в LICENSE относится к собственному коду Macro Recorder. Лицензии зависимостей сохраняются:

- PySide6 и Shiboken6: LGPL-3.0 / GPL-3.0 / коммерческая лицензия Qt. Используются динамические библиотеки, тексты лицензий включены в `third-party-licenses`.
- pynput: LGPL-3.0. [Исходники pynput](https://github.com/moses-palmer/pynput).
- pywin32: Python Software Foundation License. [Исходники pywin32](https://github.com/mhammond/pywin32).
- PyInstaller: GPL-2.0 с исключением для bootloader, разрешающим распространение собранных приложений. [Лицензирование PyInstaller](https://pyinstaller.org/en/stable/license.html).
- `macro_player.exe` содержит runtime AutoHotkey под GPL-2.0. [Исходники AutoHotkey](https://github.com/AutoHotkey/AutoHotkey).

Версии зависимостей закреплены в requirements.txt. Исходники приложения, `macro_player.ahk` и сборочные команды включены в каталог `source` поставки. Исходники сторонних компонентов доступны по ссылкам выше; Qt — на [download.qt.io](https://download.qt.io/official_releases/QtForPython/).

Динамические Qt-библиотеки можно заменить совместимыми библиотеками той же архитектуры. Их собственные лицензии не заменяются MIT.
