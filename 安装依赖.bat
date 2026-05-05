@echo off
cd /d "%~dp0"
set "PYTHON_EXE=.venv\Scripts\python.exe"

if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" -m pip install -r requirements.txt
) else (
  py -3 -m pip install -r requirements.txt
  if errorlevel 1 python -m pip install -r requirements.txt
)
pause
