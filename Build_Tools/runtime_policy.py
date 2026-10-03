"""Закрытая политика происхождения native DLL для Windows-сборки."""
from __future__ import annotations
import os
import sys
from pathlib import Path


def configure_native_path() -> Path:
    import PySide6
    import shiboken6
    qt_root = Path(PySide6.__file__).resolve().parent
    paths = [qt_root, Path(shiboken6.__file__).resolve().parent,
             Path(sys.prefix) / 'Scripts', Path(sys.base_prefix),
             Path(sys.base_prefix) / 'DLLs', Path(os.environ['SystemRoot']) / 'System32']
    os.environ['PATH'] = os.pathsep.join(str(path) for path in paths if path.is_dir())
    return qt_root


def validate_origins(binaries: list, project_root: Path) -> None:
    roots = [project_root.resolve(), Path(sys.prefix).resolve(),
             Path(sys.base_prefix).resolve(), Path(os.environ['SystemRoot']).resolve()]
    invalid = []
    for destination, source, kind in binaries:
        source_path = Path(source).resolve()
        if not source_path.is_file() or not any(source_path.is_relative_to(root) for root in roots):
            invalid.append(destination)
    if invalid:
        raise RuntimeError('Недопустимое происхождение native-компонентов: ' + ', '.join(invalid))


def use_qt_runtime(binaries: list, qt_root: Path) -> list:
    runtimes = {path.name.lower(): path for path in qt_root.glob('*.dll')
                if path.name.lower().startswith(('concrt140', 'msvcp140', 'vcruntime140'))}
    required = {'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
                'vcruntime140.dll', 'vcruntime140_1.dll', 'concrt140.dll'}
    if not required.issubset(runtimes):
        raise RuntimeError('Неполный комплект MSVC runtime в PySide6.')
    # Проверка происхождения уже выполнена. Заменяем разрешённый Python CRT
    # согласованным комплектом Qt; посторонние DLL вызывают ошибку сборки.
    result = [item for item in binaries if item[0].replace('\\', '/').lower() not in runtimes]
    result.extend((path.name, str(path), 'BINARY') for path in runtimes.values())
    return result
