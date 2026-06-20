@echo off
chcp 65001 >nul
title AutoCheckBJMF Setup Wizard

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual env not found. Please run install.bat first.
    pause
    exit /b 1
)

.venv\Scripts\python.exe src\make_config.py
pause
