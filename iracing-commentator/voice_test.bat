@echo off
REM Speaks a sample line for every event type, to tune voice/speed/pitch.
cd /d "%~dp0"
call .venv\Scripts\activate.bat 2>nul
python main.py --voice-test %*
pause
