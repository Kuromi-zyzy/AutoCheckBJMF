@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
copy /Y "%~dp0start_checkin.bat" "%STARTUP_DIR%\start_checkin.bat"
if exist "%STARTUP_DIR%\start_checkin.bat" (
    echo Success!
) else (
    echo Failed!
)
pause
