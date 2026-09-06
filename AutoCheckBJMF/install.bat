@echo off
chcp 65001 >nul
title AutoCheckBJMF - 一键安装

cd /d "%~dp0"

echo ====================================
echo   AutoCheckBJMF - 一键安装
echo ====================================
echo.

:: Check uv
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未检测到 uv，请先安装 uv：
    echo         powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('uv --version') do set UV_VER=%%i
echo [OK] %UV_VER%

:: Sync deps (uv creates .venv and installs exactly what uv.lock pins)
echo.
echo [1/2] 正在同步依赖（uv sync）...
uv sync
if %errorlevel% neq 0 (
    echo [ERROR] 依赖安装失败
    pause
    exit /b 1
)

echo.
echo [2/2] 安装完成！
echo ====================================
echo.
echo 下一步：
echo   1. 双击 config_wizard.bat 配置账号和定位
echo   2. 双击 start_checkin.bat 开始自动签到
echo.
echo 提示：依赖以 pyproject.toml + uv.lock 为准，勿再手装 pip 包
echo.
pause
