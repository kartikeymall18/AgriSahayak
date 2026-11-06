@echo off
setlocal
title AgriSahayak server
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
rem The models are loaded from local folders, so no internet is used at start-up.
rem To let the programs download models, run download_voice.py (it switches these two off by itself).
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1

if not exist ".venv\Scripts\python.exe" (
  echo Project environment not found. Follow the setup steps in README.md first.
  pause
  exit /b 1
)

echo.
echo  ==============================================
echo   AgriSahayak is starting. Keep this window open.
echo   Close it (or press Ctrl+C) to stop the server.
echo  ==============================================
echo.
rem open the dashboard in the browser after the server has had time to start
start "" /min cmd /c "timeout /t 10 /nobreak >nul & start http://localhost:8000"

".venv\Scripts\python.exe" server.py

echo.
echo  The server stopped. Read the lines above if it stopped by itself. Press any key to close.
pause >nul
