@echo off
cd /d "%~dp0"
set "PYTHON_EXE=.venv\Scripts\python.exe"

if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" .src\main.py --dry-run
) else (
  py -3 .src\main.py --dry-run
  if errorlevel 1 python .src\main.py --dry-run
)
pause
