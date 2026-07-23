@echo off
chcp 65001 >nul
title AutoCheckBJMF - 后台签到运行中

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 虚拟环境未找到，请先运行 install.bat 安装
    pause
    exit /b 1
)

if not exist "config.json" (
    echo [ERROR] 配置文件未找到，请先运行 config_wizard.bat 设置
    pause
    exit /b 1
)

echo 正在启动自动签到...
start /B "" ".venv\Scripts\pythonw.exe" "src\main.py"
echo.
echo [OK] 签到程序已在后台静默运行
echo      查看 logs\sign_log.txt 获取签到记录
echo      停止方法：打开任务管理器结束 pythonw.exe
echo.
timeout /t 3 /nobreak >nul
exit
