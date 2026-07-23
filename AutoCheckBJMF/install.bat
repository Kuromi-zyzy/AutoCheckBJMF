@echo off
chcp 65001 >nul
title AutoCheckBJMF - 一键安装

cd /d "%~dp0"

echo ====================================
echo   AutoCheckBJMF - 一键安装
echo ====================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未检测到 Python，请先安装 Python 3.11+
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PY_VER=%%i
echo [OK] %PY_VER%

:: Create venv
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [1/3] 正在创建虚拟环境...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境已创建
) else (
    echo [OK] 虚拟环境已存在，跳过
)

:: Install deps
echo.
echo [2/3] 正在安装依赖包...
.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip >nul
.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple beautifulsoup4 drissionpage prompt-toolkit questionary requests rich schedule
if %errorlevel% neq 0 (
    echo [ERROR] 依赖安装失败
    pause
    exit /b 1
)

echo.
echo [3/3] 安装完成！
echo ====================================
echo.
echo 下一步：
echo   1. 双击 config_wizard.bat 配置账号和定位
echo   2. 双击 start_checkin.bat 开始自动签到
echo.
echo 提示：使用清华镜像加速下载
echo.
pause
