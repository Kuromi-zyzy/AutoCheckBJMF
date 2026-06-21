@echo off
chcp 65001 >nul
title AutoCheckBJMF - Running

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual env not found. Please run install.bat first.
    pause
    exit /b 1
)

if not exist "config.json" (
    echo [ERROR] config.json not found. Please run config_wizard.bat first.
    pause
    exit /b 1
)

echo Starting auto check-in...
powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -NoNewWindow -FilePath '.venv\Scripts\python.exe' -ArgumentList 'src\main.py' -WorkingDirectory '%~dp0'"
echo.
echo [OK] Check-in running in background.
echo      Check sign_log.txt for records.
echo      To stop: Task Manager - end python.exe
echo.
timeout /t 3 /nobreak >nul
exit
