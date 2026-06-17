@echo off
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
copy /Y "%~dp0AutoCheckBJMF.bat" "%STARTUP_DIR%\AutoCheckBJMF.bat"
if exist "%STARTUP_DIR%\AutoCheckBJMF.bat" (
    echo Success!
) else (
    echo Failed!
)
pause
