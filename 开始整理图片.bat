@echo off
cd /d "%~dp0"
py -3 .src\main.py
if errorlevel 1 python .src\main.py
pause
