@echo off
cd /d "%~dp0"
title Jarvis (typing mode)
chcp 65001 >nul
venv\Scripts\python.exe main.py --text --console
pause
