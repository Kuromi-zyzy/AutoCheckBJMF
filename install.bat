@echo off
chcp 65001 >nul
title AutoCheckBJMF - Install

cd /d "%~dp0"

echo ====================================
echo   AutoCheckBJMF - One-click Setup
echo ====================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.11+ first.
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PY_VER=%%i
echo [OK] %PY_VER%

:: Create venv
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [1/3] Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual env.
        pause
        exit /b 1
    )
    echo [OK] Virtual env created.
) else (
    echo [OK] Virtual env exists, skipping.
)

:: Install deps
echo.
echo [2/3] Installing dependencies...
.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip >nul
.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple beautifulsoup4 drissionpage prompt-toolkit questionary requests rich schedule
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
echo ====================================
echo.
echo Next steps:
echo   1. Double-click config_wizard.bat to set up
echo   2. Double-click start_checkin.bat to begin
echo.
echo Note: Using Tsinghua mirror for faster downloads.
echo.
pause
