@echo off
cd /d "%~dp0"
title Jarvis
chcp 65001 >nul
if not exist venv\Scripts\python.exe (
  echo First time setup needed. Running install.bat ...
  call install.bat
)
venv\Scripts\python.exe main.py
echo.
echo Jarvis stopped.
pause
