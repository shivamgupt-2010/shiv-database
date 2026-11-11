@echo off
setlocal
echo ========================================================
echo   SHIV DATABASE - 24/7 WINDOWS STARTUP REGISTRATION
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "VBS_PATH=%SCRIPT_DIR%start_service.vbs"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_DIR%\SHIV_Database_24-7.lnk"

if not exist "%VBS_PATH%" (
    echo [ERROR] Could not find %VBS_PATH%
    pause
    exit /b 1
)

echo Registering SHIV Database auto-start in Windows Startup folder...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%VBS_PATH%\"'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'SHIV Database 24/7 Persistent Background Service'; $s.Save()"

if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Shortcut created at:
    echo   %SHORTCUT_PATH%
    echo.
    echo SHIV Database will now automatically start in the background whenever Windows boots!
    echo.
    echo Starting service now in background...
    wscript.exe "%VBS_PATH%"
    echo [OK] Service launched! Check status using check_status.bat
) else (
    echo [ERROR] Failed to register startup shortcut.
)

echo.
pause
