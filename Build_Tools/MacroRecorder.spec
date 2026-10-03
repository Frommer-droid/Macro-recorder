# -*- mode: python ; coding: utf-8 -*-
"""Одинаковая DLL-политика для приложения и неинтерактивного frozen smoke."""
import os
import runpy
from pathlib import Path

project_root = Path(SPECPATH).resolve().parent
policy = runpy.run_path(str(project_root / 'Build_Tools' / 'runtime_policy.py'))
qt_root = policy['configure_native_path']()
smoke = os.environ.get('MACRO_FROZEN_SMOKE') == '1'
entry = project_root / ('Build_Tools/frozen_smoke.py' if smoke else 'Macro_recorder.pyw')
app_name = 'MacroRecorderSmoke' if smoke else 'MacroRecorder'
translations = qt_root / 'translations' / 'qtbase_ru.qm'
if not translations.is_file():
    raise RuntimeError('Отсутствует обязательный русский перевод Qt.')
a = Analysis(
    [str(entry)], pathex=[str(project_root)], binaries=[],
    datas=[(str(translations), 'translations')],
    hiddenimports=['pynput.keyboard._win32', 'pynput.mouse._win32', 'win32con',
                   'win32api', 'win32gui', 'PySide6.QtNetwork'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
policy['validate_origins'](a.binaries, project_root)
a.binaries = policy['use_qt_runtime'](a.binaries, qt_root)
policy['validate_origins'](a.binaries, project_root)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=app_name,
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=smoke, disable_windowed_traceback=False,
          icon=str(project_root / 'logo.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=app_name)