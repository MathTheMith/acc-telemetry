@echo off
rem Stops the background recorder from starting with Windows. Quit the one
rem currently running from its tray icon (right click, Quit recorder).
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ACC Telemetry recorder.lnk" 2>nul
echo Autostart removed.
pause
