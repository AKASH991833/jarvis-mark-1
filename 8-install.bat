@echo off
setlocal
cd /d "%~dp0"
title Jarvis Installer
echo ==============================================
echo   JARVIS INSTALLER  (free, one time only)
echo ==============================================
echo.

set PY=
where py >nul 2>nul && set PY=py -3
if "%PY%"=="" where python >nul 2>nul && set PY=python
if "%PY%"=="" (
  echo Python is not installed. Trying to install it for free...
  winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
  echo.
  echo If Python installed now: CLOSE this window and double-click install.bat again.
  echo If it did not: open https://www.python.org/downloads/ , download Python,
  echo and TICK "Add Python to PATH" in the first screen. Then run install.bat again.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist venv (
  echo [1/3] Creating private Python environment...
  %PY% -m venv venv
  if errorlevel 1 ( echo Failed to create venv. & pause & exit /b 1 )
)
echo [2/3] Installing parts (takes 2-5 minutes, needs internet)...
call venv\Scripts\python.exe -m pip install --upgrade pip >nul
call venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 ( echo. & echo Install failed. Check internet and run install.bat again. & pause & exit /b 1 )

if not exist .env copy .env.example .env >nul
echo.
echo [3/3] Gemini key
echo Get the FREE key here: https://aistudio.google.com/apikey  (login with Google, "Create API key")
set /p JKEY=Paste your Gemini key here and press Enter (or just press Enter to do it later): 
if not "%JKEY%"=="" (
  set JARVIS_KEY=%JKEY%
  call venv\Scripts\python.exe -c "import os,re;t=open('.env',encoding='utf-8').read();t=re.sub(r'(?m)^GEMINI_API_KEY=.*$',lambda m:'GEMINI_API_KEY='+os.environ['JARVIS_KEY'].strip(),t);open('.env','w',encoding='utf-8').write(t)"
  echo Key saved.
) else (
  echo OK. Later: open the file named .env with Notepad and paste the key after GEMINI_API_KEY=
)
echo.
echo ==============================================
echo   DONE!  Now double-click  run.bat
echo ==============================================
pause
