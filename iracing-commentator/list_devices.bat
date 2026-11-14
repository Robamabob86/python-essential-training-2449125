@echo off
REM Shows your audio output devices so you can pick one in config.yaml.
cd /d "%~dp0"
call .venv\Scripts\activate.bat 2>nul
python main.py --list-devices
pause
