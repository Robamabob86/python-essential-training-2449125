@echo off
REM Live commentary for iRacing. Double-click to start, Ctrl+C to stop.
cd /d "%~dp0"
call .venv\Scripts\activate.bat 2>nul
python main.py %*
pause
