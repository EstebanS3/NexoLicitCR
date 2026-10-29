@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primero ejecuta install.ps1.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\easy_install.py run %*
set "result=%errorlevel%"
if not "%result%"=="0" pause
exit /b %result%
