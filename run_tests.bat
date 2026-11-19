@echo off
cd /d "%~dp0"
title Jarvis Tests
chcp 65001 >nul
venv\Scripts\python.exe -m unittest discover -s tests -v
echo.
pause
