@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
    py -3 -m venv .venv
)
call .venv\Scripts\activate.bat

pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconsole --onefile --name ACC_Telemetry main.py

echo.
echo Build finished if no errors above.
echo The exe is in dist\ACC_Telemetry.exe
pause
