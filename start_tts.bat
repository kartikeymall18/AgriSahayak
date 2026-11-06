@echo off
title AgriSahayak neural voice
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set HF_HUB_OFFLINE=1
tts_env\Scripts\python.exe tts_server.py
pause
