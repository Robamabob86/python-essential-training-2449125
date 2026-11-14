@echo off
REM Pretend race - try the commentator without iRacing running.
cd /d "%~dp0"
call .venv\Scripts\activate.bat 2>nul
python main.py --test %*
pause
