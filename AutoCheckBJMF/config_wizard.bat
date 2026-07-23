@echo off
chcp 65001 >nul
title AutoCheckBJMF - 配置向导

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 虚拟环境未找到，请先运行 install.bat 安装
    pause
    exit /b 1
)

.venv\Scripts\python.exe src\make_config.py
pause
