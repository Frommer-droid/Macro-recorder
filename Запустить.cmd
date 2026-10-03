@echo off
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Create the project .venv and install requirements.txt first.
  pause
  exit /b 1
)
if not exist "%~dp0Macro_recorder.pyw" (
  echo Macro_recorder.pyw was not found.
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0Macro_recorder.pyw"
