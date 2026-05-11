@echo off
cd /d "%~dp0.src"
set "PYTHON_EXE=.venv\Scripts\python.exe"

if exist "..\%PYTHON_EXE%" (
  "..\%PYTHON_EXE%" -m gui
) else (
  py -3 -m gui
  if errorlevel 1 python -m gui
)
