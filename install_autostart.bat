@echo off
rem Starts the background recorder with Windows (shortcut in the Startup
rem folder), then launches it right away. Run once; uninstall_autostart.bat
rem removes it.
setlocal
cd /d "%~dp0"

set "PYW="
for /f "delims=" %%i in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW (
    echo pythonw.exe not found in PATH. Install Python 3 and tick "Add to PATH".
    pause
    exit /b 1
)

set "APPDIR=%~dp0"
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ACC Telemetry recorder.lnk"
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK); $s.TargetPath = $env:PYW; $s.Arguments = 'main.py --background'; $s.WorkingDirectory = $env:APPDIR; $s.Save()"
if errorlevel 1 (
    echo Could not create the startup shortcut.
    pause
    exit /b 1
)

start "" "%PYW%" main.py --background
echo The recorder now starts with Windows and is running (tray icon).
pause
