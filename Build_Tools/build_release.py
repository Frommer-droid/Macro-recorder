"""Проверенная сборка публичной поставки без запуска пользовательского приложения."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / 'Build_Tools'
OUTPUT = ROOT / 'release'
POLICY = runpy.run_path(str(TOOLS / 'runtime_policy.py'))


def run(command: list[str], log_name: str, *, timeout: int = 300) -> str:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=timeout,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    (OUTPUT / log_name).write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'{log_name}: exit {result.returncode}')
    return result.stdout + result.stderr


def inspect_collect(mode: str, name: str) -> None:
    toc_path = TOOLS / 'build' / mode / 'MacroRecorder' / 'COLLECT-00.toc'
    toc = ast.literal_eval(toc_path.read_text(encoding='utf-8'))
    native = []

    def walk(value):
        if isinstance(value, (tuple, list)):
            if len(value) == 3 and isinstance(value[2], str) and value[2] in {'BINARY', 'EXTENSION'}:
                native.append(tuple(value))
            else:
                for child in value:
                    walk(child)

    walk(toc)
    if not native:
        raise RuntimeError('COLLECT не содержит native-компонентов.')
    POLICY['validate_origins'](native, ROOT)
    qt_root = POLICY['configure_native_path']()
    runtime = sorted(path for path in qt_root.glob('*.dll')
                     if path.name.lower().startswith(('concrt140', 'msvcp140', 'vcruntime140')))
    for path in runtime:
        bundled = TOOLS / 'dist' / name / '_internal' / path.name
        if hashlib.sha256(bundled.read_bytes()).digest() != hashlib.sha256(path.read_bytes()).digest():
            raise RuntimeError(f'Qt MSVC runtime отличается: {path.name}')
    shutil.copy2(toc_path, OUTPUT / f'COLLECT-{mode}.toc')
    (OUTPUT / f'native-audit-{mode}.json').write_text(
        json.dumps({'native_components': len(native), 'foreign_origins': 0,
                    'qt_runtime_files': [path.name for path in runtime]}, indent=2), encoding='utf-8')


def main() -> None:
    if Path(sys.prefix).resolve() != (ROOT / '.venv').resolve():
        raise RuntimeError('Используйте проектный .venv.')
    if (ROOT / 'VERSION').read_text(encoding='utf-8').strip() != '0.3.0':
        raise RuntimeError('Эта поставка предназначена для версии 0.3.0.')
    if (ROOT / 'MacroRecorder').exists():
        raise RuntimeError('Сохраните прежнюю portable-папку перед новой сборкой.')
    OUTPUT.mkdir(exist_ok=True)
    POLICY['configure_native_path']()
    for mode, name in [('main', 'MacroRecorder'), ('smoke', 'MacroRecorderSmoke')]:
        os.environ['MACRO_FROZEN_SMOKE'] = '1' if mode == 'smoke' else '0'
        run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
             '--distpath', str(TOOLS / 'dist'), '--workpath', str(TOOLS / 'build' / mode),
             str(TOOLS / 'MacroRecorder.spec')], f'build-{mode}.log')
        inspect_collect(mode, name)
        print(f'{mode}: DLL origins and Qt runtime verified', flush=True)
    smoke_exe = TOOLS / 'dist' / 'MacroRecorderSmoke' / 'MacroRecorderSmoke.exe'
    smoke_output = run([str(smoke_exe)], 'frozen-smoke.log', timeout=30)
    errors = ('Traceback', 'ImportError', 'DLL load failed', 'PyInstallerImportError', ':ERROR]')
    if 'FROZEN_IMPORT_OK 0.3.0 True' not in smoke_output or any(text in smoke_output for text in errors):
        raise RuntimeError('Frozen smoke завершился без подтверждения успешных импортов.')
    print('frozen imports: OK', flush=True)
    payload = ROOT / 'MacroRecorder'
    shutil.copytree(TOOLS / 'dist' / 'MacroRecorder', payload)
    for name in ['logo.ico', 'macro_player.exe', 'Assets', 'VERSION', 'LICENSE',
                 'THIRD_PARTY_NOTICES.md', 'README.md', 'README.en.md', 'RELEASE_NOTES.md']:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, payload / name)
        else:
            shutil.copy2(source, payload / name)
    tracked = subprocess.run(['C:/Program Files/Git/cmd/git.exe', 'ls-files', '-z'],
                             cwd=ROOT, capture_output=True, check=True).stdout.decode('utf-8').split('\0')
    for name in filter(None, tracked):
        if name.startswith('.vscode/'):
            continue
        source = ROOT / name
        if not source.is_file():
            raise RuntimeError(f'Нет исходного tracked-файла: {name}')
        destination = payload / 'source' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    license_dir = payload / 'third-party-licenses'
    for source in (ROOT / '.venv' / 'Lib' / 'site-packages').rglob('*'):
        if source.is_file() and any(marker in source.name.lower() for marker in ('license', 'copying')):
            relative = source.relative_to(ROOT / '.venv' / 'Lib' / 'site-packages')
            destination = license_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    forbidden = [path for path in payload.rglob('*') if path.name in {'settings.json', '.env', '.git', '.venv'}
                 or path.suffix.lower() == '.log']
    if forbidden:
        raise RuntimeError('В публичной поставке есть локальные файлы.')
    compiler = os.environ.get('INNO_SETUP_ISCC') or shutil.which('ISCC.exe')
    if not compiler or not Path(compiler).is_file():
        raise RuntimeError('Задайте INNO_SETUP_ISCC для компилятора Inno Setup.')
    run([compiler, f'/DAppSourceDir={payload}', f'/DOutputDir={OUTPUT}',
         str(TOOLS / 'MacroRecorder.iss')], 'installer.log')
    installer = OUTPUT / 'MacroRecorder_v0.3.0_Setup.exe'
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    manifest = {path.relative_to(payload).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in payload.rglob('*') if path.is_file()}
    (OUTPUT / 'payload-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    (OUTPUT / 'installer.sha256').write_text(f'{digest}  {installer.name}\n', encoding='utf-8')
    print(f'installer ready: {installer.name}, {installer.stat().st_size} bytes, SHA256 {digest}', flush=True)


if __name__ == '__main__':
    main()
